# Propuesta de Mejora de la Disponibilidad del Market Data de Binance ante Reconnection Storms mediante la Arquitectura RelayBook con State‑Based Resume

Paper de Arquitectura de Software (Lab 13‑15). El título dice reconnection storms y no fallas metaestables, porque los reconnection storms están documentados y la metaestabilidad del contrato de Binance es lo que el paper demuestra por simulación. La hipótesis afirma propiedades que surgen de la estructura de RelayBook, con su mecanismo, y el POC las confirma o las refuta.

## Restricciones del enunciado (Lab 13‑15)

| Semana | Entregable | Implicancia para la idea |
|---|---|---|
| 13 | Requerimientos, usuario modelo, estudio, propuesta y estado del arte. Sin diseño. | Problema, brecha, propuesta y SOTA definidos mañana. |
| 14 | Arquitectura básica mejorada y métricas elegidas. | Las métricas salen directo de la hipótesis. |
| 15 | Paper en PDF con arquitectura escalada, tecnologías y data final. | Se necesita un POC con números reales. |

## Glosario mínimo

| Término | Significado |
|---|---|
| Order book | Lista de órdenes de compra y venta pendientes de un par, por ejemplo BTC/USDT. |
| Nivel de precio | Un precio del order book con la cantidad total de todas las órdenes en ese precio. |
| L1, L2, L3 | Niveles de detalle del market data. L1 es solo el mejor precio, L2 son todos los niveles de precio con su cantidad total, y L3 es cada orden individual. |
| Matching engine | Componente que cruza compras con ventas y genera trades. |
| Market data | Flujo en tiempo real de los cambios del order book hacia apps y bots. |
| Falla metaestable | Estado en que un sistema sigue caído después de que la causa inicial desapareció, porque un feedback loop interno lo mantiene saturado. |

---

## RelayBook

#### En una frase

El protocolo de market data que Binance documenta obliga a cada cliente desconectado a recuperar el libro completo, lo que en un pico puede dejar al sistema saturado por sus propias recuperaciones, y el paper propone una arquitectura de relays donde recuperar a un cliente cuesta solo los niveles de precio que cambiaron.

#### El problema en simple

1. En estado normal el servidor envía los cambios del order book y cada app mantiene su copia del libro al día.
2. Llega un trigger, por ejemplo un crash que multiplica por 10 los mensajes durante cinco minutos.
3. Las conexiones WebSocket de los clientes lentos se cortan (código 1006), y como el stream no reenvía lo perdido tras reconectar, su copia queda inválida y piden el libro completo por REST, que es la operación más cara del servidor.
4. El servidor, ocupado atendiendo esos pedidos, envía el stream más lento, por lo que más conexiones se cortan y más clientes piden el libro.
5. El crash termina, pero el servidor sigue saturado por los propios pedidos de recuperación. El sistema queda caído sin causa externa, y eso es una falla metaestable.

#### Evidencia y límites

Lo documentado por Binance:
1. El stream de depth no reenvía mensajes tras una reconexión, por lo que toda reconexión exige un snapshot REST, que es el endpoint con mayor weight en el rate limit.
2. Un 429 seguido de más requests produce un ban 418, y las IPs que se desconectan repetidamente pueden ser baneadas.

Lo reportado por usuarios en el foro oficial de desarrolladores:
1. Conexiones que se cortan con 1006 durante trading intenso.
2. Un usuario con unas 340 suscripciones de depth vio caer todas casi en el mismo instante, lo que indica desconexiones correlacionadas.

Tardis.dev, proveedor profesional de datos históricos, documenta que al detectar un mensaje perdido en el stream de Binance reinicia el WebSocket y reconstruye el libro con el snapshot REST.

Lo que no existe es un post‑mortem de Binance que atribuya un incidente a una tormenta de resync. Por lo tanto el paper no afirma que Binance cayó por esta causa, sino que su contrato público reúne las condiciones estructurales de una falla metaestable.

---

### Estado del arte

#### 1. Contexto

Los exchanges cripto distribuyen market data a millones de clientes retail y bots por WebSocket sobre internet pública, a diferencia de las bolsas tradicionales, que lo hacen por multicast en redes privadas. El market data tiene tres niveles de detalle:

| Nivel | Qué contiene | Ejemplo en Binance |
|---|---|---|
| L1 (top of book) | Solo el mejor precio de compra y de venta, con su cantidad | Stream `bookTicker` |
| L2 (market by price) | Todos los niveles de precio con la cantidad total en cada uno, sumando las órdenes de ese precio | Stream `depth`, usado en este paper |
| L3 (market by order) | Cada orden individual con su identificador | Binance no lo publica. Kraken y Hyperliquid ofrecen feeds por orden |

En L2 el exchange envía un snapshot inicial y luego deltas por nivel con la cantidad absoluta resultante, donde una cantidad 0 elimina el nivel. Cada delta trae números de secuencia, y si el cliente detecta un salto debe resincronizar. La forma de resincronizar define cuánto trabajo cae sobre el servidor cuando muchos clientes fallan a la vez, y ese trabajo es el que puede sostener una falla metaestable, entendida como un estado degradado que persiste después de que desaparece el trigger porque el trabajo de recuperación consume la capacidad que evitaría nuevas fallas.

#### 2. Keywords

En inglés, para Google Scholar y arXiv:
- market data dissemination, limit order book, L2 incremental updates, order book resynchronization
- snapshot recovery, sequence gap recovery, state‑based resume, conflation
- metastable failures, retry storm, reconnection storm, overload control
- WebSocket fan‑out, edge relay, cloud‑hosted financial exchange

En español: distribución de market data, libro de órdenes, resincronización, fallas metaestables, tormenta de reconexión.

#### 3. Literatura relacionada (2023‑2026)

| Trabajo | Año y venue | Qué hace | En qué se parece | En qué se diferencia |
|---|---|---|---|---|
| Onyx / Jasper, Haseeb et al. (arXiv 2402.09527) | 2024‑2025 | Overlay multicast en árbol de proxies en la nube para el market data de un exchange, unos 250 µs hacia cerca de 1 000 participantes | Es la arquitectura más parecida, un árbol de relays entre el exchange y los clientes | Optimiza la entrega simultánea a market makers, no la recuperación de clientes desconectados |
| DBO, Gupta et al. | SIGCOMM 2023 | Ordenamiento basado en la entrega para dar equidad en exchanges en la nube | Market data de exchanges en la nube | Resuelve equidad, no recuperación |
| Cuttlefish, Yu et al. | AFT 2025 | Entorno de ejecución justo y predecible para exchanges en la nube | Liberación simultánea de market data | Se enfoca en ejecución, no en distribución a clientes retail |
| Isaacs, Alvaro et al. | HotOS 2025 | Simulación para encontrar modos metaestables antes de que ocurran | Analiza el mismo tipo de falla | Estudia servicios genéricos, no market data, y se usa aquí como método |
| Farahbakhsh, Haeberlen et al. | HotNets 2025 | Modelo general de metaestabilidad para storage replicado | Define formalmente la falla | No trata distribución de estado a clientes |
| Formal Analysis of Metastable Failures (arXiv 2510.03551) | 2025 | Cadenas de Markov para predecir tiempos de recuperación | Herramienta para analizar el protocolo | No propone arquitectura |
| Characterizing Metastable Faults and Failures (arXiv 2606.00942) | 2026 | Distingue fault y failure metaestable con el retry storm como caso central | Argumenta que el problema está en cómo se programa el trabajo de recuperación | No trata market data |
| RetryGuard (arXiv 2511.23278) | 2025 | Previene retry storms en aplicaciones cloud | Ataca el mismo loop de reintentos | Es una táctica que protege al servidor, y en market data deja al cliente con el libro inválido |
| Rajomon | NSDI 2025 | Overload control descentralizado para microservicios | Control de sobrecarga | Descarta requests, no reduce el costo de recuperar |

#### 4. Estado de la práctica (documentación vigente)

| Enfoque | Quién lo usa | Costo de recuperar a un cliente | Qué pasa en un pico |
|---|---|---|---|
| Snapshot por REST tras reconectar | Binance | Un libro completo, pedido al origen | Crece con los desconectados y choca con rate limit y bans |
| Snapshot por WebSocket al suscribirse | Kraken WebSocket v2 (con checksum CRC32), Hyperliquid L4 | Un libro completo por el mismo canal | Elimina el REST, pero cada reconexión sigue costando un libro completo |
| Resume por sequence number | Ably, con ventana de 2 minutos | Los mensajes perdidos | Con 10x mensajes la ventana cubre menos tiempo y más clientes caen a resync completo |
| Snapshot cíclico en canal separado | CME MDP 3.0, Market Recovery feed | Esperar el siguiente ciclo | Funciona sobre multicast en redes privadas, no sobre WebSocket por internet |

#### 5. Brecha

La literatura de 2023 a 2026 sobre exchanges en la nube optimiza la equidad de entrega hacia market makers, y la de metastable failures propone tácticas que protegen al servidor descartando trabajo. En la práctica, todos los enfoques sobre WebSocket recuperan a un cliente con un libro completo o con los mensajes perdidos, dos costos que crecen justo en un pico. No apareció ningún trabajo que acote el costo de recuperación por los niveles que cambiaron en lugar de por los mensajes, ni uno que analice la recuperación de market data con el marco de metastable failures. Antes de cerrar la idea falta revisar OKX, Bybit y Coinbase, y buscar en Google Scholar con las keywords anteriores.

---

#### Arquitectura propuesta: RelayBook

```
REFERENCIA · contrato público de Binance
Matching ──► Publisher ──► WebSocket deltas ──► Cliente
                                                  │ reconexión
                                                  ▼
                              REST /depth snapshot (rate limit, 429, ban)
   La recuperación sube al origen, y su costo crece con los clientes desconectados.

PROPUESTA · RelayBook, relays con state‑based resume
                 ┌─────────────── Origen ────────────────┐
                 │ Matching ──► Feed secuenciado         │
                 │              deltas + snapshot cíclico │  tasa fija, no depende de N
                 └──────────────────┬────────────────────┘
                     ┌──────────────┼──────────────┐
                Relay Lima     Relay São Paulo   Relay ...     libro local y, por nivel,
                     │                                         seq de su último cambio
                     │ conflation por cliente lento
                     ▼
                 Clientes ── reconexión con último seq ──► relay: solo niveles cambiados desde ese seq
   El tráfico de recuperación nunca sube al origen.
```

| Decisión de arquitectura | Qué hace | Fundamento |
|---|---|---|
| Separar el camino de distribución del de recuperación | El origen emite un feed de tasa fija y la recuperación ocurre en los relays | arXiv 2606.00942 (2026), que ubica el problema en el trabajo de recuperación que compite con el camino principal |
| Tier de relays como overlay sobre unicast | Cada región tiene un relay con su réplica del libro | Onyx / Jasper (2024‑2025) y DBO (SIGCOMM 2023), overlays en la nube para exchanges |
| State‑based resume (pieza nueva) | El relay guarda por nivel el seq de su último cambio, y un cliente que vuelve recibe solo los niveles modificados desde su último seq, con su valor actual | La cantidad absoluta por nivel que documenta Binance hace que el valor actual reemplace a todos los cambios intermedios |
| Conflation por cliente lento | Si la cola de un cliente crece, el relay fusiona los deltas pendientes y envía el último valor por nivel, por lo que la conexión no se corta | La misma propiedad de cantidad absoluta por nivel. CME opera un feed conflated para BrokerTec |
| Snapshot cíclico en el feed | Cubre a los relays o clientes que vuelven sin seq válido | Market Recovery feed de CME MDP 3.0 |

#### Hipótesis

La hipótesis tiene dos partes. La primera es que el contrato público de Binance, simulado con su tráfico real reproducido a 10x, permanece degradado después de retirar el pico, lo que demuestra que puede entrar en una falla metaestable. La segunda es que RelayBook no tiene estado metaestable. Bajo un pico de 10x mensajes con desconexiones correlacionadas cumple tres propiedades:
1. La carga del origen se mantiene constante sin importar cuántos clientes se desconecten.
2. El costo de recuperar a un cliente está acotado por el número de niveles distintos que cambiaron durante su desconexión, que nunca supera la profundidad del libro, y no depende de la tasa de mensajes.
3. Al retirar el pico, el sistema vuelve al estado sano en un tiempo acotado y sin intervención manual.

Mecanismo. Una falla metaestable necesita que el trabajo de recuperación compita por la capacidad que evita nuevas fallas. En la propuesta ese trabajo nunca llega al origen, y en el relay su costo no crece con la tasa de mensajes, porque muchos cambios sobre el mismo nivel se reducen a un solo valor. En el log‑based resume, en cambio, el costo es proporcional a los mensajes perdidos, que se multiplican en el pico y empujan a los clientes fuera de la ventana de recuperación. La conflation evita además que un cliente lento llegue a desconectarse, lo que elimina el trigger.

Sustento de cada propiedad:

| Propiedad | Se sustenta en |
|---|---|
| 1. Carga del origen constante | Onyx / Jasper (2024‑2025) y DBO (2023) muestran que un overlay de proxies reparte la distribución en la nube sin multicast. arXiv 2606.00942 (2026) ubica la causa de la metaestabilidad en el trabajo de recuperación que compite con el camino principal |
| 2. Recuperación acotada por niveles | Contrato documentado de Binance con cantidad absoluta por nivel. La medición empírica de mensajes frente a niveles distintos del Entregable I cuantifica el ahorro |
| 3. Retorno sin intervención | Isaacs, Alvaro et al. (HotOS 2025) y Farahbakhsh et al. (HotNets 2025) caracterizan la metaestabilidad por la existencia de un loop de sostenimiento, ausente en la propuesta. arXiv 2510.03551 (2025) permite estimar el tiempo de recuperación |

Refutación. La hipótesis cae si la carga del origen crece con los clientes desconectados, si el costo de recuperación crece con la tasa de mensajes, si los relays se saturan con las reconexiones de su región, o si durante el pico el log‑based resume no degrada a resync completo, porque entonces la pieza nueva no aportaría.

#### Cómo se demuestra

Las tres propiedades se derivan primero de forma analítica y luego se verifican con un POC (origen, 3 relays y miles de clientes WebSocket sintéticos con distintas velocidades de red). El experimento aplica un pico con desconexiones correlacionadas, lo retira y mide cada métrica. Como líneas de referencia del estado de la práctica se reproducen tres contratos públicos (snapshot por REST de Binance, snapshot por WebSocket de Kraken y log‑based resume estilo Ably).

#### Datos para el POC

| Fuente | Contenido | Costo |
|---|---|---|
| WebSocket público de Binance, stream `@depth@100ms` | Cambios L2 reales por nivel de precio, grabables en vivo sin cuenta | Gratis |
| Tardis.dev, `incremental_book_L2` | Histórico de los mismos cambios | Primer día de cada mes gratis, el resto de pago |
| data.binance.vision | Trades y `bookTicker` históricos, sin cambios completos del libro | Gratis |

El tráfico es real, grabado y reproducido a 1x, 5x y 10x, y lo simulado son los clientes, sus redes y las desconexiones. Como primera medición para el Entregable I se graba el stream real y se calcula la razón entre mensajes recibidos y niveles distintos modificados por ventana de tiempo, que es el factor de ahorro del state‑based resume.

#### Métricas de éxito

Los umbrales son una propuesta inicial y se fijan en el Entregable II.

| Métrica | Cómo se mide | Criterio de éxito |
|---|---|---|
| Carga del origen frente a clientes desconectados | Mensajes por segundo y CPU del origen con 0 %, 10 %, 30 % y 50 % de desconectados | Variación menor a 5 % |
| Resyncs completos por reconexión | Porcentaje de reconexiones que terminan en libro completo durante el pico | Cercano a 0 %, frente al log‑based resume que debería subir con la tasa |
| Bytes por recuperación frente a la tasa | Tamaño de la respuesta de resume con 1x, 5x y 10x mensajes | Constante o decreciente con la tasa |
| Tiempo hasta el estado sano | Desde que termina el pico hasta que 99 % de los clientes tiene libro válido | Acotado y sin intervención manual |
| Staleness p99 durante el pico | Diferencia entre el precio que ve el cliente y el del origen | Menor a 1 s |
| Capacidad por relay | Clientes por relay antes de saturarse | Valor medido que define el dimensionamiento |

#### Plan por semana

| Semana | Entregable |
|---|---|
| 13 | Requerimientos, usuario modelo (trader retail en móvil, market maker, operador), estudio del contrato de Binance con la medición de mensajes frente a niveles, y estado del arte |
| 14 | Arquitectura propuesta con sus decisiones, derivación de las tres propiedades, métricas y escenario de pico |
| 15 | POC, gráficas de recuperación, dimensionamiento de relays y paper |

---

## ¿Dónde está la arquitectura?

El aporte del paper son decisiones de arquitectura y no un algoritmo. Cada propiedad de la hipótesis sale de la estructura del sistema.

| Elemento | En RelayBook |
|---|---|
| Estilo | Publish‑subscribe jerárquico basado en push, en lugar del request‑response del contrato de Binance para recuperar |
| Componentes y responsabilidades | Origen (matching y feed secuenciado), relays regionales (réplica del libro, recuperación y conflation) y clientes |
| Conectores | Feed de tasa fija del origen a los relays, WebSocket de los relays a los clientes y un protocolo de resume por sequence number |
| Ubicación del estado | El libro se replica en cada relay, junto con el seq del último cambio de cada nivel, y deja de vivir solo en el origen |
| Separación de caminos | La distribución y la recuperación usan caminos distintos, por lo que la recuperación nunca compite con el origen |
| Contrato de interfaz | El cliente que vuelve envía su último seq y recibe solo los niveles cambiados, que es el state‑based resume |
| Atributos de calidad | Disponibilidad bajo picos, escalabilidad en número de clientes y frescura del dato (staleness) |
| Tácticas | Replicación de estado, colas acotadas con conflation, eliminación de contención en el origen y degradación controlada por cliente lento |

#### Trade‑offs

| Se gana | Se paga |
|---|---|
| Carga del origen independiente de los clientes desconectados | Infraestructura y operación de los relays |
| Recuperación acotada por niveles de precio | Memoria en el relay para guardar el seq de cada nivel |
| Clientes lentos que no se desconectan | Un cliente lento con conflation ve menos actualizaciones intermedias |
| Recuperación local | Consistencia eventual entre el origen y cada relay |

## Fuentes

- Enunciado: Arqui2026.12- Lab 13-15.docx
- Regla aplicada: literatura de 2023 a 2026, más documentación vigente de sistemas en producción (Binance, Kraken, Ably, Hyperliquid, CME).
- Metaestabilidad: [Isaacs, Alvaro et al., HotOS 2025](https://sigops.org/s/conferences/hotos/2025/papers/hotos25-106.pdf), [Farahbakhsh, Haeberlen et al., HotNets 2025](https://haeberlen.cis.upenn.edu/papers/metastability-hotnets2025.pdf), [arXiv 2510.03551](https://arxiv.org/abs/2510.03551), [arXiv 2606.00942](https://arxiv.org/abs/2606.00942), [RetryGuard, arXiv 2511.23278](https://arxiv.org/abs/2511.23278), Rajomon NSDI 2025
- Exchanges en la nube: [DBO, SIGCOMM 2023](https://www.microsoft.com/en-us/research/publication/dbo-fairness-for-cloud-hosted-financial-exchanges/), [Onyx / Jasper, arXiv 2402.09527](https://arxiv.org/abs/2402.09527), [Cuttlefish, AFT 2025](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.AFT.2025.33)
- Market data Binance: [How to manage a local order book correctly](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly), [Binance WebSocket Market Streams, límites y bans](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Connect), [Foro, 1006 durante trading intenso](https://dev.binance.vision/t/websocket-keeps-disconnecting-with-1006-error-during-heavy-trading/35472), [Foro, depth websockets cerrándose juntos](https://dev.binance.vision/t/depth-websockets-keep-closing-1006-but-not-clientside/2428), [Foro, reconexión del order book local](https://dev.binance.vision/t/local-orderbook-binance-spot-websocket-disconnection/22050)
- Estado de la práctica: [Kraken, reconexión WebSocket](https://docs.kraken.com/exchange/guides/websockets/reconnection), [Kraken, book v2 y checksum](https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/book), [Ably, connection state y recovery](https://ably.com/docs/connect/states), [Hyperliquid L4 book](https://www.quicknode.com/docs/hyperliquid/datasets/l4-book), [CME MDP 3.0 Recovery Services](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457325847/MDP+3.0+-+Recovery+Services), [CME conflated feed BrokerTec](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457672459/MDP+3.0+-+MBP+and+MBOLD+Market+Recovery+for+the+Conflated+UDP+Market+Data+Group+for+BrokerTec)
- Datos: [Tardis.dev, Binance Spot](https://docs.tardis.dev/historical-data-details/binance), [Tardis.dev, CSV descargables](https://docs.tardis.dev/downloadable-csv-files)
