"""Graba el stream público de profundidad L2 de Binance USD-M Futures.

Escribe en poc/data/:
  snapshot.json      snapshot REST inicial (lastUpdateId, bids, asks)
  depth.jsonl.gz     un mensaje del stream por línea, con la hora local de recepción

    python poc/recorder/record_depth.py --minutes 70
"""

import argparse
import asyncio
import gzip
import json
import time
from pathlib import Path

import requests
import websockets

DATA = Path(__file__).resolve().parent.parent / "data"
WS_URL = "wss://fstream.binance.com/ws/{symbol}@depth@100ms"
REST_URL = "https://fapi.binance.com/fapi/v1/depth?symbol={symbol}&limit=1000"


async def record(symbol, minutes):
    DATA.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + minutes * 60
    count, reconnects = 0, 0
    with gzip.open(DATA / "depth.jsonl.gz", "wt", encoding="utf8") as out:
        snapshot_taken = False
        while time.time() < deadline:
            try:
                async with websockets.connect(WS_URL.format(symbol=symbol.lower()), ping_interval=60, close_timeout=1) as ws:
                    if not snapshot_taken:
                        # El snapshot se pide con el stream ya abierto, como indica Binance
                        await asyncio.sleep(1)
                        snap = requests.get(REST_URL.format(symbol=symbol.upper()), timeout=10).json()
                        snap["recv_ms"] = int(time.time() * 1000)
                        (DATA / "snapshot.json").write_text(json.dumps(snap))
                        snapshot_taken = True
                    while time.time() < deadline:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        msg = json.loads(raw)
                        msg["recv_ms"] = int(time.time() * 1000)
                        out.write(json.dumps(msg, separators=(",", ":")) + "\n")
                        count += 1
                        if count % 3000 == 0:
                            left = (deadline - time.time()) / 60
                            print(f"{count} mensajes, faltan {left:.1f} min", flush=True)
            except Exception as exc:  # una reconexión deja un hueco que el replay detecta por pu/u
                reconnects += 1
                print(f"reconexión {reconnects}: {exc!r}", flush=True)
                await asyncio.sleep(2)
    print(f"listo: {count} mensajes, {reconnects} reconexiones", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--minutes", type=float, default=70)
    args = parser.parse_args()
    asyncio.run(record(args.symbol, args.minutes))


if __name__ == "__main__":
    main()
