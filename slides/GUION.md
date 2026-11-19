# Guion de la exposición RelayBook

Pedro expone las diapositivas 1 a 10 durante 8:45 y Nicolás las diapositivas 11 a 19 durante 8:35. El total es 17:20 de los 20 minutos disponibles, con 2:40 de margen para pausas. Los tiempos suponen una lectura en voz alta de unas 140 palabras por minuto.

| Bloque | Expone | Diapositivas | Minuto | Duración |
| --- | --- | --- | --- | --- |
| Contexto, problema, relays y state-based resume | Pedro | 1–10 | 0:00–8:45 | 8:45 |
| Réplicas, hipótesis, evaluación, resultados y conclusión | Nicolás | 11–19 | 8:45–17:20 | 8:35 |

## Pedro, diapositivas 1 a 10

### 1. Portada · 0:00–0:15 (15 s)

Buenos días. La presentación expone RelayBook, una arquitectura para que los clientes de Binance recuperen sus datos de mercado sin saturar al servidor central cuando miles se desconectan a la vez.

### 2. Binance como exchange · 0:15–0:50 (35 s)

Binance es el exchange de criptomonedas más grande del mundo. Un exchange es un mercado donde las personas compran y venden entre sí a través de la plataforma. En la figura, Ana ofrece vender medio bitcoin a 67 002 dólares y Luis ofrece comprar 1.2 a 67 000. Las órdenes sin contraparte esperan en el order book, y el matching engine cruza las que coinciden. A la derecha, Binance publica lo que ocurre en el mercado, el market data, para millones de apps, bots y proveedores.

### 3. El order book · 0:50–2:05 (75 s)

En el order book las ventas, o asks, aparecen arriba en ámbar y las compras, o bids, abajo en morado. El vendedor más barato pide 67 001 y el comprador que más paga ofrece 67 000, por lo que el precio de mercado queda entre ambos valores. Cada fila es un nivel de precio y suma todas las órdenes a ese precio, como el 2.0 de 67 001, que corresponde a dos vendedores con 0.5 y 1.5.

A la derecha, un bot compra 1 bitcoin al mejor precio. La orden se cruza con el vendedor de 67 001 y ese nivel baja de 2.0 a 1.0. Ese cambio se llama delta y contiene el valor nuevo del nivel, 1.0, en lugar de una resta. La propuesta se apoya en esta propiedad. Binance publica el libro nivel por nivel con su cantidad total, y con eso cada cliente arma una copia local.

### 4. Copia local con snapshot y deltas · 2:05–2:55 (50 s)

El cliente arma esa copia con dos tipos de mensaje. El snapshot es la foto completa del libro, que en la grabación tenía 2 000 niveles y 41 KB. Los deltas contienen solo los niveles que cambiaron y llevan un número de secuencia. En la fila superior llegan el 1001, el 1002 y el 1003, y la copia queda igual al libro real. En la fila inferior se pierde el 1002, por lo que la copia muestra 1.2 en el nivel 67 000 cuando el valor real es 1.5. El cliente detecta la pérdida porque después del 1001 recibe el 1003, y desde ese momento su copia deja de ser confiable.

### 5. Recuperación en el contrato actual de Binance · 2:55–3:35 (40 s)

Binance documenta un procedimiento en tres pasos. Primero, el cliente abre un WebSocket, una conexión persistente que empuja los deltas. Luego pide el snapshot por REST al servidor central y aplica los deltas encima. Ante un salto en la secuencia o un corte, el cliente descarta su libro y vuelve a pedir el snapshot completo. Ese endpoint tiene rate limit, con error 429 ante exceso de peticiones y 418, un ban, si el cliente insiste. Como el stream no reenvía los mensajes perdidos, un corte de un segundo o de un minuto cuesta el libro entero.

### 6. Tormenta de reconexiones · 3:35–4:30 (55 s)

El problema aparece durante un pico de volatilidad, cuando la cantidad de mensajes se multiplica, por diez en el experimento. Los clientes con conexión lenta no alcanzan a recibir el stream y pierden la conexión. Según el procedimiento, cada uno pide el libro completo, y son miles a la vez. El servidor central debe enviar el stream a diez veces su ritmo y además miles de snapshots, por lo que se satura y retrasa el stream. Ese retraso atrasa a más clientes, que también se desconectan y piden snapshot, lo que forma un bucle. Además, los clientes que reintentan demasiado reciben un ban. En consecuencia, la recuperación compite con el stream por la misma capacidad.

### 7. Falla metaestable · 4:30–5:15 (45 s)

Este bucle corresponde a una falla metaestable. A la izquierda, en una sobrecarga normal, los clientes pierden su libro durante el pico y el sistema se recupera cuando el pico termina. A la derecha, en una falla metaestable, la carga vuelve a lo normal y el sistema sigue caído, porque un efecto sostenedor, en este caso los retries de snapshots, mantiene la saturación. Los gráficos son un esquema cualitativo. La referencia es Isaacs et al., 2025, que proponen estudiar estas fallas con modelos y simulación, enfoque que sigue este trabajo.

### 8. Evidencia en Binance · 5:15–6:00 (45 s)

Respecto a Binance existen indicios. En el foro oficial, usuarios reportan conexiones cerradas con el código 1006 durante trading intenso y muchos streams de profundidad cerrándose al mismo tiempo. Además, Tardis.dev, un proveedor de datos, reconstruye el libro con el snapshot REST cuando pierde un mensaje. Sin embargo, ningún post-mortem público atribuye una caída a este bucle, y las mitigaciones internas de Binance y el costo de generar un snapshot no son públicos. Por eso el trabajo solo sostiene que el contrato tiene la estructura del problema y lo evalúa con una simulación.

### 9. RelayBook con relays regionales · 6:00–7:05 (65 s)

La propuesta, RelayBook, se basa en tres ideas, y la primera aparece en esta figura. A la izquierda, en Binance el mismo servidor central reparte el stream a todos los clientes y atiende cada recuperación, marcadas con flechas rojas, de modo que todas las reconexiones llegan al mismo punto.

A la derecha, en RelayBook el origen publica un solo feed numerado hacia una capa de relays, uno o más por región. Un relay es un servidor intermedio que mantiene una copia del libro y atiende a sus clientes. Cuando un cliente se reconecta, la recuperación ocurre en el relay, en verde, sin intervención del origen. Así, el trabajo del origen depende solo de la cantidad de relays. El costo es una capa adicional de servidores que requiere operación y que también puede fallar.

### 10. State-based resume · 7:05–8:45 (100 s)

La segunda idea es el state-based resume, que reanuda al cliente a partir del estado del libro. El mecanismo se explica en cuatro pasos con el mismo libro.

Antes del corte, el cliente tiene el libro al día hasta el mensaje 1000. Luego se desconecta y no recibe seis mensajes, marcados en rojo. El nivel 67 000 cambia cuatro veces, a 1.0, 1.5, 0.7 y 0.9, el 66 999 cambia a 0.6 y el 67 002 llega a cero, es decir, se borra.

El relay recibe esos mensajes y guarda por cada nivel su valor actual y el número del último mensaje que lo cambió. El nivel borrado queda en cero como tombstone, para poder avisarlo al cliente. En verde aparecen los niveles que cambiaron después del 1000.

Cuando el cliente vuelve e informa que tiene hasta el 1000, el relay envía solo esos tres niveles con su valor actual y el cliente queda idéntico al relay. Como cada delta trae el valor nuevo, de 1.0, 1.5, 0.7 y 0.9 solo cuenta el 0.9.

Abajo se compara la recuperación. Binance envía el libro entero de 2 000 niveles, un resume estilo Ably, servicio de mensajería en tiempo real, reenvía los seis mensajes y RelayBook envía tres niveles. Como regla de seguridad, si los cambios pesan tanto como el libro, el relay envía el libro completo, por lo que reanudar nunca cuesta más que resincronizar. Nicolás explica a continuación cómo se sincronizan los relays y cómo se evaluó la propuesta.

## Nicolás, diapositivas 11 a 19

### 11. Réplicas por región (leader-follower) · 8:45–9:50 (65 s)

La tercera idea organiza los relays como réplicas por región. Funcionan como las réplicas de una base de datos, donde el origen es el líder, los relays son followers y el feed numerado actúa como log de replicación. De ahí surgen cinco mecanismos.

Primero, solo el origen numera los mensajes, así que todos los relays aplican los mismos cambios en el mismo orden y ninguno genera un libro inexistente. Segundo, si el replication lag de un relay supera 500 milisegundos, el relay se marca como no saludable y sus clientes reanudan en otro relay de la región. Tercero, ante un gap en el feed, el relay redirige a sus clientes o espera el snapshot que el feed envía cada segundo, sin consultar al origen. Cuarto, un checksum de los 10 mejores niveles detecta copias divergentes. Quinto, con conflation el relay mantiene conectado al cliente lento y le envía solo el último valor de cada nivel.

### 12. Hipótesis y métricas · 9:50–10:40 (50 s)

La hipótesis tiene dos partes refutables. La primera plantea que el contrato de Binance, con tráfico real acelerado diez veces, sigue degradado cuando termina el pico. La segunda plantea que, en las mismas condiciones, RelayBook cumple tres metas y el resume estilo Ably muestra más atraso, porque cada recuperación arrastra todos los mensajes perdidos.

El full resync ratio mide la fracción de reconexiones que terminan en un libro completo, con meta menor al 1 %. El time to recover mide cuánto tarda el 99 % de los clientes en volver a tener un libro válido, con meta de 30 segundos o menos. La staleness p99 mide el atraso del libro del cliente, con meta menor a un segundo.

### 13. Datos reales y prototipo del relay · 10:40–11:30 (50 s)

La evaluación usa tráfico real. Se grabaron 70 minutos del stream público de profundidad de Binance Futures para BTC/USDT el 13 de noviembre, con 41 113 mensajes y ninguno perdido. Llegan casi diez mensajes por segundo y cada uno cambia en promedio 275 niveles. El snapshot tenía 2 000 niveles y pesaba 41 KB.

Sobre esa grabación se construyó un prototipo del relay que aplica cada delta y guarda por nivel el último mensaje y los tombstones. En la validación con 46 reconexiones al azar, el libro del cliente quedó idéntico al del relay en los 46 casos, tanto en el checksum como en los 100 mejores niveles de cada lado.

### 14. Tamaño de una recuperación · 11:30–12:30 (60 s)

El primer experimento mide cuánto pesa recuperar a un cliente. Sobre la grabación a ritmo normal se desconectan clientes en momentos al azar durante 1 a 60 segundos y se mide cuánto debe enviarse con cada diseño, en escala logarítmica.

La línea roja punteada es el snapshot de Binance, siempre de 41 KB. La línea gris es el resume estilo Ably, que crece porque reenvía cada mensaje y llega a 3.4 MB tras un minuto. La línea verde es el state-based resume, con 15 KB tras un segundo de corte, un 63 % menos que el snapshot. Entre 5 y 10 segundos cambian tantos niveles que el relay envía el snapshot, por lo que el costo nunca supera al libro. Frente al estilo Ably, el payload es entre 3 y 84 veces menor. La reducción se explica porque muchos mensajes vuelven a tocar los mismos niveles, ya que en 10 segundos llegan unas 27 000 actualizaciones sobre solo unos 2 800 niveles distintos.

### 15. Simulación de la tormenta con tráfico real · 12:30–13:25 (55 s)

El segundo experimento, el central, simula la tormenta. El tiempo avanza en pasos de 100 milisegundos y cada servidor reparte su capacidad entre sus conexiones. La grabación se reproduce en tres fases, cinco minutos a ritmo normal, cinco minutos a diez veces y diez minutos a ritmo normal, para observar si el sistema se recupera solo. Al inicio del pico se desconecta el 30 % de los 2 000 clientes, y el 30 % del total tiene conexión lenta.

Si una conexión acumula 1 MB pendiente, Binance y Ably la cortan, mientras que RelayBook aplica conflation desde los 256 KB. El estilo Ably corre sobre los mismos relays, de modo que solo difiere en la forma de reanudar. La capacidad sobrante de Binance y el costo de generar un snapshot no son públicos, por lo que se prueban seis capacidades y tres costos, en total 18 corridas.

### 16. Resultados de la tormenta (capacidad 3×) · 13:25–14:15 (50 s)

La tabla corresponde a una capacidad de tres veces la carga normal. Binance con snapshot barato se recupera al instante, aunque durante el pico su atraso llega a 3.6 segundos, y con snapshot caro tarda 38 segundos o no se recupera. RelayBook se recupera en cero segundos, con 1.1 segundos de atraso, y el origen carga 0.3 MB por segundo frente a 120 en Binance, 400 veces menos.

Durante el pico, Binance registró 164 mil reconexiones y RelayBook 629, porque la conflation evita cortar a los clientes lentos. El estilo Ably llegó a 120 segundos de atraso, lo que confirma esa predicción. Sin embargo, la columna de full resync marca 100 % para RelayBook, resultado que se analiza en las dos partes de la hipótesis.

### 17. Primera parte de la hipótesis · 14:15–15:15 (60 s)

La primera parte evalúa si el contrato de Binance sigue degradado tras el pico. La grilla muestra sus 18 corridas, con la capacidad en columnas, el costo del snapshot en filas y en cada celda el tiempo de recuperación. Con snapshot barato, en la fila superior, siempre se recupera en 11 segundos o menos, por lo que no aparece falla metaestable. Con snapshot caro y poca capacidad sobrante, en rojo oscuro, no se recupera en los diez minutos observados, en 5 de 18 corridas.

En esos casos aparece el efecto sostenedor, ya que el origen sigue generando snapshots para clientes que los abandonaron al reintentar, hasta 146 GB. Como el costo real de un snapshot en Binance es desconocido, el resultado identifica las condiciones de vulnerabilidad del contrato sin demostrar una falla en producción. Por lo tanto, la primera parte se cumple solo bajo esas condiciones.

### 18. Segunda parte de la hipótesis · 15:15–16:35 (80 s)

La segunda parte evalúa si RelayBook cumple las tres metas. Cumple el time to recover, queda cerca en staleness y falla en full resync. El gráfico muestra en el eje horizontal los mensajes perdidos por el cliente y en el vertical los niveles distintos que cambiaron, con la línea roja en el tamaño del libro, 2 000 niveles.

A ritmo normal, un segundo equivale a unos 10 mensajes que tocan unos 1 100 niveles, menos que el libro, de modo que el state-based resume reduce el payload. En el pico a diez veces, un segundo equivale a unos 100 mensajes que tocan unos 2 800 niveles, más que el libro entero, por lo que la regla de seguridad envía el snapshot y el full resync llega al 100 %.

Ese snapshot sale del relay y solo ocurrió 629 veces. La staleness quedó entre 1.1 y 1.3 segundos por los clientes lentos. En consecuencia, la mejora de RelayBook proviene de recuperar en los relays y de la conflation, más que del tamaño de cada recuperación.

### 19. Conclusión y trabajo futuro · 16:35–17:20 (45 s)

En síntesis, la hipótesis se cumple en time to recover, queda cerca en staleness y se refuta en full resync. El contrato de Binance solo queda caído con snapshots caros y poca capacidad, mientras que RelayBook se recupera de inmediato sin cargar al origen.

Como trabajo futuro se propone medir el costo real de generar un snapshot, probar varios instrumentos y picos reales, desplegar relays en una red real, limitar el tiempo que el relay guarda los tombstones y ajustar la conflation para reducir el atraso de los clientes lentos. Muchas gracias. ¿Preguntas?
