"""SVG figures for the README: the quarterly trend of loop papers (from data/trend.json)."""
import html
import math

W, H = 1280, 380
X0, X1, Y_TOP, Y_BASE = 84, 1224, 118, 318
SANS = "Inter, 'Segoe UI', 'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"


def nice_max(v):
    """Smallest 1/2/2.5/5 x 10^k at or above v."""
    if v <= 0:
        return 1
    base = 10 ** math.floor(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * base:
            return m * base
    return 10 * base


def esc(s):
    return html.escape(str(s), quote=True)


def trend_svg(trend, title, subtitle, milestones):
    """Area chart of trend["bins"]; milestones = [(period, label)] marked on the curve."""
    bins = trend["bins"]
    n = len(bins)
    top = nice_max(max(b["count"] for b in bins))
    xs = [X0 + (X1 - X0) * i / max(1, n - 1) for i in range(n)]
    ys = [Y_BASE - (Y_BASE - Y_TOP) * b["count"] / top for b in bins]
    full = [i for i in range(n) if not bins[i]["partial"]]
    last_full = full[-1] if full else n - 1
    line = " ".join(f"{'M' if i == 0 else 'L'}{xs[i]:.1f},{ys[i]:.1f}" for i in range(last_full + 1))
    area = line + f" L{xs[last_full]:.1f},{Y_BASE} L{xs[0]:.1f},{Y_BASE} Z"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="{esc(title)}">', f"<title>{esc(title)}</title>",
           "<defs>",
           '<linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22d3ee" '
           'stop-opacity="0.38"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></linearGradient>',
           f'<linearGradient id="stroke" gradientUnits="userSpaceOnUse" x1="{X0}" y1="0" x2="{X1}" y2="0">'
           '<stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#c084fc"/></linearGradient>',
           "</defs>",
           f'<rect width="{W}" height="{H}" rx="18" fill="#0b1020"/>',
           f'<text x="48" y="52" font-family="{SANS}" font-size="22" font-weight="700" fill="#f4f6ff">{esc(title)}'
           "</text>",
           f'<text x="48" y="78" font-family="{SANS}" font-size="13" fill="#8b9bc0">{esc(subtitle)}</text>']
    for k in range(5):  # horizontal grid with labels
        v = top * k / 4
        y = Y_BASE - (Y_BASE - Y_TOP) * k / 4
        label = f"{v:g}"
        out.append(f'<line x1="{X0}" y1="{y:.1f}" x2="{X1}" y2="{y:.1f}" stroke="#1d2947" stroke-width="1"/>')
        out.append(f'<text x="{X0 - 12}" y="{y + 4:.1f}" text-anchor="end" font-family="{SANS}" font-size="11" '
                   f'fill="#6f7fa3">{label}</text>')
    for i, b in enumerate(bins):  # year labels at Q1
        if b["period"].endswith("Q1"):
            out.append(f'<line x1="{xs[i]:.1f}" y1="{Y_BASE}" x2="{xs[i]:.1f}" y2="{Y_BASE + 5}" stroke="#3b4a6e"/>')
            out.append(f'<text x="{xs[i]:.1f}" y="{Y_BASE + 22}" text-anchor="middle" font-family="{SANS}" '
                       f'font-size="12" fill="#8b9bc0">{b["period"][:4]}</text>')
    out += [f'<path d="{area}" fill="url(#fill)"/>',
            f'<path d="{line}" fill="none" stroke="url(#stroke)" stroke-width="2.6" stroke-linejoin="round"/>']
    if last_full < n - 1:  # partial quarter: dashed segment and hollow marker
        i = n - 1
        out.append(f'<path d="M{xs[last_full]:.1f},{ys[last_full]:.1f} L{xs[i]:.1f},{ys[i]:.1f}" fill="none" '
                   f'stroke="#c084fc" stroke-width="2" stroke-dasharray="4 4"/>')
        out.append(f'<circle cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="4" fill="#0b1020" stroke="#c084fc" '
                   f'stroke-width="2"/>')
    j = last_full  # label the latest complete quarter
    out.append(f'<circle cx="{xs[j]:.1f}" cy="{ys[j]:.1f}" r="4.5" fill="#c084fc"/>')
    out.append(f'<text x="{xs[j] - 10:.1f}" y="{ys[j] - 12:.1f}" text-anchor="end" font-family="{SANS}" '
               f'font-size="13" font-weight="600" fill="#e9d5ff">{bins[j]["period"][:4]} Q{bins[j]["period"][-1]}: '
               f'{bins[j]["count"]}</text>')
    index = {b["period"]: i for i, b in enumerate(bins)}
    placed = []
    for period, label in milestones:
        i = index.get(period)
        if i is None:
            continue
        x, y = xs[i], ys[i]
        ly = min(y - 26, Y_BASE - 40)
        while any(abs(x - px) < 150 and abs(ly - py) < 18 for px, py in placed):
            ly -= 20
        placed.append((x, ly))
        anchor = "end" if x > X1 - 200 else "start"
        dx = -6 if anchor == "end" else 6
        out.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{ly + 4:.1f}" stroke="#55648a" '
                   f'stroke-dasharray="2 3"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#67e8f9"/>')
        out.append(f'<text x="{x + dx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-family="{SANS}" '
                   f'font-size="12" fill="#c7d2fe">{esc(label)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
