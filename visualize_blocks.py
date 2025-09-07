# visualize_blocks.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import json


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
    print(f"🆔 Observed seq_ids: {sorted(all_seq_ids)} → setting cmax={max_seq_id}")

    return all_steps, num_kv_cache_block, max_seq_id


def visualize_with_plotly(all_steps, num_blocks=696, cols=30):
    rows = (num_blocks + cols - 1) // cols

    # 建立座標
    x_coords = [block_idx % cols for block_idx in range(num_blocks)]
    y_coords = [block_idx // cols for block_idx in range(num_blocks)]

    fig = go.Figure()

    # 初始狀態：全部 free → neutral background
    initial_colors = ['#f0f0f0' if i < num_blocks else '#ffffff' for i in range(num_blocks)]  # light gray for valid blocks
    initial_texts = [''] * num_blocks
    hovertext = [f"Block {i}" for i in range(num_blocks)]

    # 使用固定灰色背景，無 colorscale
    fig.add_trace(
        go.Scatter(
            x=x_coords,
            y=y_coords,
            mode='markers+text',
            marker=dict(
                size=20,
                color=initial_colors,  # fixed light gray
                line=dict(width=1, color='lightgray')
            ),
            text=initial_texts,
            textfont=dict(size=12, color='black', family="Courier New"),
            hovertext=hovertext,
            hoverinfo='text',
            showlegend=False
        )
    )

    # 建立 frames
    frames = []
    for step_idx, step_data in enumerate(all_steps):
        colors = []
        texts = []
        hovertext = []
        for block_idx in range(num_blocks):
            if block_idx in step_data:
                seq_id = step_data[block_idx]
                colors.append('#e3e3e3')  # soft gray background for occupied
                texts.append(str(seq_id))
                hovertext.append(f"Block {block_idx} | Seq ID: {seq_id}")
            else:
                colors.append('#ffffff')  # white for free
                texts.append('')
                hovertext.append(f"Block {block_idx} | Free")

        frame_name = f"frame{step_idx}"
        frames.append(
            go.Frame(
                name=frame_name,
                data=[
                    go.Scatter(
                        marker=dict(color=colors, line=dict(width=1, color='lightgray')),
                        text=texts,
                        hovertext=hovertext
                    )
                ],
                layout=go.Layout(title=f"Step {step_idx} / {len(all_steps)-1}")
            )
        )

    fig.frames = frames

    # Layout
    fig.update_layout(
        title=f"KV Cache Block Table: Seq ID Only (Step 0 / {len(all_steps)-1})",
        xaxis=dict(range=[-0.5, cols - 0.5], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(range=[-0.5, rows - 0.5], showgrid=False, zeroline=False, visible=False, scaleanchor='x', scaleratio=1),
        width=1400,
        height=max(600, rows * 25),  # auto-adjust height based on rows
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=20, r=20, t=60, b=100),
        updatemenus=[{
            "type": "buttons",
            "showactive": False,
            "y": -0.1,
            "x": 0.1,
            "xanchor": "right",
            "buttons": [{
                "label": "▶️ Play",
                "method": "animate",
                "args": [None, {
                    "frame": {"duration": 200, "redraw": True},
                    "mode": "immediate",
                    "fromcurrent": True,
                    "transition": {"duration": 0}
                }]
            }, {
                "label": "⏸️ Pause",
                "method": "animate",
                "args": [[None], {
                    "frame": {"duration": 0, "redraw": True},
                    "mode": "immediate",
                    "transition": {"duration": 0}
                }]
            }]
        }],
        sliders=[{
            "currentvalue": {"prefix": "Step: ", "font": {"size": 16}},
            "steps": [
                {
                    "args": [[f"frame{step_idx}"], {
                        "frame": {"duration": 0, "redraw": True},
                        "mode": "immediate",
                        "transition": {"duration": 0}
                    }],
                    "label": str(step_idx),
                    "method": "animate"
                } for step_idx in range(len(all_steps))
            ],
            "x": 0.1,
            "len": 0.8,
            "y": -0.15,
            "yanchor": "top",
            "xanchor": "left"
        }]
    )

    fig.write_html("block_visualization.html", auto_open=True)
    print(f"✅ 成功生成視覺化檔案！")
    print(f"📍 已儲存為: block_visualization.html")


if __name__ == "__main__":
    # 請確認 output.txt 與此腳本在同一資料夾
    all_steps, num_blocks, max_seq_id = parse_output_file("output.txt")
    print(f"📊 總共解析 {len(all_steps)} 個 steps")
    visualize_with_plotly(all_steps, num_blocks=num_blocks, cols=30)