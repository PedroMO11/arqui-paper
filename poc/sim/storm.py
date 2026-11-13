"""Simulador de la tormenta de reconexiones con tráfico real de Binance.

Tick de 100 ms. Cada tick el origen publica los mensajes grabados que le tocan
según la velocidad de la fase (1x o 10x). Los servidores tienen una capacidad de
envío en bytes por tick que se reparte entre los flujos con max-min fairness, y
cada cliente tiene una velocidad de bajada propia.

Diseños:
  binance    clientes conectados al origen; tras reconectar piden un snapshot REST
             al origen, con timeout y reintento sin cancelar el pedido anterior
  ably       relays regionales; el cliente retoma recibiendo todos los mensajes
             perdidos si no pasaron más de 2 minutos, y si no, un snapshot del relay
  relaybook  relays regionales con state-based resume y conflation para clientes lentos

Supuestos declarados en el paper: la recuperación comparte la capacidad de envío
con el stream, un servidor cierra la conexión de un cliente cuyo buffer de salida
supera QMAX bytes, y un cliente reconecta si pasa STALE_TIMEOUT sin recibir datos.
"""

from dataclasses import dataclass, field

import numpy as np

TICK = 0.1
STALE_TIMEOUT = 50        # ticks sin avanzar antes de que el cliente reconecte (5 s)
REQUEST_TIMEOUT = 100     # ticks de espera de una recuperación antes de reintentar (10 s)
RECONNECT_DELAY = 10      # ticks entre una desconexión y el siguiente intento (1 s)
QMAX = 1_000_000          # bytes de buffer de salida por conexión antes de cerrarla
QCONF = 256_000           # bytes de backlog a partir de los cuales RelayBook aplica conflation
ABLY_WINDOW = 1200        # ticks de la ventana de resume por log (2 min)
LEVEL_BYTES = 20
HEADER_BYTES = 60


@dataclass
class Scenario:
    pre: int = 3000           # ticks a 1x antes del pico (5 min)
    spike: int = 3000         # ticks a 10x (5 min)
    post: int = 6000          # ticks a 1x después del pico (10 min)
    speed: int = 10
    clients: int = 2000
    relays: int = 3
    slow_share: float = 0.3
    fast_rate: float = 200_000   # bytes por tick (2 MB/s)
    slow_rate: float = 8_000     # bytes por tick (80 KB/s)
    drop_share: float = 0.3      # clientes que caen juntos al inicio del pico
    headroom: float = 3.0        # capacidad del servidor / carga del stream a 1x
    snapshot_cost: float = 1.0   # costo de generar un snapshot REST en el origen, en múltiplos de sus bytes
    seed: int = 1

    @property
    def ticks(self):
        return self.pre + self.spike + self.post


def waterfill(caps, capacity):
    """Reparte `capacity` entre flujos con tope `caps` con max-min fairness."""
    total = caps.sum()
    if total <= capacity:
        return caps.copy()
    s = np.sort(caps)
    n = len(s)
    served = np.concatenate(([0.0], np.cumsum(s)[:-1]))
    lam = (capacity - served) / (n - np.arange(n))
    k = np.argmax(lam <= s)
    return np.minimum(caps, lam[k])


@dataclass
class Trace:
    design: str
    headroom: float
    valid: np.ndarray = None
    origin_bytes: np.ndarray = None
    staleness_samples: list = field(default_factory=list)
    reconnects_spike: int = 0
    full_spike: int = 0
    recovery_bytes: list = field(default_factory=list)
    wasted_bytes: float = 0.0


def run(design, sc, msg_bytes, g_curve, snapshot_bytes):
    rng = np.random.default_rng(sc.seed)
    N, T = sc.clients, sc.ticks

    # Mensajes publicados por tick
    speeds = np.concatenate([np.ones(sc.pre), np.full(sc.spike, sc.speed), np.ones(sc.post)]).astype(int)
    idx_end = np.cumsum(speeds)
    if idx_end[-1] > len(msg_bytes):
        raise ValueError(f"la grabación tiene {len(msg_bytes)} mensajes y el escenario necesita {idx_end[-1]}")
    CB = np.concatenate(([0.0], np.cumsum(msg_bytes[: idx_end[-1]])))
    pub_tick = np.repeat(np.arange(T), speeds)          # tick en que se publicó cada mensaje
    pub_tick = np.concatenate(([0], pub_tick))           # pos=0 -> tick 0

    s1 = msg_bytes[: sc.pre].mean()                      # bytes por tick a 1x
    rates = np.where(rng.random(N) < sc.slow_share, sc.slow_rate, sc.fast_rate)
    group = np.arange(N) % sc.relays if design != "binance" else np.zeros(N, int)
    servers = 1 if design == "binance" else sc.relays
    capacity = np.array([sc.headroom * s1 * (group == g).sum() for g in range(servers)])

    def state_payload(d):
        levels = np.interp(d, g_curve[0], g_curve[1])
        return np.minimum(snapshot_bytes, HEADER_BYTES + LEVEL_BYTES * levels)

    # Estado de cada cliente
    status = np.full(N, 2)          # 0 desconectado, 1 recuperando, 2 libro válido
    consumed = np.zeros(N)          # bytes del stream ya aplicados (define la posición)
    resp = np.zeros(N)              # bytes de la respuesta de recuperación pendiente en su conexión
    resp_pos = np.zeros(N)          # posición que alcanza el cliente al terminar esa respuesta
    resp_full = np.zeros(N, bool)
    since = np.zeros(N, int)        # tick del último avance o del inicio de la espera
    reconnect_at = np.zeros(N, int)
    stream_from = np.zeros(N)       # bytes del stream desde los que la conexión actual empieza a recibir
    req_id = np.zeros(N, int)
    # Pedidos REST pendientes en el origen (solo binance)
    rest_client = np.zeros(0, int)
    rest_id = np.zeros(0, int)
    rest_left = np.zeros(0)
    rest_issued = np.zeros(0, int)

    tr = Trace(design, sc.headroom, valid=np.zeros(T), origin_bytes=np.zeros(T))
    spike_start, spike_end = sc.pre, sc.pre + sc.spike

    def pos_of(c):
        return np.searchsorted(CB, c, side="right") - 1

    def disconnect(mask, t, delay=RECONNECT_DELAY):
        nonlocal status
        status[mask] = 0
        resp[mask] = 0
        reconnect_at[mask] = t + delay

    for t in range(T):
        now_idx = idx_end[t]
        now_bytes = CB[now_idx]

        if t == spike_start:
            drop = rng.random(N) < sc.drop_share
            disconnect(drop, t, delay=0)
            reconnect_at[drop] = t + rng.integers(10, 51, drop.sum())

        # Reconexiones
        rec = (status == 0) & (reconnect_at <= t)
        if rec.any():
            ids = np.flatnonzero(rec)
            if spike_start <= t < spike_end:
                tr.reconnects_spike += len(ids)
            status[ids] = 1
            since[ids] = t
            if design == "binance":
                stream_from[ids] = now_bytes           # el WebSocket empieza a recibir desde ahora
                req_id[ids] += 1
                rest_client = np.concatenate((rest_client, ids))
                rest_id = np.concatenate((rest_id, req_id[ids]))
                rest_left = np.concatenate((rest_left, np.full(len(ids), snapshot_bytes * sc.snapshot_cost)))
                rest_issued = np.concatenate((rest_issued, np.full(len(ids), t)))
                if spike_start <= t < spike_end:
                    tr.full_spike += len(ids)
                tr.recovery_bytes.extend([snapshot_bytes] * len(ids))
            else:
                last = pos_of(consumed[ids])
                missed = now_idx - last
                if design == "ably":
                    in_window = (t - pub_tick[last]) <= ABLY_WINDOW
                    size = np.where(in_window, CB[now_idx] - CB[last], snapshot_bytes)
                    full = ~in_window
                else:
                    size = state_payload(missed)
                    full = size >= snapshot_bytes
                resp[ids] = size
                resp_full[ids] = full
                resp_pos[ids] = now_bytes
                stream_from[ids] = now_bytes
                if spike_start <= t < spike_end:
                    tr.full_spike += int(full.sum())
                tr.recovery_bytes.extend(size.tolist())

        connected = status > 0
        # Backlog del stream: lo publicado que la conexión actual aún no entregó
        base = np.where(status == 2, consumed, np.maximum(consumed, stream_from))
        backlog = np.where(connected, now_bytes - base, 0.0)

        # Clientes lentos
        if design == "relaybook":
            conf = (status == 2) & (backlog > QCONF) & (resp == 0)
            if conf.any():
                ids = np.flatnonzero(conf)
                size = state_payload(now_idx - pos_of(consumed[ids]))
                resp[ids] = size
                resp_pos[ids] = now_bytes
                resp_full[ids] = False
                stream_from[ids] = now_bytes
                backlog[ids] = 0.0
                base[ids] = now_bytes
        else:
            over = connected & (backlog > QMAX)
            if over.any():
                disconnect(over, t)
                backlog[over] = 0.0
                connected = status > 0

        # Reparto de capacidad
        if design == "binance":
            caps_ws = np.where(connected, np.minimum(rates, backlog), 0.0)
            caps = np.concatenate((caps_ws, rest_left))
            alloc = waterfill(caps, capacity[0])
            a_ws, a_rest = alloc[:N], alloc[N:]
            tr.origin_bytes[t] = alloc.sum()
            rest_left = rest_left - a_rest
            done = rest_left <= 1e-6
            if done.any():
                dc, di = rest_client[done], rest_id[done]
                ok = (status[dc] == 1) & (req_id[dc] == di)
                tr.wasted_bytes += float(snapshot_bytes * sc.snapshot_cost * (~ok).sum())
                cl = dc[ok]
                # el snapshot deja el libro en la posición actual; el stream sigue desde ahí
                consumed[cl] = np.maximum(np.maximum(consumed[cl], stream_from[cl]), now_bytes)
                status[cl] = 2
                since[cl] = t
                rest_client, rest_id, rest_left, rest_issued = (rest_client[~done], rest_id[~done],
                                                                rest_left[~done], rest_issued[~done])
            # Avance del stream de cada conexión
            adv = connected & (a_ws > 0)
            moved = adv & (status == 2)
            consumed[moved] += a_ws[moved]
            waiting = adv & (status == 1)
            stream_from[waiting] += a_ws[waiting]       # el cliente bufferiza mientras espera el snapshot
            # Timeout del pedido REST: reintento sin cancelar el anterior
            retry = (status == 1) & (t - since >= REQUEST_TIMEOUT)
            if retry.any():
                ids = np.flatnonzero(retry)
                req_id[ids] += 1
                since[ids] = t
                rest_client = np.concatenate((rest_client, ids))
                rest_id = np.concatenate((rest_id, req_id[ids]))
                rest_left = np.concatenate((rest_left, np.full(len(ids), snapshot_bytes * sc.snapshot_cost)))
                rest_issued = np.concatenate((rest_issued, np.full(len(ids), t)))
        else:
            caps = np.where(connected, np.minimum(rates, resp + backlog), 0.0)
            alloc = np.zeros(N)
            for g in range(servers):
                m = group == g
                alloc[m] = waterfill(caps[m], capacity[g])
            # El origen solo alimenta a los relays: stream más un snapshot por segundo
            tr.origin_bytes[t] = servers * (now_bytes - CB[idx_end[t - 1]] if t else 0) + servers * snapshot_bytes / 10
            to_resp = np.minimum(alloc, resp)
            resp -= to_resp
            rest = alloc - to_resp
            finished = connected & (resp <= 1e-6) & (resp_pos > 0)
            if finished.any():
                consumed[finished] = np.maximum(consumed[finished], resp_pos[finished])
                status[finished & (status == 1)] = 2
                resp_pos[finished] = 0
                since[finished] = t
            moved = connected & (status == 2) & (resp <= 1e-6)
            consumed[moved] = np.minimum(consumed[moved] + rest[moved], now_bytes)
            # Timeout de la recuperación: el cliente reconecta y retoma de nuevo
            stuck = (status == 1) & (t - since >= REQUEST_TIMEOUT)
            if stuck.any():
                disconnect(stuck, t)

        consumed = np.minimum(consumed, now_bytes)
        # Timeout por falta de datos con el libro válido
        pos = pos_of(consumed)
        if t % 10 == 0:
            stale_ticks = t - pub_tick[pos]
            if spike_start <= t < spike_end:
                tr.staleness_samples.append(stale_ticks * TICK)
        progressed = (status == 2) & (now_bytes - consumed < 1) | (status == 2) & (pub_tick[pos] > t - STALE_TIMEOUT)
        since[progressed] = t
        dead = (status == 2) & (t - since >= STALE_TIMEOUT)
        if dead.any():
            disconnect(dead, t)
        tr.valid[t] = (status == 2).mean()
    return tr


def summarize(tr, sc):
    spike_end = sc.pre + sc.spike
    post = tr.valid[spike_end:]
    window = 100   # 10 s sostenidos
    ttr = None
    ok = post >= 0.99
    for i in range(len(post) - window):
        if ok[i:i + window].all():
            ttr = i * TICK
            break
    stale = np.concatenate(tr.staleness_samples) if tr.staleness_samples else np.array([0.0])
    return {
        "design": tr.design,
        "headroom": tr.headroom,
        "full_resync_ratio": tr.full_spike / tr.reconnects_spike if tr.reconnects_spike else 0.0,
        "reconnects_spike": tr.reconnects_spike,
        "time_to_recover_s": ttr,
        "staleness_p99_s": float(np.percentile(stale, 99)),
        "valid_end": float(tr.valid[-1]),
        "valid_min": float(tr.valid.min()),
        "mean_recovery_kb": float(np.mean(tr.recovery_bytes) / 1024) if tr.recovery_bytes else 0.0,
        "origin_mb_per_s_spike": float(tr.origin_bytes[sc.pre:spike_end].mean() / TICK / 1e6),
        "origin_mb_per_s_post": float(tr.origin_bytes[spike_end:].mean() / TICK / 1e6),
        "wasted_rest_mb": tr.wasted_bytes / 1e6,
    }
