from collections import deque

from nanovllm.config import Config
from nanovllm.engine.sequence import Sequence, SequenceStatus
from nanovllm.engine.block_manager import BlockManager


class Scheduler:

    def __init__(self, config: Config):
        self.max_num_seqs = config.max_num_seqs
        self.max_num_batched_tokens = config.max_num_batched_tokens
        self.eos = config.eos
        print(config.num_kvcache_blocks, config.kvcache_block_size)
        self.block_manager = BlockManager(config.num_kvcache_blocks, config.kvcache_block_size)
        self.waiting: deque[Sequence] = deque()
        self.running: deque[Sequence] = deque()

    def is_finished(self):
        return not self.waiting and not self.running

    def add(self, seq: Sequence):
        self.waiting.append(seq)

    def schedule(self) -> tuple[list[Sequence], bool]:
        # prefill
        scheduled_seqs = []
        num_seqs = 0
        num_batched_tokens = 0
        while self.waiting and num_seqs < self.max_num_seqs:
            seq = self.waiting[0]
            if Config.DEBUG_SCHEDULER:
                print(f"Trying to prefill for seq {seq.seq_id}, can_allocate? {self.block_manager.can_allocate(seq)}")
            if num_batched_tokens + len(seq) > self.max_num_batched_tokens or not self.block_manager.can_allocate(seq):
                break
            num_seqs += 1
            self.block_manager.allocate(seq)
            num_batched_tokens += len(seq) - seq.num_cached_tokens
            seq.status = SequenceStatus.RUNNING
            self.waiting.popleft()
            self.running.append(seq)
            scheduled_seqs.append(seq)
        if scheduled_seqs:
            return scheduled_seqs, True

        # decode
        while self.running and num_seqs < self.max_num_seqs:
            seq = self.running.popleft()
            if Config.DEBUG_SCHEDULER:
                print(f"Trying to append for seq {seq.seq_id}, can_append? {self.block_manager.can_append(seq)}")
            while not self.block_manager.can_append(seq):
                if Config.DEBUG_PREEMPT:
                    print(f"[BLOCK SHORTAGE] seq {seq.seq_id} needs to append but no free blocks!")
                if self.running:
                    victim = self.running.pop()
                    if Config.DEBUG_PREEMPT:
                        print(f"  ➤ Preempting victim seq {victim.seq_id} to free blocks...")
                    self.preempt(victim)
                else:
                    self.preempt(seq)
                    break
            else:
                num_seqs += 1
                self.block_manager.may_append(seq)
                scheduled_seqs.append(seq)
        assert scheduled_seqs
        self.running.extendleft(reversed(scheduled_seqs))
        return scheduled_seqs, False

    def preempt(self, seq: Sequence):
        if Config.DEBUG_PREEMPT:
            print(f"[PREEMPT] seq {seq.seq_id:2d} | "
                f"status: {seq.status.name:8s} | "
                f"tokens: {seq.num_tokens:4d} (prompt: {seq.num_prompt_tokens:3d}, comp: {seq.num_completion_tokens:3d}) | "
                f"blocks: {len(seq.block_table):2d} {seq.block_table}")
        seq.status = SequenceStatus.WAITING
        self.block_manager.deallocate(seq)
        self.waiting.appendleft(seq)

    def postprocess(self, seqs: list[Sequence], token_ids: list[int]) -> list[bool]:
        for seq, token_id in zip(seqs, token_ids):
            seq.append_token(token_id)
            if (not seq.ignore_eos and token_id == self.eos) or seq.num_completion_tokens == seq.max_tokens:
                seq.status = SequenceStatus.FINISHED
                self.block_manager.deallocate(seq)
                self.running.remove(seq)
