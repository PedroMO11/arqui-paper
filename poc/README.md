# POC de RelayBook

Prototipo y experimentos del paper. Todo corre con Python 3.13, numpy y matplotlib; el grabador usa `websockets`.

```
pip install numpy matplotlib requests websockets
```

## 1. Grabar el stream real de Binance

```
python poc/recorder/record_depth.py --minutes 70
```

Se suscribe al stream público `btcusdt@depth@100ms` de Binance USD-M Futures, toma un snapshot REST de 1000 niveles por lado y guarda cada mensaje en `poc/data/depth.jsonl.gz` (no se sube al repo). El escenario completo consume unos 65 minutos de grabación.

## 2. Experimento 1, payload y correctness con datos reales

```
python poc/experiments/e1_payload.py
```

Recorre la grabación con el relay real (`poc/sim/relaybook.py`), desconecta clientes en puntos aleatorios y los recupera con los tres contratos. Mide los bytes de cada recuperación y verifica que el libro del cliente quede idéntico al del relay. Resultados en `poc/results/e1_payload.json` y `e1_payload.png`.

## 3. Experimento 2, tormenta de reconexiones

```
python poc/experiments/e2_storm.py           # escenario completo
python poc/experiments/e2_storm.py --quick   # escenario reducido para probar
```

Simulación de 20 minutos con 2000 clientes que reproduce la grabación en tres fases (1x, 10x con 30% de clientes desconectados al inicio, 1x). Barre la capacidad de los servidores y, para Binance, el costo de generar un snapshot. Resultados en `poc/results/e2_storm.json`, `e2_valid.png` y `e2_ttr.png`.

## Archivos

| Archivo | Contenido |
|---|---|
| `recorder/record_depth.py` | Grabador del stream |
| `sim/data.py` | Carga de la grabación y libro L2 |
| `sim/relaybook.py` | Relay con state-based resume, tombstones y checksum |
| `sim/gcurve.py` | Niveles distintos que cambian según los mensajes perdidos, medido sobre la grabación |
| `sim/storm.py` | Simulador de capacidad, desconexiones y recuperación para los tres diseños |

## Supuestos del simulador

- La recuperación comparte la capacidad de envío del servidor con el stream.
- Un servidor cierra la conexión de un cliente cuyo buffer de salida supera 1 MB (Binance y estilo Ably). RelayBook aplica conflation desde 256 KB.
- Un cliente reconecta si su libro tiene más de 5 s de antigüedad, y reintenta una recuperación que no llega en 10 s.
- En Binance, un pedido REST abandonado se sigue procesando en el origen.
- 30% de los clientes tiene una bajada de 80 KB/s y el resto de 2 MB/s.
