import os
import time
from random import randint, seed
from nanovllm import LLM, SamplingParams
# from vllm import LLM, SamplingParams


def main():
    BENCH_PREFIX_SHARING = True
    block_size = 256
    min_input_len = block_size * 2  # 確保總長度足夠
    shared_prefix_len = block_size  # 每個 prefix 共享一個完整 block

    seed(0)
    num_seqs = 256
    max_input_len = 1024
    max_output_len = 1024  # 修正 typo: ouput → output

    path = os.path.expanduser("~/huggingface/Qwen3-0.6B/")
    llm = LLM(path, enforce_eager=False, max_model_len=4096)

    if not BENCH_PREFIX_SHARING:
        prompt_token_ids = [[randint(0, 10000) for _ in range(randint(100, max_input_len))] for _ in range(num_seqs)]
    else:
        # ====== 關鍵修改：三種不同的 agent prefix ======
        num_groups = 3
        # 平均分配序列數量（最後一組補餘數）
        group_sizes = [num_seqs // num_groups] * num_groups
        for i in range(num_seqs % num_groups):
            group_sizes[i] += 1

        # 生成三種不同的共享 prefix（每種長度 = block_size）
        shared_prefixes = [
            [randint(0, 10000) for _ in range(shared_prefix_len)]
            for _ in range(num_groups)
        ]

        prompt_token_ids = []
        for group_id in range(num_groups):
            prefix = shared_prefixes[group_id]
            group_size = group_sizes[group_id]
            for _ in range(group_size):
                unique_part_len = randint(
                    min_input_len - shared_prefix_len,
                    max_input_len - shared_prefix_len
                )
                unique_part = [randint(0, 10000) for _ in range(unique_part_len)]
                prompt_token_ids.append(prefix + unique_part)
        # ==============================================

    sampling_params = [
        SamplingParams(temperature=0.6, ignore_eos=True, max_tokens=randint(100, max_output_len))
        for _ in range(num_seqs)
    ]

    print('{' + f'"num_seqs": {num_seqs}' + '}')
    t = time.time()
    llm.generate(prompt_token_ids, sampling_params, use_tqdm=False)
    t = (time.time() - t)
    total_tokens = sum(sp.max_tokens for sp in sampling_params)
    throughput = total_tokens / t
    print(f"Total: {total_tokens}tok, Time: {t:.2f}s, Throughput: {throughput:.2f}tok/s")

    # again test
    print('{' + f'"num_seqs": {num_seqs}' + '}')
    t = time.time()
    llm.generate(prompt_token_ids, sampling_params, use_tqdm=False)
    t = (time.time() - t)
    total_tokens = sum(sp.max_tokens for sp in sampling_params)
    throughput = total_tokens / t
    print(f"Total: {total_tokens}tok, Time: {t:.2f}s, Throughput: {throughput:.2f}tok/s")


if __name__ == "__main__":
    main()
