"""Draw the demo's threshold chart as an SVG in the portfolio's Field Guide colors.

    python scripts/chart.py            reads reports/results.json, writes docs/threshold_chart.svg
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INK, INK2, GREEN, RULE = "#1b1a17", "#57544c", "#24513c", "rgba(27,26,23,.14)"
FONT = "'Red Hat Mono', ui-monospace, Menlo, monospace"


def main():
    r = json.loads((ROOT / "reports/results.json").read_text())
    rows = r["sweep"]
    target = r["costs"]["target_accuracy"] * 100
    W, H, L, R, T, B = 720, 400, 56, 72, 20, 92
    pw, ph = W - L - R, H - T - B
    xs = [s["threshold"] for s in rows]
    x0, x1 = 0.0, 1.0
    costs = [s["cost_per_1k"] for s in rows]
    c0, c1 = 600, max(1300, max(costs))

    def X(v):
        return L + (v - x0) / (x1 - x0) * pw

    def Y(p):
        return T + ph - p / 100 * ph

    def YC(c):
        return T + ph - (c - c0) / (c1 - c0) * ph

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="Share routed automatically, accuracy on those, and cost per 1,000 tickets by confidence threshold" '
           f'font-family="{FONT}" font-size="12" fill="{INK2}">']
    for p in range(0, 101, 20):
        out.append(f'<line x1="{L}" x2="{L + pw}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="{RULE}"/>')
        out.append(f'<text x="{L - 10}" y="{Y(p) + 4:.1f}" text-anchor="end">{p}%</text>')
    for c in range(c0, int(c1) + 1, 200):
        out.append(f'<text x="{L + pw + 10}" y="{YC(c) + 4:.1f}">${c:,}</text>')
    for t in (0, 0.2, 0.4, 0.6, 0.8, 1.0):
        out.append(f'<text x="{X(t):.1f}" y="{T + ph + 22}" text-anchor="middle">{t:.1f}</text>')
    out.append(f'<text x="{L + pw / 2}" y="{T + ph + 44}" text-anchor="middle">Confidence threshold</text>')
    out.append(f'<line x1="{L}" x2="{L + pw}" y1="{T + ph}" y2="{T + ph}" stroke="{INK}"/>')
    out.append(f'<line x1="{L}" x2="{L + pw}" y1="{Y(target):.1f}" y2="{Y(target):.1f}" stroke="{GREEN}" stroke-dasharray="2 4"/>')
    out.append(f'<text x="{L + pw - 4}" y="{Y(target) + 16:.1f}" fill="{GREEN}" text-anchor="end">{target:.0f}% accuracy target</text>')

    def line(pts, color, dash="", width=2):
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>' for x, y in pts)
        return f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{da}/>{dots}'

    out.append(line([(X(x), Y(s["auto_share"] * 100)) for x, s in zip(xs, rows)], INK))
    out.append(line([(X(x), Y(s["auto_accuracy"] * 100)) for x, s in zip(xs, rows) if s["auto_share"]], GREEN))
    out.append(line([(X(x), YC(c)) for x, c in zip(xs, costs)], INK2, "5 4", 1.5))
    lx, ly = L, H - 16
    for label, color, dash in (("Routed automatically", INK, ""), ("Accuracy on those", GREEN, ""),
                               ("Cost per 1,000 tickets (right axis)", INK2, "5 4")):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<line x1="{lx}" x2="{lx + 22}" y1="{ly - 4}" y2="{ly - 4}" stroke="{color}" stroke-width="2"{da}/>')
        out.append(f'<text x="{lx + 30}" y="{ly}" fill="{INK}">{label}</text>')
        lx += 30 + len(label) * 7.3 + 24
    out.append("</svg>")
    (ROOT / "docs/threshold_chart.svg").write_text("".join(out) + "\n")
    print("wrote docs/threshold_chart.svg")


if __name__ == "__main__":
    main()
