#!/usr/bin/env python3
"""Write the README banners assets/banner.svg (English subtitle) and assets/banner.zh-CN.svg (Chinese subtitle).

Edit SUB below to change the text, then run: python3 scripts/banner.py
"""
import html
import os

W, H = 1280, 400
CX, A, B, T = 935, 118, 33, 8          # stack centre x, slab half-width, half-depth, thickness
Y0, STEP = 336, 36                     # bottom slab centre, vertical spacing
ROLES = ["edge", "edge", "core", "core", "core", "core", "edge", "edge"]   # bottom -> top
SANS = "Inter, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
CJK = "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', 'Source Han Sans SC', sans-serif"

SUB = {
    "en": (["Loop Transformers are becoming the default pre-training architecture",
            "for stronger reasoning. How to build loops that are principled and",
            "efficient remains wide open."], SANS, 18, "PAPERS · OPEN MODELS · EVIDENCE", 3),
    "zh": (["Loop Transformer 正在成为增强推理能力的默认预训练架构；",
            "如何构建更科学、更高效的循环结构，仍有广阔的探索空间。"], CJK, 19, "论文 · 开源模型 · 证据", 4),
}


def slab(cy, role):
    top = [(CX - A, cy), (CX, cy - B), (CX + A, cy), (CX, cy + B)]
    left = [(CX - A, cy), (CX, cy + B), (CX, cy + B + T), (CX - A, cy + T)]
    right = [(CX, cy + B), (CX + A, cy), (CX + A, cy + T), (CX, cy + B + T)]
    pts = lambda ps: " ".join(f"{x:g},{y:g}" for x, y in ps)
    if role == "core":
        return (f'<polygon points="{pts(left)}" fill="#1e3a8a"/><polygon points="{pts(right)}" fill="#312e81"/>'
                f'<polygon points="{pts(top)}" fill="url(#core)" fill-opacity="0.92" stroke="#bfdbfe" '
                f'stroke-opacity="0.55" stroke-width="1"/>')
    return (f'<polygon points="{pts(left)}" fill="#111a2e"/><polygon points="{pts(right)}" fill="#0e1628"/>'
            f'<polygon points="{pts(top)}" fill="#1b2540" stroke="#3b4a6e" stroke-width="1"/>')


def build(lang):
    lines, font, size, foot, foot_ls = SUB[lang]
    ys = [Y0 - i * STEP for i in range(len(ROLES))]
    core_top, core_bot = ys[5], ys[2]
    x_in = CX + A + 6
    ribbon = f"M{x_in},{core_top} C{x_in + 150},{core_top - 34} {x_in + 150},{core_bot + 34} {x_in + 4},{core_bot}"
    echo = lambda dx, op, w: (f'<path d="M{x_in},{core_top} C{x_in + 150 + dx},{core_top - 34 - dx / 3} '
                              f'{x_in + 150 + dx},{core_bot + 34 + dx / 3} {x_in + 4},{core_bot}" fill="none" '
                              f'stroke="url(#ribbon)" stroke-opacity="{op}" stroke-width="{w}"/>')
    tip = (x_in - 2, core_bot)
    head = f"M{tip[0]},{tip[1]} L{tip[0] + 13},{tip[1] - 8} L{tip[0] + 11},{tip[1] + 7} Z"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="The Era of Loop. {html.escape(" ".join(lines))}">',
        f"<title>The Era of Loop</title>",
        "<defs>",
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#060a16"/>'
        '<stop offset="0.55" stop-color="#0c1530"/><stop offset="1" stop-color="#080d1f"/></linearGradient>',
        '<radialGradient id="glow" cx="0.74" cy="0.52" r="0.42"><stop offset="0" stop-color="#4f7cff" '
        'stop-opacity="0.30"/><stop offset="1" stop-color="#4f7cff" stop-opacity="0"/></radialGradient>',
        '<linearGradient id="core" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#60a5fa"/>'
        '<stop offset="0.6" stop-color="#818cf8"/><stop offset="1" stop-color="#a78bfa"/></linearGradient>',
        '<linearGradient id="ribbon" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22d3ee"/>'
        '<stop offset="0.5" stop-color="#818cf8"/><stop offset="1" stop-color="#c084fc"/></linearGradient>',
        '<linearGradient id="title" gradientUnits="userSpaceOnUse" x1="405" y1="0" x2="575" y2="0">'
        '<stop offset="0" stop-color="#67e8f9"/><stop offset="1" stop-color="#c4b5fd"/></linearGradient>',
        '<linearGradient id="rule" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#67e8f9"/>'
        '<stop offset="1" stop-color="#c4b5fd"/></linearGradient>',
        '<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" '
        'fill="#ffffff" fill-opacity="0.07"/></pattern>',
        '<filter id="blur" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="7"/></filter>',
        "</defs>",
        "<style>.pulse{stroke-dasharray:18 640;animation:flow 3.6s linear infinite}"
        "@keyframes flow{from{stroke-dashoffset:0}to{stroke-dashoffset:-658}}"
        "@media (prefers-reduced-motion:reduce){.pulse{animation:none;stroke-opacity:0}}</style>",
        f'<rect width="{W}" height="{H}" fill="url(#bg)"/>',
        f'<rect width="{W}" height="{H}" fill="url(#dots)"/>',
        f'<rect width="{W}" height="{H}" fill="url(#glow)"/>',
        # motif
        f'<path d="{ribbon}" fill="none" stroke="url(#ribbon)" stroke-width="10" stroke-opacity="0.55" '
        f'filter="url(#blur)"/>',
    ]
    out += [slab(y, r) for y, r in zip(ys, ROLES)]
    out += [
        echo(40, 0.16, 1.5), echo(20, 0.32, 1.8),
        f'<path d="{ribbon}" fill="none" stroke="url(#ribbon)" stroke-width="3" stroke-linecap="round"/>',
        f'<path class="pulse" d="{ribbon}" fill="none" stroke="#ecfeff" stroke-width="4" stroke-linecap="round"/>',
        f'<path d="{head}" fill="#c084fc"/>',
        f'<text x="{x_in + 128}" y="{(core_top + core_bot) / 2 + 7:g}" font-family="Georgia, \'Times New Roman\', serif" '
        f'font-style="italic" font-size="24" fill="#c4b5fd">×T</text>',
        # text block
        f'<text x="88" y="104" font-family="{SANS}" font-size="14" font-weight="600" letter-spacing="4.5" '
        f'fill="#7aa2ff">AWESOME LOOP</text>',
        f'<text x="86" y="184" font-family="{SANS}" font-size="66" font-weight="700" letter-spacing="-1.2" '
        f'fill="#f4f6ff">The Era of <tspan fill="url(#title)">Loop</tspan></text>',
        *[f'<text x="88" y="{244 + 29 * i}" font-family="{font}" font-size="{size}" fill="#b9c5dd">'
          f'{html.escape(line)}</text>' for i, line in enumerate(lines)],
        f'<rect x="88" y="{268 + 29 * len(lines)}" width="44" height="2" fill="url(#rule)"/>',
        f'<text x="146" y="{274 + 29 * len(lines)}" font-family="{font}" font-size="12" letter-spacing="{foot_ls}" '
        f'fill="#6f7fa3">{foot}</text>',
        "</svg>",
    ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for lang, name in (("en", "banner.svg"), ("zh", "banner.zh-CN.svg")):
        with open(os.path.join(root, "assets", name), "w", encoding="utf-8") as f:
            f.write(build(lang))
        print("wrote", name)
