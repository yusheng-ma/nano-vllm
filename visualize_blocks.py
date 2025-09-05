# visualize_blocks.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re


def parse_output_file(filename):
    with open(filename, 'r') as f:
        content = f.read()

    # 用 20 個 '-' 分割 steps
    steps = re.split(r'-{20,}', content)
    steps = [step.strip() for step in steps if step.strip()]

    all_steps = []

    for step in steps:
        lines = step.strip().splitlines()
        step_data = {}
        for line in lines:
            line = line.strip()
            if not line or not re.match(r'\d+\s+\[\s*-?\d+', line):
                continue
            try:
                # 使用正規表示法更穩健地解析
                match = re.match(r'(\d+)\s+(\[.*\])', line)
                if not match:
                    continue
                seq_id = int(match.group(1))
                block_str = match.group(2)
                block_list = list(map(int, re.findall(r'-?\d+', block_str)))
                for block_idx in block_list:
                    if block_idx != -1:
                        step_data[block_idx] = seq_id
            except Exception as e:
                print(f"Error parsing line: {line}, error: {e}")
                continue
        all_steps.append(step_data)

    return all_steps


def visualize_with_plotly(all_steps, num_blocks=696, cols=30):
    rows = (num_blocks + cols - 1) // cols

    # 建立座標
    x_coords = [block_idx % cols for block_idx in range(num_blocks)]
    y_coords = [block_idx // cols for block_idx in range(num_blocks)]

    fig = go.Figure()

    # 初始狀態：全部 free
    initial_colors = [-1] * num_blocks
    initial_texts = [''] * num_blocks
    hovertext = [f"Block {i}" for i in range(num_blocks)]

    # 使用 'Turbo' colorscale：色彩豐富、對比強，適合大量分類
    fig.add_trace(
        go.Scatter(
            x=x_coords,
            y=y_coords,
            mode='markers+text',
            marker=dict(
                size=16,
                color=initial_colors,
                colorscale='Turbo',        # 🔥 強烈推薦：色彩分佈均勻
                cmin=-1,                   # -1 是 free
                cmax=255,                  # 最大 seq_id
                showscale=True,
                colorbar=dict(
                    title="Seq ID",
                    tickmode='array',
                    tickvals=list(range(0, 256, 16)) + [-1],  # 每 16 個標一次
                    ticktext=[str(i) for i in range(0, 256, 16)] + ['Free'],
                    len=0.9
                )
            ),
            text=initial_texts,
            textfont=dict(size=10, color='black'),
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
                colors.append(seq_id)
                texts.append(str(seq_id))
                hovertext.append(f"Block {block_idx} | Seq ID: {seq_id}")
            else:
                colors.append(-1)  # free
                texts.append('')
                hovertext.append(f"Block {block_idx} | Free")

        frames.append(
            go.Frame(
                data=[
                    go.Scatter(
                        marker=dict(color=colors),
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
        title=f"Block Table Visualization (Step 0 / {len(all_steps)-1})",
        xaxis=dict(range=[-0.5, cols - 0.5], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(range=[-0.5, rows - 0.5], showgrid=False, zeroline=False, visible=False, scaleanchor='x', scaleratio=1),
        width=1400,
        height=800,
        plot_bgcolor='white',
        margin=dict(l=20, r=20, t=60, b=100),
        updatemenus=[{
            "type": "buttons",
            "showactive": False,
            "y": -0.1,
            "x": 0.1,
            "xanchor": "right",
            "buttons": [{
                "label": "Play",
                "method": "animate",
                "args": [None, {
                    "frame": {"duration": 200, "redraw": True},
                    "mode": "immediate"
                }]
            }, {
                "label": "Pause",
                "method": "animate",
                "args": [[None], {
                    "frame": {"duration": 0, "redraw": True},
                    "mode": "immediate"
                }]
            }]
        }],
        sliders=[{
            "currentvalue": {"prefix": "Step: ", "font": {"size": 16}},
            "steps": [
                {
                    "args": [[f"frame{step_idx}"], {
                        "frame": {"duration": 0, "redraw": True},
                        "mode": "immediate"
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
    all_steps = parse_output_file("output.txt")
    print(f"總共解析 {len(all_steps)} 個 steps")
    visualize_with_plotly(all_steps, num_blocks=696, cols=30)