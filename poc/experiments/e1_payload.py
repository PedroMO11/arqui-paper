"""Experimento 1: payload y correctness del state-based resume sobre datos reales.

Recorre la grabación con un relay real. En puntos aleatorios desconecta a un
cliente durante d mensajes y lo reconecta con los tres contratos:
  snapshot (Binance), log-based resume (estilo Ably) y state-based resume (RelayBook).
Mide los bytes de cada recuperación y verifica que el libro del cliente quede
idéntico al del relay (checksum de los 10 mejores niveles e igualdad del top 100).

    python poc/experiments/e1_payload.py
"""

import json
import random
import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))

from data import Book, aligned_messages, load_messages, load_snapshot  # noqa: E402
from relaybook import Client, Relay, checksum  # noqa: E402

RESULTS = ROOT / "results"
DURATIONS = [10, 30, 50, 100, 300, 600]   # mensajes perdidos; 10 mensajes = 1 s a ritmo normal
TRIALS = 8


def top_n(qty, n=100):
    bids = sorted(((float(p), p) for (s, p), q in qty.items() if s == "b" and float(q) > 0), reverse=True)[:n]
    asks = sorted((float(p), p) for (s, p), q in qty.items() if s == "a" and float(q) > 0)[:n]
    return [(p, qty[("b", p)]) for _, p in bids], [(p, qty[("a", p)]) for _, p in asks]


def main():
    snap = load_snapshot()
    msgs = aligned_messages(load_messages(), snap)
    rng = random.Random(7)
    max_d = max(DURATIONS)
    # Puntos de desconexión ordenados, para recorrer la grabación una sola vez por duración
    rows, checks = [], 0
    ok = 0
    for d in DURATIONS:
        starts = sorted(rng.sample(range(50, len(msgs) - max_d - 1), TRIALS))
        relay = Relay(snap)
        client = Client(snap)
        i = 0
        for a in starts:
            if a < i or a + d > len(msgs):    # sin solapar desconexiones ni pasar el final
                continue
            while i < a:                      # cliente conectado: recibe el stream
                relay.apply(msgs[i])
                client.apply(msgs[i])
                i += 1
            s_c = client.seq
            log_bytes = sum(m["bytes"] for m in msgs[i:i + d])
            for m in msgs[i:i + d]:            # cliente desconectado: solo el relay avanza
                relay.apply(m)
            i += d
            kind, levels, size = relay.resume(s_c)
            client.apply_resume(kind, levels, relay.S)
            same = checksum(client.qty) == checksum(relay.book.qty) and top_n(client.qty) == top_n(relay.book.qty)
            checks += 1
            ok += same
            rows.append({"missed_messages": d, "seconds_at_1x": d / 10, "snapshot_bytes": snap["bytes"],
                         "log_bytes": log_bytes, "state_bytes": size, "state_kind": kind, "correct": same})
            # El cliente sigue desde donde quedó el relay
    summary = {}
    for d in DURATIONS:
        rs = [r for r in rows if r["missed_messages"] == d]
        if not rs:
            continue
        summary[d] = {k: sum(r[k] for r in rs) / len(rs) for k in ("snapshot_bytes", "log_bytes", "state_bytes")}
        summary[d]["full_snapshot_share"] = sum(r["state_kind"] == "snapshot" for r in rs) / len(rs)
    RESULTS.mkdir(exist_ok=True)
    out = {"messages": len(msgs), "trials": checks, "correct": ok, "summary": summary, "rows": rows}
    (RESULTS / "e1_payload.json").write_text(json.dumps(out, indent=1))

    print(f"{len(msgs)} mensajes, {checks} reconexiones, libros correctos {ok}/{checks}")
    print(f"{'perdidos':>9} {'seg@1x':>7} {'snapshot':>9} {'log':>9} {'state':>9} {'state=snap':>10}")
    for d, s in summary.items():
        print(f"{d:9d} {d/10:7.0f} {s['snapshot_bytes']/1024:8.1f}K {s['log_bytes']/1024:8.1f}K "
              f"{s['state_bytes']/1024:8.1f}K {s['full_snapshot_share']:10.0%}")

    durations = [d for d in DURATIONS if d in summary]
    xs = [d / 10 for d in durations]
    fig, ax = plt.subplots(figsize=(3.5, 2.4), dpi=300)
    ax.plot(xs, [summary[d]["log_bytes"] / 1024 for d in durations], "o-", color="#c4461a", label="Log-based (Ably-style)", ms=3)
    ax.plot(xs, [summary[d]["snapshot_bytes"] / 1024 for d in durations], "s--", color="#1c5cab", label="Snapshot (Binance)", ms=3)
    ax.plot(xs, [summary[d]["state_bytes"] / 1024 for d in durations], "^-", color="#2b8a3e", label="State-based (RelayBook)", ms=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Disconnection at normal rate (s)", fontsize=7)
    ax.set_ylabel("Recovery payload (KB)", fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.grid(True, which="both", lw=0.3, alpha=0.5)
    ax.legend(fontsize=6, frameon=False)
    fig.tight_layout()
    fig.savefig(RESULTS / "e1_payload.png")
    print("escrito", RESULTS / "e1_payload.png")


if __name__ == "__main__":
    main()
