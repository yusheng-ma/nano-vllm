import os
import time
from random import randint, seed
from nanovllm import LLM, SamplingParams
# from vllm import LLM, SamplingParams


def main():
    # consider block size is 256
    seed(0)
    num_seqs = 2
    max_input_len = 512
    max_ouput_len = 512

    path = os.path.expanduser("~/huggingface/Qwen3-0.6B/")
    llm = LLM(path, enforce_eager=False, max_model_len=4096)

    # prompt_token_ids = [[randint(0, 10000) for _ in range(randint(100, max_input_len))] for _ in range(num_seqs)]
    # ====== 關鍵修改：讓 shared_prefix 長度 >= block_size (256) ======
    block_size = 256
    min_input_len = block_size * 2  # 確保總長度足夠
    shared_prefix_len = block_size  # 共享一個完整 block

    shared_prefix = [randint(0, 10000) for _ in range(shared_prefix_len)]

    prompt_token_ids = [
        shared_prefix + [
            randint(0, 10000)
            for _ in range(randint(min_input_len - shared_prefix_len, max_input_len - shared_prefix_len))
        ]
        for _ in range(num_seqs)
    ]
    # =================================================================
    sampling_params = [SamplingParams(temperature=0.6, ignore_eos=True, max_tokens=randint(100, max_ouput_len)) for _ in range(num_seqs)]
    # uncomment the following line for vllm
    # prompt_token_ids = [dict(prompt_token_ids=p) for p in prompt_token_ids]
    # for i, (prompt, sp) in enumerate(zip(prompt_token_ids, sampling_params)):
    #     print(f"Seq {i}: prompt_len={len(prompt)}, max_tokens={sp.max_tokens}")
    # llm.generate(["Benchmark: "], SamplingParams()) # warm up... skipp!
    print('{' + f'"num_seqs": {num_seqs}' + '}')
    t = time.time()
    llm.generate(prompt_token_ids, sampling_params, use_tqdm=False)
    t = (time.time() - t)
    total_tokens = sum(sp.max_tokens for sp in sampling_params)
    throughput = total_tokens / t
    print(f"Total: {total_tokens}tok, Time: {t:.2f}s, Throughput: {throughput:.2f}tok/s")


if __name__ == "__main__":
    main()
