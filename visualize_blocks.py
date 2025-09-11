# visualize_blocks.py (Final Clean Version for Prefix Sharing)
import json
import re
import os


def parse_output_file(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()

    # 1. Skip first two lines (KV cache allocation info)
    lines = lines[2:]

    # 2. Parse third line: "5 256" → num_blocks
    first_data_line = lines[0].strip()
    match = re.match(r'(\d+)\s+(\d+)', first_data_line)
    if not match:
        raise ValueError(f"Expected format 'num_kv_cache_block total_tokens' but got: {first_data_line}")
    num_kv_cache_block = int(match.group(1))
    print(f"🔢 Auto-detected num_blocks = {num_kv_cache_block}")

    # 3. Next line: {"num_seqs": 2} → optional, for info
    second_data_line = lines[1].strip()
    num_seqs = 1  # default
    try:
        if second_data_line.startswith('{') and '"num_seqs"' in second_data_line:
            meta = json.loads(second_data_line)
            num_seqs = meta.get("num_seqs", 1)
            print(f"🧬 Detected num_seqs = {num_seqs}")
    except Exception as e:
        print(f"⚠️ Could not parse metadata line: {second_data_line}, error: {e}")

    # 4. Remove last line (summary) and first two data lines we just used
    lines = lines[2:-1]

    # Rejoin for splitting by separator
    content = ''.join(lines)

    # Split steps by 20+ dashes
    steps = re.split(r'-{20,}', content)
    steps = [step.strip() for step in steps if step.strip()]

    all_steps = []
    all_seq_ids = set()

    for step in steps:
        lines = step.strip().splitlines()
        step_data = {}  # block_id -> set(seq_ids)
        for line in lines:
            line = line.strip()
            if not line or not re.match(r'\d+\s+\[.*\]', line):
                continue
            try:
                match = re.match(r'(\d+)\s+(\[.*\])', line)
                if not match:
                    continue
                seq_id = int(match.group(1))
                all_seq_ids.add(seq_id)
                block_str = match.group(2)
                block_list = list(map(int, re.findall(r'-?\d+', block_str)))
                for block_idx in block_list:
                    if block_idx != -1:
                        if block_idx not in step_data:
                            step_data[block_idx] = set()
                        step_data[block_idx].add(seq_id)
            except Exception as e:
                print(f"⚠️ Error parsing line: {line}, error: {e}")
                continue
        all_steps.append(step_data)

    max_seq_id = max(all_seq_ids) if all_seq_ids else 0
    min_seq_id = min(all_seq_ids) if all_seq_ids else 0
    print(f"🆔 Observed seq_ids: {sorted(all_seq_ids)}")

    return all_steps, num_kv_cache_block, sorted(all_seq_ids)


def generate_html_visualization(all_steps, num_blocks, seq_ids):
    # Prepare data for JS
    steps_data = []
    for step_data in all_steps:
        grid = [[] for _ in range(num_blocks)]
        for block_idx, seq_id_set in step_data.items():
            if block_idx < num_blocks:
                grid[block_idx] = sorted(list(seq_id_set))
        steps_data.append(grid)

    js_steps_data = json.dumps(steps_data)
    total_steps = len(all_steps)

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>KV Cache Block Visualizer</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 10px;
            background-color: #fafafa;
            color: #333;
            overflow-x: auto; /* 允許水平滾動 */
        }}
        #container {{
            display: inline-block;
            margin-top: 10px;
        }}
        .grid {{
            display: flex; /* 改用 flex 更穩定 */
            flex-wrap: wrap; /* 每行滿了就換行 */
            gap: 1px;
            background: white;
            padding: 8px;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            width: 100%; /* ← 強制佔滿父容器 */
            min-width: 100%; /* ← 防止縮小 */
        }}
        .block {{
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-family: 'Courier New', monospace;
            border: 1px solid #eee;
            background-color: white;
            cursor: default;
            transition: all 0.15s ease;
            position: relative;
        }}
        .block.occupied {{
            background-color: #f8f8f8;
            font-weight: bold;
        }}
        .block.shared {{
            background-color: #fff3cd !important;
            border: 1px solid #ffd54f;
            box-shadow: none;
        }}
        .block:hover {{
            z-index: 10;
            transform: scale(1.2);
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
        }}
        .tooltip {{
            visibility: hidden;
            position: absolute;
            bottom: 110%;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 11px;
            white-space: nowrap;
            opacity: 0;
            transition: opacity 0.2s;
            pointer-events: none;
        }}
        .block:hover .tooltip {{
            visibility: visible;
            opacity: 1;
        }}
        .controls {{
            display: flex;
            flex-wrap: nowrap;
            align-items: center;
            gap: 6px;
            background: white;
            padding: 8px 12px;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 8px;
        }}
        button {{
            padding: 4px 8px;
            font-size: 12px;
            cursor: pointer;
            border: 1px solid #ccc;
            background: #f8f8f8;
            border-radius: 4px;
            transition: background 0.2s;
        }}
        button:hover {{
            background: #e8e8e8;
        }}
        button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        button.playing {{
            background: #d4edda;
            border-color: #c3e6cb;
            color: #155724;
        }}
        #step-display {{
            font-size: 14px;
            font-weight: 500;
            min-width: 100px;
            text-align: center;
            margin: 0 6px;
        }}
        #slider {{
            width: 300px;
        }}
        .slider-container {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        h2 {{
            color: #2c3e50;
            margin: 5px 0 10px 0;
            font-size: 18px;
        }}
    </style>
</head>
<body>
    <h2>KV Cache Block Table (Blocks: {num_blocks})</h2>

    <div class="controls">
        <button id="btn-first" title="First Step">⏮️</button>
        <button id="btn-prev" title="Previous Step">⬅️</button>
        <button id="btn-play" title="Play/Pause">▶️</button>
        <button id="btn-next" title="Next Step">➡️</button>
        <button id="btn-last" title="Last Step">⏭️</button>
        <span id="step-display">Step 0 / {total_steps - 1}</span>
        <div class="slider-container">
            <input type="range" id="slider" min="0" max="{total_steps - 1}" value="0" step="1">
        </div>
    </div>

    <div id="container">
        <div id="grid" class="grid"></div>
    </div>

    <script>
        const stepsData = {js_steps_data};
        const numBlocks = {num_blocks};
        let currentStep = 0;
        let isPlaying = false;
        let playInterval = null;
        const playSpeed = 300;

        let blockElements = [];

        function renderGrid() {{
            const grid = document.getElementById('grid');

            if (blockElements.length === 0) {{
                grid.innerHTML = '';
                for (let i = 0; i < numBlocks; i++) {{
                    const block = document.createElement('div');
                    block.className = 'block';
                    block.id = `block-${{i}}`;

                    const tooltip = document.createElement('div');
                    tooltip.className = 'tooltip';
                    block.appendChild(tooltip);

                    grid.appendChild(block);
                    blockElements.push({{ block, tooltip }});
                }}
            }}

            const data = stepsData[currentStep];
            for (let i = 0; i < numBlocks; i++) {{
                const {{ block, tooltip }} = blockElements[i];
                const seqList = data[i] || [];

                block.className = 'block';
                tooltip.textContent = '';

                if (seqList.length > 0) {{
                    block.classList.add('occupied');
                    if (seqList.length === 1) {{
                        block.textContent = seqList[0];
                        block.title = `Block ${{i}} | Seq: ${{seqList[0]}}`;
                    }} else {{
                        block.classList.add('shared');
                        block.textContent = "★";
                        const sharedText = `Shared by: ${{seqList.join(', ')}}`;
                        tooltip.textContent = sharedText;
                        block.title = `Block ${{i}} | ${{sharedText}}`;
                    }}
                }} else {{
                    block.textContent = '';
                    block.title = `Block ${{i}} | Free`;
                }}
            }}

            document.getElementById('step-display').textContent = `Step ${{currentStep}} / {total_steps - 1}`;
            document.getElementById('slider').value = currentStep;

            document.getElementById('btn-prev').disabled = currentStep === 0;
            document.getElementById('btn-next').disabled = currentStep === {total_steps - 1};
        }}

        function goToStep(step) {{
            currentStep = step;
            renderGrid();
        }}

        function stepForward() {{
            if (currentStep < {total_steps - 1}) {{
                currentStep++;
                renderGrid();
            }}
        }}

        function stepBackward() {{
            if (currentStep > 0) {{
                currentStep--;
                renderGrid();
            }}
        }}

        function togglePlay() {{
            const btn = document.getElementById('btn-play');
            if (isPlaying) {{
                clearInterval(playInterval);
                isPlaying = false;
                btn.textContent = '▶️';
                btn.classList.remove('playing');
            }} else {{
                isPlaying = true;
                btn.textContent = '⏸️';
                btn.classList.add('playing');
                playInterval = setInterval(() => {{
                    if (currentStep >= {total_steps - 1}) {{
                        clearInterval(playInterval);
                        isPlaying = false;
                        btn.textContent = '▶️';
                        btn.classList.remove('playing');
                        return;
                    }}
                    stepForward();
                }}, playSpeed);
            }}
        }}

        document.getElementById('btn-first').addEventListener('click', () => goToStep(0));
        document.getElementById('btn-prev').addEventListener('click', stepBackward);
        document.getElementById('btn-play').addEventListener('click', togglePlay);
        document.getElementById('btn-next').addEventListener('click', stepForward);
        document.getElementById('btn-last').addEventListener('click', () => goToStep({total_steps - 1}));

        document.getElementById('slider').addEventListener('input', (e) => {{
            goToStep(parseInt(e.target.value));
        }});

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowRight') {{
                stepForward();
            }} else if (e.key === 'ArrowLeft') {{
                stepBackward();
            }} else if (e.key === ' ') {{
                e.preventDefault();
                togglePlay();
            }}
        }});

        renderGrid();
    </script>
</body>
</html>
"""
    output_file = "interactive_blocks.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ 成功生成滿版顯示的 KV Cache Block 視覺化！")
    print(f"📍 已儲存為: interactive_blocks.html")
    print(f"🎮 特性：")
    print(f"   📏 所有 blocks 自動填滿整行，無右側留白")
    print(f"   🌐 適應任何螢幕寬度，橫向可捲動查看")
    print(f"   🟡 黃色邊框 = 共享 block，懸停看共享序列")
    print(f"   ⌨️  鍵盤控制與播放功能保留")


if __name__ == "__main__":
    all_steps, num_blocks, seq_ids = parse_output_file("output.txt")
    print(f"📊 總共解析 {len(all_steps)} 個 steps")
    print(f"👥 涉及序列: {seq_ids}")
    generate_html_visualization(all_steps, num_blocks, seq_ids)