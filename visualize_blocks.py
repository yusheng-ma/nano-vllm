# visualize_blocks.py
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

    # 3. Next line: {"num_seqs": 1} → optional, for info
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
        step_data = {}
        for line in lines:
            line = line.strip()
            if not line or not re.match(r'\d+\s+\[\s*-?\d+', line):
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
                        step_data[block_idx] = seq_id
            except Exception as e:
                print(f"⚠️ Error parsing line: {line}, error: {e}")
                continue
        all_steps.append(step_data)

    max_seq_id = max(all_seq_ids) if all_seq_ids else 0
    min_seq_id = min(all_seq_ids) if all_seq_ids else 0
    print(f"🆔 Observed seq_ids: {sorted(all_seq_ids)}")

    return all_steps, num_kv_cache_block


def generate_html_visualization(all_steps, num_blocks, cols=10):
    rows = (num_blocks + cols - 1) // cols

    # Prepare data for JS
    steps_data = []
    for step_data in all_steps:
        grid = [-1] * num_blocks  # -1 means free
        for block_idx, seq_id in step_data.items():
            if block_idx < num_blocks:
                grid[block_idx] = seq_id
        steps_data.append(grid)

    # Generate JS array
    js_steps_data = json.dumps(steps_data)
    total_steps = len(all_steps)

    # Generate HTML with embedded JS
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>KV Cache Block Visualizer</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 20px;
            background-color: #fafafa;
            color: #333;
        }}
        #container {{
            display: inline-block;
            margin-top: 20px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat({cols}, 30px);
            gap: 2px;
            margin-bottom: 20px;
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .block {{
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-family: 'Courier New', monospace;
            border: 1px solid #ddd;
            background-color: white;
            cursor: default;
            transition: all 0.2s ease;
        }}
        .block.occupied {{
            background-color: #e9e9e9;
            font-weight: bold;
        }}
        .controls {{
            margin: 20px 0;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        button {{
            padding: 8px 16px;
            font-size: 14px;
            cursor: pointer;
            border: 1px solid #ccc;
            background: #f8f8f8;
            border-radius: 6px;
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
            font-size: 18px;
            font-weight: bold;
            margin: 0 10px;
            min-width: 120px;
            text-align: center;
        }}
        #slider {{
            width: 100%;
            max-width: 600px;
        }}
        .slider-container {{
            width: 100%;
            max-width: 600px;
            margin: 10px 0;
        }}
        h2 {{
            color: #2c3e50;
        }}
    </style>
</head>
<body>
    <h2>KV Cache Block Table</h2>
    <div class="controls">
        <button id="btn-first" title="First Step">⏮️ First</button>
        <button id="btn-prev" title="Previous Step">⬅️ Back</button>
        <button id="btn-play" title="Play/Pause">▶️ Play</button>
        <button id="btn-next" title="Next Step">➡️ Next</button>
        <button id="btn-last" title="Last Step">⏭️ Last</button>
        <span id="step-display">Step 0 / {total_steps - 1}</span>
    </div>

    <div class="slider-container">
        <input type="range" id="slider" min="0" max="{total_steps - 1}" value="0" step="1">
    </div>

    <div id="container">
        <div id="grid" class="grid"></div>
    </div>

    <script>
        const stepsData = {js_steps_data};
        const numBlocks = {num_blocks};
        const cols = {cols};
        let currentStep = 0;
        let isPlaying = false;
        let playInterval = null;
        const playSpeed = 200; // ms per frame

        function renderGrid() {{
            const grid = document.getElementById('grid');
            grid.innerHTML = '';
            grid.style.gridTemplateColumns = `repeat(${{cols}}, 30px)`;

            const data = stepsData[currentStep];
            for (let i = 0; i < numBlocks; i++) {{
                const block = document.createElement('div');
                block.className = 'block';
                if (data[i] !== -1) {{
                    block.classList.add('occupied');
                    block.textContent = data[i];
                    block.title = `Block ${{i}} | Seq ID: ${{data[i]}}`;
                }} else {{
                    block.title = `Block ${{i}} | Free`;
                }}
                grid.appendChild(block);
            }}

            document.getElementById('step-display').textContent = `Step ${{currentStep}} / {total_steps - 1}`;
            document.getElementById('slider').value = currentStep;

            // Update button states
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
                btn.textContent = '▶️ Play';
                btn.classList.remove('playing');
            }} else {{
                isPlaying = true;
                btn.textContent = '⏸️ Pause';
                btn.classList.add('playing');
                playInterval = setInterval(() => {{
                    if (currentStep >= {total_steps - 1}) {{
                        clearInterval(playInterval);
                        isPlaying = false;
                        btn.textContent = '▶️ Play';
                        btn.classList.remove('playing');
                        return;
                    }}
                    stepForward();
               }}, playSpeed);
            }}
        }}

        // Event listeners
        document.getElementById('btn-first').addEventListener('click', () => goToStep(0));
        document.getElementById('btn-prev').addEventListener('click', stepBackward);
        document.getElementById('btn-play').addEventListener('click', togglePlay);
        document.getElementById('btn-next').addEventListener('click', stepForward);
        document.getElementById('btn-last').addEventListener('click', () => goToStep({total_steps - 1}));

        document.getElementById('slider').addEventListener('input', (e) => {{
            goToStep(parseInt(e.target.value));
        }});

        // Keyboard navigation
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

        // Initialize
        renderGrid();
    </script>
</body>
</html>
"""

    output_file = "interactive_blocks.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ 成功生成互動式視覺化檔案！")
    print(f"📍 已儲存為: {output_file}")
    print(f"🎮 控制方式：")
    print(f"   ⏯️  按鈕：播放/暫停、上一步、下一步、首步、末步")
    print(f"   🎚️  滑桿：拖曳或點擊跳轉步驟")
    print(f"   ⌨️  鍵盤：← → 方向鍵切換步驟，空白鍵播放/暫停")


if __name__ == "__main__":
    all_steps, num_blocks = parse_output_file("output.txt")
    print(f"📊 總共解析 {len(all_steps)} 個 steps")
    generate_html_visualization(all_steps, num_blocks, cols=10)  # adjust cols as needed