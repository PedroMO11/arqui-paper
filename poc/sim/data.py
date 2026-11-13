"""Carga la grabación del stream de Binance y reconstruye el libro.

La grabación puede estar en curso, por eso el .gz se lee con zlib y se descarta
la última línea si está incompleta.
"""

import json
import zlib
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Profundidad que entrega el snapshot REST (limit=1000), es decir, lo que ve un cliente
DEPTH = 1000


def load_messages(path=DATA / "depth.jsonl.gz"):
    raw = path.read_bytes()
    text = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw).decode("utf8", "ignore")
    msgs = []
    for line in text.split("\n"):
        line = line.strip()
        if line.endswith("}"):
            msgs.append(json.loads(line))
    for m in msgs:
        m["bytes"] = len(json.dumps({k: m[k] for k in m if k != "recv_ms"}, separators=(",", ":")))
    return msgs


def load_snapshot(path=DATA / "snapshot.json"):
    snap = json.loads(path.read_text())
    snap["bytes"] = len(json.dumps({k: snap[k] for k in ("lastUpdateId", "bids", "asks")}, separators=(",", ":")))
    return snap


def aligned_messages(msgs, snap):
    """Descarta los mensajes anteriores al snapshot y verifica la continuidad (pu == u previo)."""
    last = snap["lastUpdateId"]
    start = next(i for i, m in enumerate(msgs) if m["U"] <= last <= m["u"])
    out = msgs[start:]
    for prev, cur in zip(out, out[1:]):
        if cur["pu"] != prev["u"]:
            raise ValueError(f"hueco en la grabación entre u={prev['u']} y pu={cur['pu']}")
    return out


class Book:
    """Libro L2: (lado, precio) -> cantidad, con el número de secuencia del último cambio."""

    def __init__(self, snap=None):
        self.qty = {}
        self.seq = {}
        if snap:
            for side, key in (("b", "bids"), ("a", "asks")):
                for p, q in snap[key]:
                    self.qty[(side, p)] = q
                    self.seq[(side, p)] = snap["lastUpdateId"]

    def apply(self, msg):
        for side in ("b", "a"):
            for p, q in msg[side]:
                self.qty[(side, p)] = q
                self.seq[(side, p)] = msg["u"]

    def top(self, depth=DEPTH):
        """Niveles visibles para un cliente: los mejores `depth` precios por lado con cantidad > 0."""
        bids = sorted((float(p), p) for (s, p), q in self.qty.items() if s == "b" and float(q) > 0)[-depth:]
        asks = sorted((float(p), p) for (s, p), q in self.qty.items() if s == "a" and float(q) > 0)[:depth]
        return {("b", p): self.qty[("b", p)] for _, p in bids} | {("a", p): self.qty[("a", p)] for _, p in asks}
