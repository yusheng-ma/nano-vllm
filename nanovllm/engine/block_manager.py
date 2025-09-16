from collections import deque
import xxhash
import numpy as np

from nanovllm.engine.sequence import Sequence
from nanovllm.config import Config

class Block:

    def __init__(self, block_id):
        self.block_id = block_id
        self.ref_count = 0
        self.hash = -1
        self.token_ids = []

    def update(self, hash: int, token_ids: list[int]):
        self.hash = hash
        self.token_ids = token_ids

    def reset(self):
        self.ref_count = 1
        self.hash = -1
        self.token_ids = []


class BlockManager:

    def __init__(self, num_blocks: int, block_size: int):
        self.block_size = block_size
        self.blocks: list[Block] = [Block(i) for i in range(num_blocks)]
        self.hash_to_block_id: dict[int, int] = dict()
        self.free_block_ids: deque[int] = deque(range(num_blocks))
        self.used_block_ids: set[int] = set()

    @classmethod
    def compute_hash(cls, token_ids: list[int], prefix: int = -1):
        h = xxhash.xxh64()
        if prefix != -1:
            h.update(prefix.to_bytes(8, "little"))
        h.update(np.array(token_ids).tobytes())
        return h.intdigest()

    def _allocate_block(self, block_id: int) -> Block:
        block = self.blocks[block_id]
        assert block.ref_count == 0
        block.reset()
        self.free_block_ids.remove(block_id)
        self.used_block_ids.add(block_id)
        return self.blocks[block_id]

    def _deallocate_block(self, block_id: int) -> Block:
        assert self.blocks[block_id].ref_count == 0
        self.used_block_ids.remove(block_id)
        self.free_block_ids.append(block_id)

    def can_allocate(self, seq: Sequence) -> bool:
        return len(self.free_block_ids) >= seq.num_blocks

    def allocate(self, seq: Sequence):
        assert not seq.block_table
        h = -1
        cache_miss = False

        # 🟢 新增：印出開始分配
        if Config.DEBUG_BLOCK_MANAGER_LV2:
            print(f"[DEBUG] Allocating for seq {seq.seq_id}, total blocks: {seq.num_blocks}, prompt_len={len(seq)}")

        for i in range(seq.num_blocks):
            token_ids = seq.block(i)
            h = self.compute_hash(token_ids, h) if len(token_ids) == self.block_size else -1

            # 🟢 新增：印出當前 block 的 tokens 和 hash
            if Config.DEBUG_BLOCK_MANAGER_LV2:
                print(f"  [Block {i}] tokens: {token_ids[:4]}... (len={len(token_ids)}), hash: {h}")

            block_id = self.hash_to_block_id.get(h, -1)

            # 🟢 新增：印出是否找到 hash 對應的 block_id
            if Config.DEBUG_BLOCK_MANAGER_LV2:
                print(f"    → hash_to_block_id.get({h}) = {block_id}")

            if block_id == -1 or self.blocks[block_id].token_ids != token_ids:
                cache_miss = True

                # 🟢 新增：印出 cache miss 原因
                if Config.DEBUG_BLOCK_MANAGER_LV2:
                    reason = "block_id == -1" if block_id == -1 else "token_ids mismatch"
                    print(f"    ❌ CACHE MISS (reason: {reason}) → will allocate new block")

            if cache_miss:
                block_id = self.free_block_ids[0]
                block = self._allocate_block(block_id)

                # 🟢 新增：印出新分配的 block_id
                if Config.DEBUG_BLOCK_MANAGER_LV2:
                    print(f"    ➤ Allocated NEW block_id: {block_id}")
            else:
                seq.num_cached_tokens += self.block_size

                # 🟢 新增：印出命中快取
                if Config.DEBUG_BLOCK_MANAGER_LV2:
                    print(f"    ✅ CACHE HIT → reusing block_id: {block_id}, num_cached_tokens now: {seq.num_cached_tokens}")

                if block_id in self.used_block_ids:
                    block = self.blocks[block_id]
                    block.ref_count += 1
                else:
                    block = self._allocate_block(block_id)

            if h != -1:
                block.update(h, token_ids)
                self.hash_to_block_id[h] = block_id

                # 🟢 新增：印出 hash 映射更新
                if Config.DEBUG_BLOCK_MANAGER_LV2:
                    print(f"    ➤ Updated hash {h} → block_id {block_id}")

            seq.block_table.append(block_id)

        # 🟢 新增：印出分配完成結果
        if Config.DEBUG_BLOCK_MANAGER_LV2:
            print(f"[DEBUG] ✅ Finished allocating seq {seq.seq_id}: "
                  f"num_cached_tokens={seq.num_cached_tokens}, block_table={seq.block_table}")

    def deallocate(self, seq: Sequence):
        for block_id in reversed(seq.block_table):
            block = self.blocks[block_id]
            block.ref_count -= 1
            if block.ref_count == 0:
                self._deallocate_block(block_id)
            if Config.DEBUG_BLOCK_MANAGER:
                print(f"  [FREE] block {block_id} from seq {seq.seq_id}")
        seq.num_cached_tokens = 0
        seq.block_table.clear()

    def can_append(self, seq: Sequence) -> bool:
        return len(self.free_block_ids) >= (len(seq) % self.block_size == 1)

    def may_append(self, seq: Sequence):
        block_table = seq.block_table
        last_block = self.blocks[block_table[-1]]

        # 🟢 新增：印出進入 may_append
        if Config.DEBUG_BLOCK_MANAGER_LV2:
            print(f"[DEBUG] may_append for seq {seq.seq_id}, len(seq)={len(seq)}, "
                  f"last_block_id={last_block.block_id}, last_block.hash={last_block.hash}, "
                  f"block_table={block_table}")

        if len(seq) % self.block_size == 1:
            assert last_block.hash != -1

            # 🟢 新增：印出「需要新 block」的原因
            if Config.DEBUG_BLOCK_MANAGER_LV2:
                print(f"  ➤ len(seq) % block_size == 1 → need NEW block for new token")

            block_id = self.free_block_ids[0]
            self._allocate_block(block_id)
            block_table.append(block_id)

            # 🟢 新增：印出新分配的 block
            if Config.DEBUG_BLOCK_MANAGER_LV2:
                print(f"  ➤ Allocated NEW block_id: {block_id} for seq {seq.seq_id}")

        elif len(seq) % self.block_size == 0:
            assert last_block.hash == -1

            # 🟢 新增：印出「完整 block，準備計算 hash」
            if Config.DEBUG_BLOCK_MANAGER_LV2:
                print(f"  ➤ len(seq) % block_size == 0 → block now full, computing hash...")

            token_ids = seq.block(seq.num_blocks-1)
            prefix = self.blocks[block_table[-2]].hash if len(block_table) > 1 else -1
            h = self.compute_hash(token_ids, prefix)

            # 🟢 新增：印出計算的 hash 和 token_ids
            if Config.DEBUG_BLOCK_MANAGER_LV2:
                print(f"    → token_ids[:4]={token_ids[:4]}..., prefix_hash={prefix}, computed_hash={h}")

            last_block.update(h, token_ids)
            self.hash_to_block_id[h] = last_block.block_id

            # 🟢 新增：印出 hash 映射更新
            if Config.DEBUG_BLOCK_MANAGER_LV2:
                print(f"    ➤ Mapped hash {h} → block_id {last_block.block_id}")

        else:
            assert last_block.hash == -1

            # 🟢 新增：印出「partial block，無需動作」
            if Config.DEBUG_BLOCK_MANAGER_LV2:
                print(f"  ➤ len(seq) % block_size = {len(seq) % self.block_size} → partial block, no hash update needed")