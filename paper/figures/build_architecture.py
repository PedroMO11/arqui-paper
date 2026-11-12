"""Genera paper/figures/architecture.png, el diagrama del paper.

Panel (a): contrato público de Binance, donde la recuperación sube al origen.
Panel (b): RelayBook, donde la recuperación termina en el relay de cada región.

    python paper/figures/build_architecture.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "architecture.png"

INK = "#1e1e1e"
ORIGIN_FILL = "#d0e4fb"
RELAY_FILL = "#d3f1e5"
CLIENT_FILL = "#f1f0ec"
HOT_FILL = "#fde0d2"
DIST = "#1c5cab"
RECOVERY_BAD = "#c4461a"
RECOVERY_OK = "#2b8a3e"


def box(ax, x, y, w, h, text, fill, size=7.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=1.0, edgecolor=INK, facecolor=fill))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
            color=INK, fontweight="bold" if bold else "normal", linespacing=1.25)


def arrow(ax, start, end, color, dashed=False, rad=0.0, label=None, label_pos=0.5, label_off=(0, 0)):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=9,
                                 linewidth=1.1, color=color,
                                 linestyle=(0, (4, 2.5)) if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        lx = start[0] + (end[0] - start[0]) * label_pos + label_off[0]
        ly = start[1] + (end[1] - start[1]) * label_pos + label_off[1]
        ax.text(lx, ly, label, ha="center", va="center", fontsize=6.3, color=color,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6))


def setup(ax, title):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.4)
    ax.axis("off")
    ax.set_title(title, fontsize=8.5, color=INK, pad=4)


def panel_binance(ax):
    setup(ax, "(a) Public Binance contract")
    # Origen
    box(ax, 0.3, 4.7, 9.4, 2.3, "", ORIGIN_FILL)
    ax.text(0.5, 6.75, "Origin", fontsize=7.5, fontweight="bold", color=INK, va="center")
    box(ax, 0.8, 5.0, 2.4, 1.3, "Matching\nengine", "white")
    box(ax, 3.8, 5.0, 2.4, 1.3, "Depth stream\npublisher", "white")
    box(ax, 6.8, 5.0, 2.6, 1.3, "REST snapshot\nendpoint\n(rate limit, bans)", HOT_FILL, size=7)
    arrow(ax, (3.2, 5.65), (3.8, 5.65), DIST)

    # Clientes
    xs = [0.8, 3.7, 6.6]
    for i, x in enumerate(xs):
        box(ax, x, 0.6, 2.6, 1.2, f"Client {i + 1}\nlocal book", CLIENT_FILL)
        arrow(ax, (5.0, 5.0), (x + 1.0, 1.8), DIST)
        arrow(ax, (x + 2.0, 1.8), (8.1, 5.0), RECOVERY_BAD, dashed=True)
    ax.text(5.0, 0.15, "each reconnection requests a full book from the origin",
            ha="center", fontsize=6.3, color=RECOVERY_BAD)


def panel_relaybook(ax):
    setup(ax, "(b) RelayBook")
    # Origen
    box(ax, 0.3, 5.3, 9.4, 1.7, "", ORIGIN_FILL)
    ax.text(0.5, 6.75, "Origin", fontsize=7.5, fontweight="bold", color=INK, va="center")
    box(ax, 0.8, 5.5, 2.6, 0.95, "Matching engine", "white", size=7)
    box(ax, 4.0, 5.5, 5.4, 0.95, "Sequenced feed\ndeltas + periodic snapshot", "white", size=7)
    arrow(ax, (3.4, 5.97), (4.0, 5.97), DIST)

    # Relays
    relay_x = [0.4, 3.55, 6.7]
    names = ["Relay A", "Relay B", "Relay C"]
    for x, name in zip(relay_x, names):
        box(ax, x, 2.75, 2.9, 1.75, f"{name}\nbook replica\nseq per level\nconflation", RELAY_FILL, size=6.6)
        arrow(ax, (6.7, 5.5), (x + 1.45, 4.5), DIST)

    # Clientes de cada relay
    for x in relay_x:
        for j, dx in enumerate((0.0, 1.55)):
            cx = x + dx
            box(ax, cx, 0.5, 1.35, 0.9, "Client", CLIENT_FILL, size=6.6)
            arrow(ax, (x + 0.75 + dx * 0.9, 2.75), (cx + 0.45, 1.4), DIST)
            arrow(ax, (cx + 0.95, 1.4), (x + 1.2 + dx * 0.6, 2.75), RECOVERY_OK, dashed=True)
    ax.text(5.0, 0.15, "a reconnection resumes at the relay with the last seq",
            ha="center", fontsize=6.3, color=RECOVERY_OK)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 3.0), dpi=300)
    panel_binance(axes[0])
    panel_relaybook(axes[1])
    handles = [
        plt.Line2D([], [], color=DIST, lw=1.2, label="distribution"),
        plt.Line2D([], [], color=RECOVERY_BAD, lw=1.2, ls=(0, (4, 2.5)), label="recovery to the origin"),
        plt.Line2D([], [], color=RECOVERY_OK, lw=1.2, ls=(0, (4, 2.5)), label="recovery at the relay"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=6.5, frameon=False,
               bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(OUT, bbox_inches="tight")
    print(f"escrito {OUT}")


if __name__ == "__main__":
    main()
