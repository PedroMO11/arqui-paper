"""Curva g(d): niveles distintos dentro de la vista del cliente que cambian en d mensajes.

Se mide sobre la grabación real recorriendo el libro una vez. En puntos de control
cada STEP mensajes se cuenta, para varios d, cuántos niveles de la banda visible
(definida igual que en relaybook.Relay._band) cambiaron en los últimos d mensajes.
"""

import numpy as np

from data import DEPTH, Book

D_VALUES = np.array([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000])
STEP = 100


def compute(msgs, snap):
    book = Book(snap)
    last = {k: -1 for k in book.qty}
    rows = []
    for i, m in enumerate(msgs):
        book.apply(m)
        for side in ("b", "a"):
            for p, _ in m[side]:
                last[(side, p)] = i
        if i >= D_VALUES.max() and i % STEP == 0:
            view = book.top(DEPTH)
            bid_floor = min(float(p) for (s, p) in view if s == "b")
            ask_ceiling = max(float(p) for (s, p) in view if s == "a")
            keys = list(last.keys())
            side = np.array([k[0] == "b" for k in keys])
            price = np.array([float(k[1]) for k in keys])
            idx = np.array([last[k] for k in keys])
            in_band = np.where(side, price >= bid_floor, price <= ask_ceiling)
            idx = idx[in_band]
            rows.append([(idx > i - d).sum() for d in D_VALUES])
    if not rows:
        raise ValueError("la grabación es demasiado corta para medir g(d)")
    g = np.array(rows).mean(axis=0)
    return np.concatenate(([0], D_VALUES)), np.concatenate(([0.0], g))
