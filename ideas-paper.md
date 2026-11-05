# Ideas de paper · Arquitectura de Software

Eje común: arquitectura de exchanges (Binance, Hyperliquid). Cada idea parte de una línea de investigación publicada, identifica qué parte no está resuelta para un exchange y propone una arquitectura que la resuelve. La hipótesis afirma propiedades que surgen de la estructura de la arquitectura propuesta, con su mecanismo, y el POC las confirma o las refuta. El diseño actual aparece solo como línea de referencia.

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
| Leverage y liquidación | Operar con dinero prestado. Si las pérdidas agotan el dinero propio, el exchange cierra la posición a la fuerza. |
| ADL (auto‑deleveraging) | Último recurso cuando una liquidación deja pérdidas que el fondo de seguro no cubre. El exchange cierra a la fuerza parte de las posiciones ganadoras para cubrir el hueco. |
| Falla metaestable | Estado en que un sistema sigue caído después de que la causa inicial desapareció, porque un feedback loop interno lo mantiene saturado. |

---

## Idea 1 · Market data de Binance con recuperación por estado (idea principal)

#### Título propuesto

Propuesta de Mejora de la Recuperación del Market Data de Binance ante Picos de Volatilidad mediante Relays con Resume por Estado

Alternativa más corta: Resume por Estado, una Arquitectura de Market Data sin Tormentas de Reconexión. El Caso de Binance.

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
| Resume por número de secuencia | Ably, con ventana de 2 minutos | Los mensajes perdidos | Con 10x mensajes la ventana cubre menos tiempo y más clientes caen a resync completo |
| Snapshot cíclico en canal separado | CME MDP 3.0, Market Recovery feed | Esperar el siguiente ciclo | Funciona sobre multicast en redes privadas, no sobre WebSocket por internet |

#### 5. Brecha

La literatura de 2023 a 2026 sobre exchanges en la nube optimiza la equidad de entrega hacia market makers, y la de metastable failures propone tácticas que protegen al servidor descartando trabajo. En la práctica, todos los enfoques sobre WebSocket recuperan a un cliente con un libro completo o con los mensajes perdidos, dos costos que crecen justo en un pico. No apareció ningún trabajo que acote el costo de recuperación por los niveles que cambiaron en lugar de por los mensajes, ni uno que analice la recuperación de market data con el marco de metastable failures. Antes de cerrar la idea falta revisar OKX, Bybit y Coinbase, y buscar en Google Scholar con las keywords anteriores.

---

#### Arquitectura propuesta

```
REFERENCIA · contrato público de Binance
Matching ──► Publisher ──► WebSocket deltas ──► Cliente
                                                  │ reconexión
                                                  ▼
                              REST /depth snapshot (rate limit, 429, ban)
   La recuperación sube al origen, y su costo crece con los clientes desconectados.

PROPUESTA · relays con resume por estado
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
| Resume por estado (pieza nueva) | El relay guarda por nivel el seq de su último cambio, y un cliente que vuelve recibe solo los niveles modificados desde su último seq, con su valor actual | La cantidad absoluta por nivel que documenta Binance hace que el valor actual reemplace a todos los cambios intermedios |
| Conflation por cliente lento | Si la cola de un cliente crece, el relay fusiona los deltas pendientes y envía el último valor por nivel, por lo que la conexión no se corta | La misma propiedad de cantidad absoluta por nivel. CME opera un feed conflated para BrokerTec |
| Snapshot cíclico en el feed | Cubre a los relays o clientes que vuelven sin seq válido | Market Recovery feed de CME MDP 3.0 |

#### Hipótesis

La arquitectura con relays y resume por estado no tiene estado metaestable. Bajo un pico de 10x mensajes con desconexiones correlacionadas cumple tres propiedades:
1. La carga del origen se mantiene constante sin importar cuántos clientes se desconecten.
2. El costo de recuperar a un cliente está acotado por el número de niveles distintos que cambiaron durante su desconexión, que nunca supera la profundidad del libro, y no depende de la tasa de mensajes.
3. Al retirar el pico, el sistema vuelve al estado sano en un tiempo acotado y sin intervención manual.

Mecanismo. Una falla metaestable necesita que el trabajo de recuperación compita por la capacidad que evita nuevas fallas. En la propuesta ese trabajo nunca llega al origen, y en el relay su costo no crece con la tasa de mensajes, porque muchos cambios sobre el mismo nivel se reducen a un solo valor. En el resume por log, en cambio, el costo es proporcional a los mensajes perdidos, que se multiplican en el pico y empujan a los clientes fuera de la ventana de recuperación. La conflation evita además que un cliente lento llegue a desconectarse, lo que elimina el trigger.

Sustento de cada propiedad:

| Propiedad | Se sustenta en |
|---|---|
| 1. Carga del origen constante | Onyx / Jasper (2024‑2025) y DBO (2023) muestran que un overlay de proxies reparte la distribución en la nube sin multicast. arXiv 2606.00942 (2026) ubica la causa de la metaestabilidad en el trabajo de recuperación que compite con el camino principal |
| 2. Recuperación acotada por niveles | Contrato documentado de Binance con cantidad absoluta por nivel. La medición empírica de mensajes frente a niveles distintos del Entregable I cuantifica el ahorro |
| 3. Retorno sin intervención | Isaacs, Alvaro et al. (HotOS 2025) y Farahbakhsh et al. (HotNets 2025) caracterizan la metaestabilidad por la existencia de un loop de sostenimiento, ausente en la propuesta. arXiv 2510.03551 (2025) permite estimar el tiempo de recuperación |

Refutación. La hipótesis cae si la carga del origen crece con los clientes desconectados, si el costo de recuperación crece con la tasa de mensajes, si los relays se saturan con las reconexiones de su región, o si durante el pico el resume por log no degrada a resync completo, porque entonces la pieza nueva no aportaría.

#### Cómo se demuestra

Las tres propiedades se derivan primero de forma analítica y luego se verifican con un POC (origen, 3 relays y miles de clientes WebSocket sintéticos con distintas velocidades de red). El experimento aplica un pico con desconexiones correlacionadas, lo retira y mide cada métrica. Como líneas de referencia del estado de la práctica se reproducen tres contratos públicos (snapshot por REST de Binance, snapshot por WebSocket de Kraken y resume por log estilo Ably).

#### Datos para el POC

| Fuente | Contenido | Costo |
|---|---|---|
| WebSocket público de Binance, stream `@depth@100ms` | Cambios L2 reales por nivel de precio, grabables en vivo sin cuenta | Gratis |
| Tardis.dev, `incremental_book_L2` | Histórico de los mismos cambios | Primer día de cada mes gratis, el resto de pago |
| data.binance.vision | Trades y `bookTicker` históricos, sin cambios completos del libro | Gratis |

El tráfico es real, grabado y reproducido a 1x, 5x y 10x, y lo simulado son los clientes, sus redes y las desconexiones. Como primera medición para el Entregable I se graba el stream real y se calcula la razón entre mensajes recibidos y niveles distintos modificados por ventana de tiempo, que es el factor de ahorro del resume por estado.

#### Métricas de éxito

Los umbrales son una propuesta inicial y se fijan en el Entregable II.

| Métrica | Cómo se mide | Criterio de éxito |
|---|---|---|
| Carga del origen frente a clientes desconectados | Mensajes por segundo y CPU del origen con 0 %, 10 %, 30 % y 50 % de desconectados | Variación menor a 5 % |
| Resyncs completos por reconexión | Porcentaje de reconexiones que terminan en libro completo durante el pico | Cercano a 0 %, frente al resume por log que debería subir con la tasa |
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

## Idea 2 · Risk engine event‑sourced para ADL en plena cascada

#### En una frase

Papers de 2025 y 2026 muestran que el ADL usado el 10/10/2025 cerró de más a los traders ganadores y proponen algoritmos mejores, y este paper propone la arquitectura de risk engine que permite ejecutarlos en tiempo real durante una cascada.

#### El problema en simple

1. Cuando una liquidación deja pérdidas que el fondo de seguro no cubre, el exchange cierra a la fuerza parte de las posiciones ganadoras para cubrir el hueco. Eso es el ADL.
2. Elegir bien a quién cerrar exige mirar todas las posiciones abiertas en ese instante.
3. En una cascada hay miles de déficits por minuto, por lo que el exchange usa una regla simple y barata de calcular, una cola ordenada por ganancia y leverage.
4. Esa regla cierra más de lo necesario. Los algoritmos mejores existen, pero son caros de calcular en el momento.

#### Base académica

arXiv 2512.01112 (2025) analiza el evento en Hyperliquid y estima que el algoritmo de producción quitó entre 45 y 51,7 millones de USD de más a los traders ganadores. arXiv 2602.15182 (2026) modela el ADL como online learning y reporta un regret cercano a 50 % para producción frente a 2,6 % para el optimizado. arXiv 2603.15963 (2026) propone una asignación basada en riesgo sobre unos 2 mil millones de USD de ADL concentrados en minutos. En arquitectura, arXiv 2606.01183 (2026) y arXiv 2309.04259 (2023) describen matching engines con sequencer y journal de eventos como fuente única de verdad, y DBSP (Budiu et al., VLDB 2023) formaliza el mantenimiento incremental de vistas sobre streams de cambios.

#### Brecha

Los papers de ADL evalúan los algoritmos offline sobre datos históricos y no tratan cómo obtener, en el instante del déficit, una vista global y consistente de todas las posiciones sin frenar el matching.

#### Arquitectura propuesta

```
REFERENCIA · cálculo en el momento
Matching ──► Risk engine ──► déficit ──► recorre todas las posiciones ──► cola de ADL

PROPUESTA · risk engine event‑sourced con proyección incremental
Matching ──► Journal secuenciado ──┬──► (hot path sigue sin esperar)
                                   │
                                   ▼
                          Position projector  ── fold determinista sobre el journal
                                   │
                                   ▼
                    Vista de riesgo indexada por la clave del algoritmo, versión = seq N
                                   │ consulta en el déficit
                                   ▼
                    ADL engine ──► decisión firmada con el seq N ──► Matching
```

| Decisión de arquitectura | Qué hace | Fundamento |
|---|---|---|
| Journal del matching como fuente única de verdad | Todo cambio de posición es un evento secuenciado | arXiv 2606.01183 (2026) y arXiv 2309.04259 (2023), sequencer con journal |
| Proyección de riesgo separada del write path | El projector consume el journal de forma asíncrona, fuera del critical path del matching | CQRS con event sourcing, en la variante snapshot‑centric de Hruzin y Lytvynov (2026) |
| Índice mantenido incrementalmente | Cada trade actualiza el índice en O(log n), por lo que en el déficit solo se consulta | Incremental view maintenance, DBSP (VLDB 2023) |
| Decisión versionada por número de secuencia | Cada decisión de ADL declara sobre qué prefijo del journal se calculó | Determinismo de state machine replication, base de trabajos recientes como Chora (arXiv 2507.12792, 2025) |

#### Hipótesis

El risk engine event‑sourced ejecuta un algoritmo de ADL optimizado durante una cascada con tres propiedades:
1. La latencia de decisión de ADL no depende del número de posiciones abiertas.
2. La latencia p99 del matching no cambia al activar el projector.
3. Toda decisión de ADL es reproducible exactamente desde el journal, por lo que es auditable.

Mecanismo. La vista es una función determinista del prefijo del journal, así que mantenerla con cada trade reparte el costo en el tiempo y la consulta en el déficit cuesta O(k log n) para k posiciones cerradas. El projector lee el journal sin bloquear al matching, y la reproducibilidad sale de versionar cada decisión con el número de secuencia.

Sustento de cada propiedad:

| Propiedad | Se sustenta en |
|---|---|
| 1. Latencia independiente del número de posiciones | DBSP (Budiu et al., VLDB 2023) muestra que el mantenimiento incremental de una vista cuesta en proporción al cambio y no al tamaño de los datos |
| 2. Matching sin impacto | En los diseños de arXiv 2309.04259 (2023) y arXiv 2606.01183 (2026) los consumidores del journal leen sin bloquear al sequencer. CQRS separa el modelo de escritura del de lectura |
| 3. Decisión reproducible | En state machine replication el mismo prefijo del log produce el mismo estado, propiedad sobre la que se construye Chora (arXiv 2507.12792, 2025). |

La necesidad de un ADL mejor la establecen arXiv 2512.01112, 2602.15182 y 2603.15963.

Refutación. La hipótesis cae si durante la cascada el projector no alcanza la tasa de eventos y su lag crece sin límite, ya que la vista se volvería un componente saturado. Ese punto define la capacidad del projector.

#### Cómo se demuestra

Replay de los fills públicos de Hyperliquid del 10/10/2025 a 1x y 10x de velocidad. Se mide latencia de decisión frente al número de posiciones, lag del projector, latencia p99 del matching con y sin projector, y se verifica que reproducir el journal da las mismas decisiones. El exceso en USD se reporta como resultado secundario, porque depende del algoritmo de los papers.

#### Métricas de éxito

| Métrica | Cómo se mide | Criterio de éxito |
|---|---|---|
| Latencia de decisión de ADL | p99 por déficit con 10 mil, 100 mil y 1 millón de posiciones | Crecimiento logarítmico, sin saltos proporcionales a n |
| Impacto en el matching | Latencia p99 del matching con y sin projector | Diferencia menor a 5 % |
| Lag del projector | Eventos pendientes durante el replay a 10x | Acotado durante toda la cascada |
| Reproducibilidad | Decisiones al reproducir el journal frente a las originales | 100 % idénticas |

---

## Idea 3 · Exchange particionado con escrow de saldos

#### En una frase

Un exchange escala dividiendo los pares en particiones, pero el saldo de un usuario es uno solo y se usa en todos los pares, y el paper propone una arquitectura con escrow donde cada partición valida órdenes sin coordinarse con las demás.

#### El problema en simple

1. Para escalar, cada par (BTC/USDT, ETH/USDT) vive en su propia partición con su propio hilo.
2. Antes de aceptar una orden hay que verificar que el usuario tenga saldo.
3. El saldo es uno solo para todos los pares, así que la partición de BTC tiene que consultar o bloquear un saldo que también usa la partición de ETH.
4. Esa consulta es una transacción distribuida en casi toda orden, y es lo que más frena a este tipo de sistemas.

#### Base académica

Lotus (Zhou, Yu, Graefe y Stonebraker, VLDB 2022) revisa la arquitectura de un hilo por partición de H‑Store y VoltDB y muestra que es imbatible cuando cada transacción toca una sola partición, pero que rinde muy mal con transacciones multi‑partición. arXiv 2606.01183 (2026) usa la misma estructura para matching, un libro por core. La ECOOP 2025 (Ensuring Convergence and Invariants Without Coordination) señala que mantener invariantes en sistemas replicados exige coordinación o tiene aplicabilidad limitada. El benchmark de SoftwareMill (2025) muestra que la contención en hot accounts degrada a PostgreSQL, y TigerBeetle implementa reservas de saldo como transferencias pendientes en dos fases. Fugue (VLDB 2025) estudia la migración en vivo de particiones con estado y encuentra que mover la partición más caliente es el caso más costoso.

#### Brecha

En un exchange el matching se particiona por par y el saldo por usuario, así que las dos claves de partición no coinciden. Lotus mejora las transacciones multi‑partición pero asume una sola clave, y los trabajos de invariantes sin coordinación no consideran la demanda concentrada de un listing, que agota las reservas de una partición en segundos.

#### Arquitectura propuesta

```
REFERENCIA · saldo central
Gateway ──► Partición BTC ──► 2PC ──► Servicio de saldos ◄── 2PC ◄── Partición ETH

PROPUESTA · particiones por par con escrow de saldos
                          Balance service (saldo global)
                         ▲ transferencia de reservas, asíncrona y guiada por demanda
           ┌─────────────┼──────────────┐
Gateway ─► Partición BTC   Partición ETH   Partición del listing
           sequencer        sequencer       migración en vivo pre‑copy    
           book + reservas  book + reservas reservas asignadas según demanda
   Una orden se valida contra la reserva local, sin salir de la partición.
```

| Decisión de arquitectura | Qué hace | Fundamento |
|---|---|---|
| Partición por par con un sequencer por partición | Cada libro se procesa en un hilo sin locks | Lotus (VLDB 2022) y arXiv 2606.01183 (2026) |
| Saldo como escrow | El saldo del usuario se reparte en reservas por partición, cuya suma nunca supera el saldo | Transferencias pendientes en dos fases de TigerBeetle (documentación vigente) y ECOOP 2025 |
| Transferencia de reservas guiada por demanda | Las reservas se mueven hacia las particiones donde el usuario opera más | Diseño propio guiado por la demanda observada, evaluado en el POC |
| Migración en vivo de pares calientes | Un par con demanda extrema se mueve a su propia partición sin detener el trading | Fugue (VLDB 2025), migración en vivo por pre‑copy iterativa |

#### Hipótesis

La arquitectura con escrow cumple tres propiedades:
1. Una orden se admite sin coordinación entre particiones mientras la reserva local alcance, por lo que el throughput de cada partición no depende del porcentaje de usuarios que operan en varios pares.
2. El costo de coordinación es proporcional a la frecuencia de transferencias de reservas y no al número de órdenes.
3. El invariante saldo ≥ 0 se cumple siempre, incluso durante transferencias y migraciones.

Mecanismo. El invariante de saldo exige coordinación, como recuerda la ECOOP 2025, y el escrow la concentra en la transferencia de reservas, que ocurre solo cuando una reserva se agota. La propiedad 3 sale de que la suma de reservas nunca supera el saldo global, condición que la transferencia preserva por construcción.

Sustento de cada propiedad:

| Propiedad | Se sustenta en |
|---|---|
| 1. Admisión sin coordinación | Lotus (VLDB 2022) muestra que en un diseño de un hilo por partición las transacciones locales son las rápidas y las multi‑partición las lentas, por lo que volver locales las órdenes es la palanca principal. Las transferencias pendientes de TigerBeetle permiten reservar saldo sin bloquear el total |
| 2. Coordinación solo por transferencia | La ECOOP 2025 busca mantener invariantes evitando coordinación, y aquí la coordinación queda reducida a las transferencias de reservas |
| 3. Saldo nunca negativo | Según la ECOOP 2025 este tipo de invariante requiere coordinación, que aquí se concentra en la transferencia, manteniendo la suma de reservas menor o igual al saldo |

Refutación. La hipótesis cae si, durante un listing, las transferencias de reservas se vuelven tan frecuentes como las órdenes, porque la coordinación volvería a ser por orden. Ese punto define el límite de concentración que la arquitectura soporta.

#### Cómo se demuestra

Mini exchange con 8 particiones. Se varía el porcentaje de usuarios multi‑par y se simula un listing con demanda concentrada. Se mide throughput por partición, latencia p99, transferencias de reservas por segundo y órdenes rechazadas por reserva insuficiente, y un checker verifica el invariante de saldo en cada paso. El diseño con saldo central se usa solo como línea de referencia.

#### Métricas de éxito

| Métrica | Cómo se mide | Criterio de éxito |
|---|---|---|
| Throughput por partición | Órdenes por segundo con 0 %, 25 %, 50 % y 75 % de usuarios multi‑par | Variación menor a 10 % |
| Coordinación por orden | Transferencias de reservas divididas entre órdenes aceptadas | Menor a 1 % fuera del listing |
| Violaciones del invariante | Saldos negativos detectados por el checker | 0 |
| Rechazos por reserva insuficiente | Porcentaje de órdenes rechazadas con saldo total suficiente | Medido y reportado como costo del diseño |
| Pausa de migración | Tiempo sin aceptar órdenes al mover el par caliente | Proporcional al journal pendiente, no al tamaño del libro |

---

## Comparación

| | Idea 1 | Idea 2 | Idea 3 |
|---|---|---|---|
| Línea académica | Metastable failures y exchanges en la nube | Auto‑deleveraging | Partitioned in‑memory DB y escrow |
| Contribución | Arquitectura de distribución que no puede entrar en estado metaestable | Risk engine event‑sourced que ejecuta ADL optimizado en tiempo real | Arquitectura que concilia dos claves de partición con escrow |
| Data | Simulación | Fills reales de Hyperliquid | Simulación |
| Riesgo | Dimensionar los relays | Entender el algoritmo de los papers | Implementar escrow y migración en 12 h |

## Decisión arquitectónica y trade‑off de cada idea

| | Decisión que cambia | Atributo que se gana | Lo que se paga |
|---|---|---|---|
| Idea 1 | Comunicación de pull a push, y un tier de edge relays con estado replicado | Disponibilidad bajo picos, ya que el costo de recuperación deja de depender de los clientes que fallan | Staleness para clientes lentos por conflation y costo de infraestructura de los relays |
| Idea 2 | El cálculo de riesgo sale del hot path y pasa a una vista materializada por CQRS | Latencia del ADL dentro del presupuesto del risk engine | Consistencia eventual, ya que la vista puede ir milisegundos detrás del matching |
| Idea 3 | El saldo pasa de un servicio central a reservas por partición, con coordinación por rebalanceo y no por orden | Throughput y escalabilidad horizontal | Rechazos por reserva insuficiente aunque el saldo total alcance |


## Fuentes

- Enunciado: Arqui2026.12- Lab 13-15.docx
- Regla aplicada: literatura de 2023 a 2026, más documentación vigente de sistemas en producción (Binance, Kraken, Ably, Hyperliquid, CME, TigerBeetle). Lotus (VLDB 2022) en la Idea 3 queda en el límite de 4 años.
- Metaestabilidad: [Isaacs, Alvaro et al., HotOS 2025](https://sigops.org/s/conferences/hotos/2025/papers/hotos25-106.pdf), [Farahbakhsh, Haeberlen et al., HotNets 2025](https://haeberlen.cis.upenn.edu/papers/metastability-hotnets2025.pdf), [arXiv 2510.03551](https://arxiv.org/abs/2510.03551), [arXiv 2606.00942](https://arxiv.org/abs/2606.00942), [RetryGuard, arXiv 2511.23278](https://arxiv.org/abs/2511.23278), Rajomon NSDI 2025
- Exchanges en la nube: [DBO, SIGCOMM 2023](https://www.microsoft.com/en-us/research/publication/dbo-fairness-for-cloud-hosted-financial-exchanges/), [Onyx / Jasper, arXiv 2402.09527](https://arxiv.org/abs/2402.09527), [Cuttlefish, AFT 2025](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.AFT.2025.33)
- Market data Binance: [How to manage a local order book correctly](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly), [Binance WebSocket Market Streams, límites y bans](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Connect), [Foro, 1006 durante trading intenso](https://dev.binance.vision/t/websocket-keeps-disconnecting-with-1006-error-during-heavy-trading/35472), [Foro, depth websockets cerrándose juntos](https://dev.binance.vision/t/depth-websockets-keep-closing-1006-but-not-clientside/2428), [Foro, reconexión del order book local](https://dev.binance.vision/t/local-orderbook-binance-spot-websocket-disconnection/22050)
- Estado de la práctica: [Kraken, reconexión WebSocket](https://docs.kraken.com/exchange/guides/websockets/reconnection), [Kraken, book v2 y checksum](https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/book), [Ably, connection state y recovery](https://ably.com/docs/connect/states), [Hyperliquid L4 book](https://www.quicknode.com/docs/hyperliquid/datasets/l4-book), [CME MDP 3.0 Recovery Services](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457325847/MDP+3.0+-+Recovery+Services), [CME conflated feed BrokerTec](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457672459/MDP+3.0+-+MBP+and+MBOLD+Market+Recovery+for+the+Conflated+UDP+Market+Data+Group+for+BrokerTec)
- Datos: [Tardis.dev, Binance Spot](https://docs.tardis.dev/historical-data-details/binance), [Tardis.dev, CSV descargables](https://docs.tardis.dev/downloadable-csv-files)
- ADL y risk engine: [arXiv 2512.01112](https://arxiv.org/abs/2512.01112), [arXiv 2602.15182](https://arxiv.org/abs/2602.15182), [arXiv 2603.15963](https://arxiv.org/abs/2603.15963), [DBSP, VLDB 2023](https://www.vldb.org/pvldb/vol16/p1601-budiu.pdf), [Hruzin y Lytvynov 2026](https://scinews.kpi.ua/article/view/350992), [Chora, arXiv 2507.12792](https://arxiv.org/abs/2507.12792), [arXiv 2309.04259](https://arxiv.org/abs/2309.04259), [arXiv 2606.01183](https://arxiv.org/abs/2606.01183)
- Particionado y escrow: [Lotus, VLDB 2022](https://www.vldb.org/pvldb/vol15/p2939-zhou.pdf), [Fugue, VLDB 2025](https://www.vldb.org/pvldb/vol19/p3288-zhang.pdf), [ECOOP 2025, Ensuring Convergence and Invariants Without Coordination](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2025.4), [TigerBeetle docs](https://docs.tigerbeetle.com/), [SoftwareMill, TigerBeetle vs PostgreSQL](https://softwaremill.com/tigetbeetle-vs-postgresql-performance-benchmark-harness-cloud-tests)
