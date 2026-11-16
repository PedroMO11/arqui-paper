"""Lógica del relay de RelayBook: state-based resume con tombstones y checksum.

El relay replica el libro del origen aplicando el feed en orden. Para cada nivel
guarda la cantidad y el número de secuencia de su último cambio, incluso cuando
la cantidad es 0 (tombstone), de modo que un cliente que vuelve también se
entera de los niveles que desaparecieron.
"""

import zlib

from data import DEPTH, Book

LEVEL_BYTES = 20      # tamaño medio de un nivel ["precio","cantidad"] medido en el stream
HEADER_BYTES = 60     # campos fijos de un mensaje (tipo, símbolo, U, u)


def checksum(qty, n=10):
    """CRC32 sobre los n mejores niveles por lado, en el estilo del checksum de Kraken."""
    bids = sorted(((float(p), p) for (s, p), q in qty.items() if s == "b" and float(q) > 0), reverse=True)[:n]
    asks = sorted((float(p), p) for (s, p), q in qty.items() if s == "a" and float(q) > 0)[:n]
    text = "|".join(f"{p}:{qty[('a', p)]}" for _, p in asks) + "#" + "|".join(f"{p}:{qty[('b', p)]}" for _, p in bids)
    return zlib.crc32(text.encode())


class Relay:
    def __init__(self, snap):
        self.book = Book(snap)
        self.S = snap["lastUpdateId"]
        self.snapshot_bytes = snap["bytes"]

    def apply(self, msg):
        if msg["pu"] != self.S and self.S != msg["U"] - 1 and not (msg["U"] <= self.S <= msg["u"]):
            raise ValueError("hueco en el feed: el relay debe esperar el siguiente snapshot")
        self.book.apply(msg)
        self.S = msg["u"]

    def _band(self):
        """Rango de precios visible para un cliente: todo lo mejor que el nivel DEPTH de cada lado.

        La banda no se corta en el mejor precio actual, porque cuando el precio se mueve
        los niveles que quedan del otro lado se borran, y esos tombstones también deben
        llegar al cliente.
        """
        view = self.book.top(DEPTH)
        bids = [float(p) for (s, p) in view if s == "b"]
        asks = [float(p) for (s, p) in view if s == "a"]
        return {"b": (min(bids), float("inf")), "a": (float("-inf"), max(asks))}

    def resume(self, s_c):
        """Responde a un cliente cuyo último cambio aplicado es s_c (Algorithm 1)."""
        if s_c > self.S:
            raise ValueError("cliente adelantado: el relay debe esperar hasta S >= s_c")
        band = self._band()
        delta = {}
        for key, seq in self.book.seq.items():
            side, p = key
            if seq > s_c and band[side][0] <= float(p) <= band[side][1]:
                delta[key] = self.book.qty[key]
        size = HEADER_BYTES + LEVEL_BYTES * len(delta)
        if size >= self.snapshot_bytes:
            return "snapshot", self.book.top(DEPTH), self.snapshot_bytes
        return "delta", delta, size


class Client:
    def __init__(self, snap):
        self.qty = {}
        for side, key in (("b", "bids"), ("a", "asks")):
            for p, q in snap[key]:
                self.qty[(side, p)] = q
        self.seq = snap["lastUpdateId"]

    def apply(self, msg):
        for side in ("b", "a"):
            for p, q in msg[side]:
                self.qty[(side, p)] = q
        self.seq = msg["u"]

    def apply_resume(self, kind, levels, S):
        if kind == "snapshot":
            self.qty = dict(levels)
        else:
            self.qty.update(levels)
        self.seq = S
