"""Gráficos de linha e de barras em SVG, sem dependências externas."""

import math
from html import escape

COLORS = ["#1d4ed8", "#c62828", "#2e7d32", "#ef6c00", "#6a1b9a", "#00838f"]
WIDTH, HEIGHT = 720, 420
MARGIN = {"left": 70, "right": 170, "top": 50, "bottom": 60}


def _fmt(value: float) -> str:
    if value >= 100:
        text = f"{value:,.0f}"
    elif value >= 1:
        text = f"{value:,.1f}"
    else:
        text = f"{value:.2g}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _frame(title: str, x_label: str, y_label: str, body: list[str]) -> str:
    plot_w = WIDTH - MARGIN["left"] - MARGIN["right"]
    plot_h = HEIGHT - MARGIN["top"] - MARGIN["bottom"]
    cx = MARGIN["left"] + plot_w / 2
    cy = MARGIN["top"] + plot_h / 2
    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Helvetica, Arial, sans-serif" font-size="12">',
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
            f'<text x="{MARGIN["left"]}" y="28" font-size="15" font-weight="bold" fill="#1f2933">'
            f"{escape(title)}</text>",
            f'<text x="{cx}" y="{HEIGHT - 16}" text-anchor="middle" fill="#52606d">{escape(x_label)}</text>',
            f'<text transform="translate(18 {cy}) rotate(-90)" text-anchor="middle" fill="#52606d">'
            f"{escape(y_label)}</text>",
            *body,
            "</svg>",
        ]
    )


def _legend(names: list[str]) -> list[str]:
    x = WIDTH - MARGIN["right"] + 16
    items = []
    for i, name in enumerate(names):
        y = MARGIN["top"] + 8 + i * 20
        color = COLORS[i % len(COLORS)]
        items.append(f'<rect x="{x}" y="{y - 9}" width="12" height="12" rx="2" fill="{color}"/>')
        items.append(f'<text x="{x + 18}" y="{y + 1}" fill="#1f2933">{escape(name)}</text>')
    return items


def line_chart(
    title: str,
    x_label: str,
    y_label: str,
    xs: list[float],
    series: dict[str, list[float]],
    log_y: bool = False,
) -> str:
    plot_w = WIDTH - MARGIN["left"] - MARGIN["right"]
    plot_h = HEIGHT - MARGIN["top"] - MARGIN["bottom"]
    values = [v for ys in series.values() for v in ys if v > 0 or not log_y]
    if log_y:
        lo = 10 ** math.floor(math.log10(min(values)))
        hi = 10 ** math.ceil(math.log10(max(values)))
        ticks = [10**e for e in range(round(math.log10(lo)), round(math.log10(hi)) + 1)]

        def ty(v):
            return math.log10(v / lo) / math.log10(hi / lo)
    else:
        lo, hi = 0.0, max(values) * 1.1
        ticks = [hi * k / 5 for k in range(6)]

        def ty(v):
            return (v - lo) / (hi - lo)

    x_lo, x_hi = min(xs), max(xs)

    def px(x):
        return MARGIN["left"] + (x - x_lo) / (x_hi - x_lo) * plot_w

    def py(v):
        return MARGIN["top"] + plot_h - ty(v) * plot_h

    body = []
    for t in ticks:
        y = py(t)
        body.append(f'<line x1="{MARGIN["left"]}" x2="{MARGIN["left"] + plot_w}" y1="{y}" y2="{y}" stroke="#e5e9ef"/>')
        body.append(f'<text x="{MARGIN["left"] - 8}" y="{y + 4}" text-anchor="end" fill="#52606d">{_fmt(t)}</text>')
    for x in xs:
        body.append(
            f'<text x="{px(x)}" y="{MARGIN["top"] + plot_h + 20}" text-anchor="middle" fill="#52606d">{_fmt(x)}</text>'
        )
    body.append(
        f'<line x1="{MARGIN["left"]}" x2="{MARGIN["left"] + plot_w}" y1="{MARGIN["top"] + plot_h}" '
        f'y2="{MARGIN["top"] + plot_h}" stroke="#9aa5b1"/>'
    )
    for i, ys in enumerate(series.values()):
        color = COLORS[i % len(COLORS)]
        points = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs, ys, strict=True))
        body.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for x, y in zip(xs, ys, strict=True):
            body.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="4" fill="{color}"/>')
    body += _legend(list(series))
    return _frame(title, x_label, y_label, body)


def stacked_bars(title: str, x_label: str, y_label: str, categories: list[str], stacks: dict[str, list[float]]) -> str:
    plot_w = WIDTH - MARGIN["left"] - MARGIN["right"]
    plot_h = HEIGHT - MARGIN["top"] - MARGIN["bottom"]
    totals = [sum(values) for values in zip(*stacks.values(), strict=True)]
    hi = max(totals) * 1.1

    def py(v):
        return MARGIN["top"] + plot_h - v / hi * plot_h

    body = []
    for k in range(6):
        t = hi * k / 5
        y = py(t)
        body.append(f'<line x1="{MARGIN["left"]}" x2="{MARGIN["left"] + plot_w}" y1="{y}" y2="{y}" stroke="#e5e9ef"/>')
        body.append(f'<text x="{MARGIN["left"] - 8}" y="{y + 4}" text-anchor="end" fill="#52606d">{_fmt(t)}</text>')
    slot = plot_w / len(categories)
    bar_w = slot * 0.55
    for j, category in enumerate(categories):
        x = MARGIN["left"] + j * slot + (slot - bar_w) / 2
        base = 0.0
        for i, values in enumerate(stacks.values()):
            v = values[j]
            body.append(
                f'<rect x="{x:.1f}" y="{py(base + v):.1f}" width="{bar_w:.1f}" '
                f'height="{py(base) - py(base + v):.1f}" fill="{COLORS[i % len(COLORS)]}"/>'
            )
            base += v
        body.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{py(base) - 6:.1f}" text-anchor="middle" fill="#1f2933">'
            f"{_fmt(base)}</text>"
        )
        body.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{MARGIN["top"] + plot_h + 20}" text-anchor="middle" '
            f'fill="#52606d">{escape(category)}</text>'
        )
    body += _legend(list(stacks))
    return _frame(title, x_label, y_label, body)
