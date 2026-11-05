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
| Matching engine | Componente que cruza compras con ventas y genera trades. |
| Market data | Flujo en tiempo real de los cambios del order book hacia apps y bots. |
| Leverage y liquidación | Operar con dinero prestado. Si las pérdidas agotan el dinero propio, el exchange cierra la posición a la fuerza. |
| ADL (auto‑deleveraging) | Último recurso cuando una liquidación deja pérdidas que el fondo de seguro no cubre. El exchange cierra a la fuerza parte de las posiciones ganadoras para cubrir el hueco. |
| Falla metaestable | Estado en que un sistema sigue caído después de que la causa inicial desapareció, porque un feedback loop interno lo mantiene saturado. |

---

## Idea 1 · Arquitectura de market data sin estado metaestable (idea principal)

#### En una frase

El protocolo de market data que Binance documenta reúne las condiciones de una falla metaestable, y el paper propone una arquitectura de distribución jerárquica por push con recuperación local que, por su estructura, no puede entrar en ese estado.

#### El problema en simple

1. En estado normal el servidor envía los cambios del order book y cada app mantiene su copia del libro al día.
2. Llega un trigger, por ejemplo un crash que multiplica por 10 los mensajes durante cinco minutos.
3. Las conexiones WebSocket de los clientes lentos se cortan (código 1006), y como el stream no reenvía lo perdido tras reconectar, su copia queda inválida y piden el libro completo por REST, que es la operación más cara del servidor.
4. El servidor, ocupado atendiendo esos pedidos, envía el stream más lento, por lo que más conexiones se cortan y más clientes piden el libro.
5. El crash termina, pero el servidor sigue saturado por los propios pedidos de recuperación. El sistema queda caído sin causa externa, y eso es una falla metaestable. Hoy se sale de ese estado con intervención manual, descartando carga o reiniciando.

#### Evidencia y límites

Lo documentado por Binance:
1. El stream de depth no reenvía mensajes tras una reconexión, por lo que toda reconexión exige un snapshot REST, que es el endpoint con mayor weight en el rate limit.
2. Un 429 seguido de más requests produce un ban 418, y las IPs que se desconectan repetidamente pueden ser baneadas. Ambas reglas convierten una falla transitoria en una exclusión prolongada del cliente.

Lo reportado por usuarios en el foro oficial de desarrolladores:
1. Conexiones que se cortan con 1006 durante trading intenso.
2. Un usuario con unas 340 suscripciones de depth vio caer todas casi en el mismo instante, lo que indica que las desconexiones están correlacionadas.

Lo que no existe: un post‑mortem de Binance que atribuya un incidente a una tormenta de resync. El 10/10/2025 Binance reconoció carga alta, delays y un "display error", sin detallar la causa, y tampoco se conocen sus mitigaciones internas. Por lo tanto el paper no afirma que Binance cayó por esta causa, sino que su contrato público reúne las condiciones estructurales de una falla metaestable.

#### Base académica

Bronson et al. (HotOS 2021) definen la falla metaestable como un sistema que entra en un estado malo por un trigger y permanece ahí por un sustaining effect, un loop donde el trabajo generado por las fallas consume la capacidad que evitaría nuevas fallas. Huang et al. (OSDI 2022) documentan 22 incidentes reales con esa estructura. Isaacs, Alvaro et al. (HotOS 2025) proponen simular sistemas para encontrar modos metaestables antes de que ocurran. El mismo patrón aparece en reliable multicast como NACK implosion, donde muchos receptores piden retransmisión a la fuente y la colapsan (SRM, Floyd et al., SIGCOMM 1995).

#### Brecha

La literatura de metastable failures estudia storage, RPC y microservicios, y sus soluciones son sobre todo tácticas, como load shedding, control de retries y admission control. Huang et al. reportan load shedding en más de 55 % de las recuperaciones estudiadas. Esas tácticas protegen al servidor descartando trabajo, pero en market data un resync descartado deja al cliente con el libro inválido. Por otro lado, las soluciones estructurales de reliable multicast (recuperación local y retransmisión cíclica) asumen IP multicast, que internet pública y las nubes no ofrecen. Falta una arquitectura que lleve esas soluciones estructurales a distribución por WebSocket hacia millones de clientes retail.

#### Arquitectura propuesta

```
REFERENCIA · contrato público de Binance
Matching ──► Publisher ──► WebSocket deltas ──► Cliente
                                                  │ reconexión
                                                  ▼
                              REST /depth snapshot (rate limit, 429, ban)
   La recuperación sube al origen, y su costo crece con los clientes desconectados.

PROPUESTA · distribución jerárquica por push con recuperación local
                 ┌─────────────── Origen ───────────────┐
                 │ Matching ──► Feed secuenciado        │
                 │              deltas + snapshot cíclico│  tasa fija, no depende de N
                 └──────────────────┬───────────────────┘
                     ┌──────────────┼──────────────┐
                Relay Lima     Relay São Paulo   Relay ...     cada relay mantiene
                libro local    libro local                     su copia del libro
                     │ conflation por cliente lento
                     ▼
                 Clientes ── reconexión ──► relay local (nunca el origen)
   El tráfico de recuperación nunca sube al origen.
```

| Decisión de arquitectura | Qué hace | Fundamento |
|---|---|---|
| Separar el camino de distribución del camino de recuperación | El origen solo emite un feed de tasa fija y la recuperación ocurre en el tier de relays | Recuperación local de SRM y designated receivers de RMTP (Paul et al., IEEE JSAC 1997) |
| Tier de edge relays como overlay sobre unicast | Cada región tiene un relay con su propia réplica del libro que atiende las reconexiones de sus clientes | Jasper (Haseeb et al., arXiv 2402.09527, 2024‑2025), overlay de proxies en la nube para market data de un exchange |
| Snapshot cíclico dentro del feed | El libro completo circula en loop, así un relay o cliente desincronizado se recupera sin hacer requests | Data carousel (Byers et al., SIGCOMM 1998) y Market Recovery feed de CME MDP 3.0 |
| Conflation por cliente en el relay | Si la cola de un cliente lento crece, el relay fusiona los deltas pendientes y envía el último valor por nivel de precio, por lo que la conexión no se corta | Delta‑state CRDTs (Almeida, Shoker y Baquero, JPDC 2018). Los deltas de Binance traen cantidades absolutas por nivel, así que el libro es un mapa de registros last‑writer‑wins y fusionar deltas no altera el estado final. CME opera un feed conflated para BrokerTec |

El estilo resultante es un publish‑subscribe jerárquico basado en push, con el estado del libro replicado en los relays bajo consistencia eventual.

#### Hipótesis

La arquitectura propuesta no tiene estado metaestable. Bajo un pico de 10x mensajes con desconexiones correlacionadas cumple tres propiedades:
1. La carga del origen se mantiene constante sin importar cuántos clientes se desconecten.
2. El tiempo de recuperación de un cliente está acotado por el periodo del snapshot cíclico más un salto al relay, y no depende de cuántos clientes se recuperan a la vez.
3. Al retirar el pico, el sistema vuelve al estado sano en un tiempo acotado y sin intervención manual.

Mecanismo. Una falla metaestable necesita que el trabajo de recuperación compita por la misma capacidad que evita nuevas fallas. En la arquitectura propuesta ese loop no se cierra en el origen, porque ningún tráfico de recuperación sube hasta él y el snapshot cíclico tiene tasa fija. Dentro de cada relay el trabajo de recuperación queda limitado a sus propios clientes, y la conflation evita que un cliente lento llegue a desconectarse, con lo que se elimina el trigger en su origen.

Refutación. La hipótesis cae si la carga del origen crece con el número de clientes desconectados, si el tiempo de recuperación crece con el número de clientes recuperándose a la vez, o si los propios relays entran en un estado metaestable al saturarse con las reconexiones de su región. Este último caso define el límite de clientes por relay, que forma parte del dimensionamiento de la arquitectura.

#### Cómo se demuestra

Las tres propiedades se derivan primero de forma analítica a partir de la estructura, y luego se verifican con un POC de la arquitectura (origen, 3 relays y miles de clientes WebSocket sintéticos con distintas velocidades de red). El experimento aplica un pico de mensajes con desconexiones correlacionadas, lo retira y mide carga del origen frente al número de desconectados, tiempo de recuperación por cliente, staleness p99 y tiempo hasta el estado sano. El contrato público de Binance se reproduce solo como línea de referencia para cuantificar la mejora.

#### Plan por semana

| Semana | Entregable |
|---|---|
| 13 | Requerimientos (staleness, tiempo de recuperación, carga del origen), usuario modelo (trader retail en móvil, market maker, operador), estudio del contrato de Binance y SOTA |
| 14 | Arquitectura propuesta con sus decisiones, derivación de las tres propiedades y definición de métricas y del escenario de pico |
| 15 | POC, gráficas de recuperación, dimensionamiento de relays y paper |

#### Por qué cumple con todo

| Requisito | Cómo lo cumple |
|---|---|
| Caso real | Contrato documentado oficialmente por Binance, reportes del foro y evento del 10/10/2025 |
| Base académica | Metastable failures (2021‑2026), reliable multicast, Jasper (2024‑2025) y delta‑CRDTs |
| Brecha | Las tácticas actuales no resuelven el caso, y las soluciones estructurales asumen multicast |
| Es arquitectura | La hipótesis es una propiedad que surge de la topología, la separación de caminos y la ubicación del estado |
| Hipótesis con mecanismo | Se deriva de la definición de sustaining effect |
| Demostración con métricas | Las tres propiedades se miden en el POC |
| POC en 12 h | Origen, relays y clientes sintéticos en contenedores, sin data privada |

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

arXiv 2512.01112 (2025) analiza el evento en Hyperliquid y estima que el algoritmo de producción quitó entre 45 y 51,7 millones de USD de más a los traders ganadores. arXiv 2602.15182 (2026) modela el ADL como online learning y reporta un regret cercano a 50 % para producción frente a 2,6 % para el optimizado. arXiv 2603.15963 (2026) propone una asignación basada en riesgo sobre unos 2 mil millones de USD de ADL concentrados en minutos. En arquitectura, LMAX usa el journal de eventos del matching como fuente única de verdad, y DBSP (Budiu et al., VLDB 2023) formaliza el mantenimiento incremental de vistas sobre streams de cambios.

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
| Journal del matching como fuente única de verdad | Todo cambio de posición es un evento secuenciado | Event sourcing en LMAX (Fowler, The LMAX Architecture) |
| Proyección de riesgo separada del write path | El projector consume el journal de forma asíncrona, fuera del critical path del matching | CQRS |
| Índice mantenido incrementalmente | Cada trade actualiza el índice en O(log n), por lo que en el déficit solo se consulta | Incremental view maintenance, DBSP (VLDB 2023) |
| Decisión versionada por número de secuencia | Cada decisión de ADL declara sobre qué prefijo del journal se calculó | Determinismo del state machine, que permite reproducir y auditar la decisión |

#### Hipótesis

El risk engine event‑sourced ejecuta un algoritmo de ADL optimizado durante una cascada con tres propiedades:
1. La latencia de decisión de ADL no depende del número de posiciones abiertas.
2. La latencia p99 del matching no cambia al activar el projector.
3. Toda decisión de ADL es reproducible exactamente desde el journal, por lo que es auditable.

Mecanismo. La vista es una función determinista del prefijo del journal, así que mantenerla con cada trade reparte el costo en el tiempo y la consulta en el déficit cuesta O(k log n) para k posiciones cerradas. El projector lee el journal sin bloquear al matching, y la reproducibilidad sale de versionar cada decisión con el número de secuencia.

Refutación. La hipótesis cae si durante la cascada el projector no alcanza la tasa de eventos y su lag crece sin límite, ya que la vista se volvería un componente saturado. Ese punto define la capacidad del projector.

#### Cómo se demuestra

Replay de los fills públicos de Hyperliquid del 10/10/2025 a 1x y 10x de velocidad. Se mide latencia de decisión frente al número de posiciones, lag del projector, latencia p99 del matching con y sin projector, y se verifica que reproducir el journal da las mismas decisiones. El exceso en USD se reporta como resultado secundario, porque depende del algoritmo de los papers.

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

H‑Store (Stonebraker et al., VLDB 2007) muestra que una base de datos en memoria con un hilo por partición logra órdenes de magnitud más throughput siempre que las transacciones toquen una sola partición, porque las distribuidas son mucho más lentas. Es la misma estructura que LMAX y arXiv 2606.01183 (2026) usan para matching. Bailis et al. (VLDB 2015) demuestran que un invariante como saldo no negativo bajo retiros exige coordinación. Escrow (O'Neil, TODS 1986) y Homeostasis (Roy et al., SIGMOD 2015) reducen esa coordinación repartiendo el valor en reservas locales. E‑Store (VLDB 2014) y Squall (SIGMOD 2015) mueven datos calientes entre particiones en vivo.

#### Brecha

En un exchange el matching se particiona por par y el saldo por usuario, así que las dos claves de partición no coinciden. Los trabajos de H‑Store asumen una sola clave, y los de escrow no consideran la demanda concentrada de un listing, que agota las reservas de una partición en segundos.

#### Arquitectura propuesta

```
REFERENCIA · saldo central
Gateway ──► Partición BTC ──► 2PC ──► Servicio de saldos ◄── 2PC ◄── Partición ETH

PROPUESTA · particiones por par con escrow de saldos
                          Balance service (saldo global)
                         ▲ transferencia de reservas, asíncrona y guiada por demanda
           ┌─────────────┼──────────────┐
Gateway ─► Partición BTC   Partición ETH   Partición del listing
           sequencer        sequencer       migración en vivo estilo Squall
           book + reservas  book + reservas reservas asignadas según demanda
   Una orden se valida contra la reserva local, sin salir de la partición.
```

| Decisión de arquitectura | Qué hace | Fundamento |
|---|---|---|
| Partición por par con un sequencer por partición | Cada libro se procesa en un hilo sin locks | H‑Store, LMAX, arXiv 2606.01183 |
| Saldo como escrow | El saldo del usuario se reparte en reservas por partición, cuya suma nunca supera el saldo | Escrow (O'Neil 1986) |
| Transferencia de reservas guiada por demanda | Las reservas se mueven hacia las particiones donde el usuario opera más | Treaties de Homeostasis (SIGMOD 2015) |
| Migración en vivo de pares calientes | Un par con demanda extrema se mueve a su propia partición sin detener el trading | Squall (SIGMOD 2015) y E‑Store (VLDB 2014) |

#### Hipótesis

La arquitectura con escrow cumple tres propiedades:
1. Una orden se admite sin coordinación entre particiones mientras la reserva local alcance, por lo que el throughput de cada partición no depende del porcentaje de usuarios que operan en varios pares.
2. El costo de coordinación es proporcional a la frecuencia de transferencias de reservas y no al número de órdenes.
3. El invariante saldo ≥ 0 se cumple siempre, incluso durante transferencias y migraciones.

Mecanismo. Bailis et al. prueban que el invariante de saldo exige coordinación, y el escrow la concentra en la transferencia de reservas, que ocurre solo cuando una reserva se agota. La propiedad 3 sale de que la suma de reservas nunca supera el saldo global, condición que la transferencia preserva por construcción.

Refutación. La hipótesis cae si, durante un listing, las transferencias de reservas se vuelven tan frecuentes como las órdenes, porque la coordinación volvería a ser por orden. Ese punto define el límite de concentración que la arquitectura soporta.

#### Cómo se demuestra

Mini exchange con 8 particiones. Se varía el porcentaje de usuarios multi‑par y se simula un listing con demanda concentrada. Se mide throughput por partición, latencia p99, transferencias de reservas por segundo y órdenes rechazadas por reserva insuficiente, y un checker verifica el invariante de saldo en cada paso. El diseño con saldo central se usa solo como línea de referencia.

---

## Comparación

| | Idea 1 | Idea 2 | Idea 3 |
|---|---|---|---|
| Línea académica | Metastable failures | Auto‑deleveraging | Partitioned in‑memory DB y escrow |
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
- Metaestabilidad: [Isaacs, Alvaro et al., HotOS 2025](https://sigops.org/s/conferences/hotos/2025/papers/hotos25-106.pdf), [arXiv 2510.03551](https://arxiv.org/abs/2510.03551), [arXiv 2606.00942](https://arxiv.org/abs/2606.00942), [Farahbakhsh, Haeberlen et al., HotNets 2025](https://haeberlen.cis.upenn.edu/papers/metastability-hotnets2025.pdf), Bronson et al. HotOS 2021, Huang et al. OSDI 2022
- Market data Binance: [How to manage a local order book correctly](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly), [Binance WebSocket Market Streams, límites y bans](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Connect), [Foro, 1006 durante trading intenso](https://dev.binance.vision/t/websocket-keeps-disconnecting-with-1006-error-during-heavy-trading/35472), [Foro, depth websockets cerrándose juntos](https://dev.binance.vision/t/depth-websockets-keep-closing-1006-but-not-clientside/2428), [Foro, reconexión del order book local](https://dev.binance.vision/t/local-orderbook-binance-spot-websocket-disconnection/22050)
- Recientes: [Jasper, arXiv 2402.09527](https://arxiv.org/abs/2402.09527), [RetryGuard, arXiv 2511.23278](https://arxiv.org/abs/2511.23278), Rajomon (NSDI 2025), [Metastable Failures in the Wild](https://www.usenix.org/publications/loginonline/metastable-failures-wild)
- Arquitectura C: [SRM, Floyd et al. SIGCOMM 1995](https://www.icir.org/floyd/srm.html), RMTP (Paul et al., IEEE JSAC 1997), Digital Fountain y data carousel (Byers et al., SIGCOMM 1998), [Delta‑state CRDTs, arXiv 1603.01529](https://arxiv.org/abs/1603.01529), [CME MDP 3.0 Recovery Services](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457325847/MDP+3.0+-+Recovery+Services), [CME conflated feed BrokerTec](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457672459/MDP+3.0+-+MBP+and+MBOLD+Market+Recovery+for+the+Conflated+UDP+Market+Data+Group+for+BrokerTec)
- ADL: [DBSP, VLDB 2023](https://www.vldb.org/pvldb/vol16/p1601-budiu.pdf), [Fowler, CQRS](https://martinfowler.com/bliki/CQRS.html), [arXiv 2512.01112](https://arxiv.org/abs/2512.01112), [arXiv 2602.15182](https://arxiv.org/abs/2602.15182), [arXiv 2603.15963](https://arxiv.org/abs/2603.15963)
- Particionado y escrow: [E‑Store, VLDB 2014](https://db.cs.cmu.edu/wordpress/wp-content/uploads/2015/01/E_Store.pdf), [Squall, SIGMOD 2015](https://www.doi.org/10.1145/2723372.2723726), [O'Neil, Escrow Transactional Method](https://www.cs.umb.edu/~poneil/EscrowTM.pdf), [Homeostasis, SIGMOD 2015](https://infoscience.epfl.ch/record/219208/files/final_camera_ready.pdf), Bailis et al. VLDB 2015, Stonebraker et al. VLDB 2007, [arXiv 2606.01183](https://arxiv.org/abs/2606.01183)
