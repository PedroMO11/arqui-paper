"""Experimento 2: tormenta de reconexiones para Binance, estilo Ably y RelayBook.

Reproduce la grabación real en tres fases (5 min a 1x, 5 min a 10x con 30% de
clientes desconectados al inicio, 10 min a 1x) y barre la capacidad de los
servidores en múltiplos de la carga del stream a ritmo normal.

    python poc/experiments/e2_storm.py            # escenario completo (requiere ~65 min de grabación)
    python poc/experiments/e2_storm.py --quick    # escenario reducido para probar
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))

import gcurve  # noqa: E402
from data import aligned_messages, load_messages, load_snapshot  # noqa: E402
from storm import Scenario, run, summarize  # noqa: E402

RESULTS = ROOT / "results"
DESIGNS = ["binance", "ably", "relaybook"]
COLORS = {"binance": "#1c5cab", "ably": "#c4461a", "relaybook": "#2b8a3e"}
LABELS = {"binance": "Binance contract", "ably": "Ably-style resume", "relaybook": "RelayBook"}
HEADROOMS = [1.5, 2, 3, 5, 10, 15]
SNAPSHOT_COSTS = [1.0, 10.0, 50.0]   # costo de un snapshot REST en el origen, en múltiplos de sus bytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--clients", type=int, default=2000)
    args = parser.parse_args()

    snap = load_snapshot()
    msgs = aligned_messages(load_messages(), snap)
    msg_bytes = np.array([m["bytes"] for m in msgs], dtype=float)
    RESULTS.mkdir(exist_ok=True)

    g = gcurve.compute(msgs, snap)
    (RESULTS / "g_curve.json").write_text(json.dumps({"d": g[0].tolist(), "levels": g[1].tolist()}))
    print("g(d):", {int(d): round(v) for d, v in zip(*g)})

    base = dict(clients=args.clients)
    if args.quick:
        base.update(pre=300, spike=300, post=900)
    rows, traces = [], {}
    runs = [(h, d, 1.0) for h in HEADROOMS for d in DESIGNS]
    runs += [(h, "binance", c) for c in SNAPSHOT_COSTS[1:] for h in HEADROOMS]
    for h, design, cost in runs:
            sc = Scenario(headroom=h, snapshot_cost=cost, **base)
            tr = run(design, sc, msg_bytes, g, snap["bytes"])
            s = summarize(tr, sc)
            s["snapshot_cost"] = cost
            rows.append(s)
            traces[(design, h, cost)] = tr.valid
            ttr = "never" if s["time_to_recover_s"] is None else f"{s['time_to_recover_s']:.1f}s"
            print(f"h={h:<4} cost={cost:<4} {design:<10} full_resync={s['full_resync_ratio']:6.1%} ttr={ttr:>7} "
                  f"stale_p99={s['staleness_p99_s']:7.1f}s valid_end={s['valid_end']:6.1%} "
                  f"origin={s['origin_mb_per_s_post']:7.1f}MB/s rec={s['mean_recovery_kb']:7.1f}KB wasted={s['wasted_rest_mb']:7.1f}MB",
                  flush=True)

    tag = "_quick" if args.quick else ""
    sc = Scenario(**base)
    (RESULTS / f"e2_storm{tag}.json").write_text(json.dumps({"scenario": sc.__dict__, "rows": rows}, indent=1))

    np.savez_compressed(RESULTS / f"e2_traces{tag}.npz",
                        **{f"{d}_{h}_{c}": v for (d, h, c), v in traces.items()})

    # Figura 1: libros válidos en el tiempo, promedio por segundo
    def per_second(v):
        n = len(v) // 10
        return v[: n * 10].reshape(n, 10).mean(axis=1)

    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.3), dpi=300)
    t = np.arange(sc.ticks // 10) / 60
    for ax, h in zip(axes, (3, 10)):
        for d in DESIGNS:
            ax.plot(t, per_second(traces[(d, h, 1.0)]) * 100, color=COLORS[d], lw=0.8, label=LABELS[d])
        ax.plot(t, per_second(traces[("binance", h, SNAPSHOT_COSTS[-1])]) * 100, color=COLORS["binance"], lw=0.8, ls="--",
                label=f"Binance, snapshot cost {SNAPSHOT_COSTS[-1]:.0f}x")
        ax.axvspan(sc.pre * 0.1 / 60, (sc.pre + sc.spike) * 0.1 / 60, color="#999", alpha=0.15, lw=0)
        ax.set_title(f"Server capacity {h}x the normal stream load", fontsize=7.5)
        ax.set_xlabel("Time (min)", fontsize=7)
        ax.set_ylabel("Clients with a valid book (%)", fontsize=7)
        ax.set_ylim(-3, 103)
        ax.tick_params(labelsize=6.5)
        ax.grid(True, lw=0.3, alpha=0.5)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(RESULTS / f"e2_valid{tag}.png")

    # Figura 2: tiempo de recuperación según la capacidad
    fig, ax = plt.subplots(figsize=(3.5, 2.3), dpi=300)
    limit = sc.post * 0.1
    series = [(d, 1.0, "-", LABELS[d]) for d in DESIGNS]
    series += [("binance", c, ls, f"Binance, snapshot cost {c:.0f}x") for c, ls in zip(SNAPSHOT_COSTS[1:], ("--", ":"))]
    for d, cost, ls, label in series:
        ys = [r["time_to_recover_s"] if r["time_to_recover_s"] is not None else limit
              for r in rows if r["design"] == d and r["snapshot_cost"] == cost]
        ax.plot(HEADROOMS, ys, "o", color=COLORS[d], label=label, ms=3, lw=1, ls=ls)
    ax.axhline(limit, color="#666", lw=0.6, ls=":")
    ax.text(HEADROOMS[0], limit, "no recovery in the window", fontsize=6, ha="left", va="bottom", color="#666")
    ax.set_xscale("log")
    ax.set_xticks(HEADROOMS)
    ax.set_xticklabels([str(h) for h in HEADROOMS])
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.xaxis.set_minor_locator(plt.NullLocator())
    ax.set_xlabel("Server capacity / normal stream load", fontsize=7)
    ax.set_ylabel("Time to recover (s)", fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.grid(True, lw=0.3, alpha=0.5)
    ax.set_ylim(-5, limit * 1.12)
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=5.8, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.2, 1, 1))
    fig.savefig(RESULTS / f"e2_ttr{tag}.png")
    print("figuras en", RESULTS)


if __name__ == "__main__":
    main()
