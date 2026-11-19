# Guion de la exposición RelayBook

Pedro expone las diapositivas 1 a 10 (8:45) y Nicolás de la 11 a la 19 (8:35). Total 17:20 de 20:00, con unos 2:40 de margen para pausas. El texto está pensado para leerse en voz alta a unas 140 palabras por minuto; no hace falta memorizarlo.

| Bloque | Expone | Diapositivas | Minuto | Duración |
| --- | --- | --- | --- | --- |
| Contexto, problema, relays y state-based resume | Pedro | 1–10 | 0:00–8:45 | 8:45 |
| Réplicas, hipótesis, cómo lo probamos, resultados y conclusión | Nicolás | 11–19 | 8:45–17:20 | 8:35 |

## Pedro, parte 1: contexto, problema y propuesta

### 1. Portada · 0:00–0:15 (15 s)

Buenos días. Somos Pedro Mori y Nicolás Castaneda, y presentamos RelayBook: una arquitectura para que los clientes de Binance recuperen sus datos de mercado sin tumbar al servidor central cuando miles se desconectan a la vez.

### 2. ¿Qué es Binance? Un exchange · 0:15–0:50 (35 s)

Primero, el contexto. Binance es el exchange de criptomonedas más grande del mundo. Un exchange es un mercado: uno no le compra bitcoin a Binance, se lo compra a otra persona a través de Binance. Ana quiere vender medio bitcoin a 67 002 dólares y Luis quiere comprar 1.2 a 67 000. Las órdenes que no encuentran pareja esperan en el order book, y el matching engine cruza las que coinciden. A la derecha, lo que nos importa: Binance publica lo que pasa en el mercado, el market data, para millones de apps, bots y proveedores.

### 3. El order book · 0:50–2:05 (75 s)

Así se ve un order book. Arriba, en ámbar, las ventas, o asks. Abajo, en morado, las compras, o bids. El vendedor más barato pide 67 001 y el comprador que más paga ofrece 67 000, así que el precio de mercado está entre esos dos valores. Cada fila es un nivel de precio y suma todas las órdenes a ese precio: el 2.0 de 67 001 son dos vendedores, uno con 0.5 y otro con 1.5.

A la derecha, qué cambia el libro. Un bot quiere comprar 1 bitcoin ya: se cruza con el vendedor más barato y el nivel 67 001 baja de 2.0 a 1.0. Ese cambio se llama delta, y dice el valor nuevo, “67 001 ahora vale 1.0”, no “resta 1”. Esto será clave más adelante. Binance publica el libro así, nivel por nivel con su cantidad total, y con eso cada cliente arma su propia copia.

### 4. Cómo el cliente arma su copia · 2:05–2:55 (50 s)

¿Cómo arma esa copia? Con dos tipos de mensaje. Primero, un snapshot: la foto completa del libro; en nuestros datos, 2 000 niveles y 41 KB. Después, deltas: mensajes con solo los niveles que cambiaron, cada uno con un número de secuencia. En la fila de arriba llegan todos: aplico el 1001, el 1002 y el 1003, y mi copia queda igual al libro real. En la fila de abajo se pierde el 1002, y mi copia sigue diciendo 1.2 en el nivel 67 000 cuando el real es 1.5. Me doy cuenta porque después del 1001 me llegó el 1003. Desde ese momento, mi copia no es confiable.

### 5. Binance hoy: qué pasa si pierdes un mensaje · 2:55–3:35 (40 s)

Esta es la receta que Binance documenta. Uno: abrir el WebSocket, una conexión que se queda abierta y empuja los deltas. Dos: pedir el snapshot por REST, una petición puntual al servidor central. Tres: aplicar los deltas encima. Si hay un salto en la secuencia o se corta la conexión, el cliente tira su libro y vuelve al paso dos. Ese REST tiene límites: error 429 si pides demasiado, y 418, un baneo, si insistes. Lo clave: Binance no reenvía lo perdido. Un segundo o un minuto fuera, pagas el libro entero.

### 6. El problema: una tormenta de reconexiones · 3:35–4:30 (55 s)

Ahora, el problema. Imaginen un momento de mucha volatilidad: el bitcoin cae fuerte y los mensajes se multiplican; en nuestro experimento, por diez. Los clientes con internet lento no alcanzan a recibir todo y se les corta la conexión. Según la receta, cada uno pide el libro completo, y son miles a la vez. El servidor central tiene que mandar el stream, que ya va a diez veces, y además miles de snapshots. Se satura y retrasa el stream; eso atrasa a más clientes, que también se cortan y piden snapshot. Es un bucle, y quien reintenta mucho termina baneado. La recuperación compite con el stream por la misma capacidad.

### 7. La falla metaestable · 4:30–5:15 (45 s)

¿Por qué es grave? Porque este bucle tiene nombre en la literatura: falla metaestable. A la izquierda, una sobrecarga normal: durante el pico los clientes pierden su libro, pero cuando termina, el sistema se recupera solo. A la derecha, una falla metaestable: el pico termina, la carga vuelve a lo normal, y el sistema sigue caído, porque lo mantiene un efecto sostenedor, aquí los reintentos de snapshots. Estos gráficos son un esquema, no mediciones. La referencia es Isaacs y otros, 2025, que proponen estudiar estas fallas con modelos y simulación, y eso es lo que hicimos.

### 8. ¿Le pasa esto a Binance de verdad? · 5:15–6:00 (45 s)

¿Le pasa esto a Binance de verdad? Hay indicios. En el foro oficial de Binance, usuarios reportan conexiones cerradas con el código 1006 en momentos de mucho trading, y muchos streams cerrándose a la vez. Y Tardis.dev, un proveedor de datos, reconstruye el libro con el snapshot REST cuando pierde un mensaje. Pero no hay ningún post-mortem público que atribuya una caída a este bucle, y no conocemos las mitigaciones internas de Binance ni cuánto le cuesta generar un snapshot. Por eso solo afirmamos que el contrato tiene la estructura del problema, y lo pusimos a prueba con una simulación.

### 9. RelayBook: recuperar en relays regionales · 6:00–7:05 (65 s)

Nuestra propuesta se llama RelayBook y tiene tres ideas. La primera está en esta figura. A la izquierda, Binance hoy: el mismo servidor central reparte el stream a todos los clientes y además atiende cada recuperación; son las flechas rojas. Cuando miles se reconectan, todas llegan al mismo lugar.

A la derecha, RelayBook. El origen publica un solo feed numerado hacia una capa de relays, uno o más por región. Un relay es un servidor intermedio que mantiene una copia del libro y atiende a sus clientes. Cuando un cliente se reconecta, lo resuelve el relay, en verde, y el origen ni se entera. Así, el trabajo del origen depende de cuántos relays hay, no de cuántos clientes se desconectan. El costo es una capa nueva de servidores que hay que operar y que puede fallar.

### 10. Idea 2: state-based resume · 7:05–8:45 (100 s)

La segunda idea es la central: state-based resume, reanudar por estado. Va en cuatro pasos, con el mismo libro de antes.

Paso uno: antes del corte, el cliente tiene el libro al día hasta el mensaje 1000. Paso dos: se desconecta y no recibe seis mensajes. En rojo: el nivel 67 000 cambia cuatro veces, a 1.0, 1.5, 0.7 y 0.9; el 66 999 cambia a 0.6; y el 67 002 llega a cero, o sea, se borra.

Paso tres: el relay sí recibió esos mensajes. Por cada nivel guarda su valor actual y el número del último mensaje que lo cambió. Al nivel borrado no lo elimina: lo deja en cero, como una lápida, para poder avisarle al cliente. En verde, los niveles que cambiaron después del 1000.

Paso cuatro: el cliente vuelve y dice “tengo hasta el 1000”. El relay le manda solo esos tres niveles con su valor actual, y el cliente queda idéntico al relay. Como cada delta trae el valor nuevo, de 1.0, 1.5, 0.7 y 0.9 solo importa el 0.9.

Abajo, la comparación: Binance manda el libro entero, 2 000 niveles; Ably, un servicio de mensajería en tiempo real, reenvía los seis mensajes; nosotros, tres niveles. Y una regla de seguridad: si los cambios ya pesan tanto como el libro, el relay manda el libro completo. Reanudar nunca cuesta más que resincronizar. Nicolás les explica cómo se mantienen sincronizados los relays y cómo lo probamos.

## Nicolás, parte 2: réplicas, evaluación y resultados

### 11. Idea 3: réplicas por región · 8:45–9:50 (65 s)

Gracias, Pedro. La tercera idea: réplicas por región. Los relays funcionan como las réplicas de una base de datos: el origen es el líder, los relays son seguidores, y el feed numerado es el log de replicación. De ahí salen los cinco mecanismos de la derecha.

Uno, un solo orden: solo el origen numera, así que todos aplican lo mismo en el mismo orden; un relay puede ir atrasado, pero nunca inventa un libro. Dos, lag acotado: si un relay se atrasa más de 500 milisegundos, se marca como no saludable y sus clientes reanudan en otro relay de la región. Tres, gaps: si un relay pierde mensajes del feed, no le pide nada al origen; redirige a sus clientes o espera el snapshot que el feed manda cada segundo. Cuatro, checksum: una suma de verificación de los 10 mejores niveles detecta copias que divergen. Y cinco, conflation: a un cliente lento no se le corta; el relay le manda solo el último valor de cada nivel.

### 12. Hipótesis y cómo la medimos · 9:50–10:40 (50 s)

La hipótesis tiene dos partes, y cualquiera puede salir refutada. Parte uno: el contrato de Binance, con tráfico real acelerado diez veces, sigue degradado cuando termina el pico. Parte dos: en las mismas condiciones, RelayBook cumple tres metas, y el resume estilo Ably tiene más atraso, porque cada recuperación arrastra todos los mensajes perdidos.

Las metas son tres. Full resync: qué fracción de las reconexiones termina en un libro completo; menos del 1 %. Time to recover: cuánto tarda el 99 % de los clientes en volver a tener un libro válido; 30 segundos o menos. Staleness p99: el atraso del libro del cliente; menos de un segundo.

### 13. Paso 1: datos reales y un prototipo del relay · 10:40–11:30 (50 s)

Para probarlo no inventamos el tráfico. Grabamos 70 minutos del stream público de profundidad de Binance Futures para BTC/USDT, el 13 de noviembre: 41 113 mensajes, sin perder ninguno. Llegan casi diez por segundo, y cada uno cambia en promedio 275 niveles. El snapshot tenía 2 000 niveles y pesaba 41 KB.

Con esa grabación construimos un prototipo del relay, que aplica cada delta y guarda por nivel el último mensaje y las lápidas. Lo validamos con 46 reconexiones al azar: en las 46, el libro del cliente quedó idéntico al del relay, tanto en el checksum como en los 100 mejores niveles de cada lado.

### 14. Paso 2: ¿cuánto pesa recuperar a un cliente? · 11:30–12:30 (60 s)

Primer experimento: ¿cuánto pesa recuperar a un cliente? Sobre la grabación, a ritmo normal, desconectamos clientes en momentos al azar, por 1 a 60 segundos, y medimos cuánto hay que mandarle con cada diseño. El gráfico está en escala logarítmica.

La línea roja punteada es el snapshot de Binance: siempre 41 KB. La gris es el estilo Ably: crece porque reenvía cada mensaje, y llega a 3.4 MB tras un minuto. La verde es nuestro resume por estado: tras un segundo fuera, 15 KB, un 63 % menos que el snapshot. Entre 5 y 10 segundos ya cambiaron tantos niveles que el relay manda el snapshot, así que nunca pagamos más que el libro. Frente a Ably, entre 3 y 84 veces menos. Funciona porque muchos mensajes vuelven a tocar los mismos niveles: en 10 segundos llegan unas 27 000 actualizaciones, pero solo a unos 2 800 niveles distintos.

### 15. Paso 3: simulamos la tormenta · 12:30–13:25 (55 s)

Segundo experimento, el central: simular la tormenta. El tiempo avanza en pasos de 100 milisegundos y cada servidor reparte su capacidad entre sus conexiones. Reproducimos la grabación en tres fases: cinco minutos normales, cinco a diez veces y diez normales, para ver si el sistema se recupera solo. Al inicio del pico se desconecta el 30 % de los 2 000 clientes, y el 30 % tiene internet lento.

Si una conexión acumula 1 MB pendiente, Binance y Ably la cortan; RelayBook aplica conflation desde los 256 KB. El estilo Ably corre sobre los mismos relays, así que solo cambia cómo reanuda. Dos cosas no las conocemos de Binance: cuánta capacidad le sobra y cuánto le cuesta generar un snapshot. Así que probamos varios valores: seis capacidades por tres costos, 18 corridas.

### 16. Resultados de la tormenta (capacidad 3×) · 13:25–14:15 (50 s)

Esta tabla es con una capacidad de tres veces la carga normal. Binance con snapshot barato se recupera al instante, pero durante el pico su atraso llega a 3.6 segundos; con snapshot caro tarda 38 segundos o no se recupera. RelayBook se recupera en cero segundos, con 1.1 segundos de atraso, y el origen carga 0.3 MB por segundo contra 120 de Binance: 400 veces menos.

En la línea de abajo, durante el pico Binance tuvo 164 mil reconexiones y RelayBook 629, porque a los lentos no se les corta. El estilo Ably llegó a 120 segundos de atraso, así que esa predicción se cumplió. Pero la columna de full resync dice 100 % para RelayBook. Vamos a ver las dos partes de la hipótesis.

### 17. Parte 1: Binance solo cae si el snapshot es caro · 14:15–15:15 (60 s)

Parte uno: ¿el contrato de Binance sigue degradado tras el pico? Esta grilla son sus 18 corridas: capacidad en columnas, costo del snapshot en filas, y en cada celda cuánto tardó en recuperarse. Con snapshot barato, la fila de arriba, siempre se recupera en 11 segundos o menos: no hay falla metaestable. Con snapshot caro y poca capacidad sobrante, en rojo oscuro, no se recupera en los diez minutos que observamos: 5 de 18 corridas.

Ahí se ve el efecto sostenedor del que habló Pedro: el origen sigue generando snapshots para clientes que ya los abandonaron porque reintentaron, y llegó a gastar 146 GB en eso. Como no sabemos cuánto le cuesta a Binance un snapshot, esto dice en qué condiciones el contrato es vulnerable, no que Binance falle. La parte uno se cumple solo en esas condiciones.

### 18. Parte 2: ¿por qué 100 % de full resync? · 15:15–16:35 (80 s)

Parte dos: ¿RelayBook cumple las tres metas? Cumplió el tiempo de recuperación, quedó cerca en el atraso y falló en full resync. Este gráfico explica por qué. En el eje horizontal, cuántos mensajes se perdió el cliente; en el vertical, cuántos niveles distintos cambiaron. La línea roja es el tamaño del libro, 2 000 niveles.

A ritmo normal, un segundo son unos 10 mensajes que tocan unos 1 100 niveles: menos que el libro, y el resume por estado gana. En el pico a diez veces, un segundo son unos 100 mensajes que tocan unos 2 800 niveles, más que el libro entero. Entonces se activa la regla de seguridad y el relay manda el snapshot: por eso el 100 %.

Lo importante es que ese snapshot sale del relay, no del origen, y fueron solo 629. El atraso quedó entre 1.1 y 1.3 segundos por los clientes lentos. La conclusión honesta: la mejora de RelayBook no vino de recuperaciones más chicas, sino de dónde se recupera y de la conflation.

### 19. Conclusión y trabajo futuro · 16:35–17:20 (45 s)

Para cerrar. En la hipótesis: tiempo de recuperación cumplido, atraso cerca y full resync refutado. El contrato de Binance solo queda caído con snapshots caros y poca capacidad, y RelayBook se recupera de inmediato sin cargar al origen.

Como trabajo futuro: medir cuánto cuesta de verdad generar un snapshot, que es la gran incógnita; probar varios instrumentos y picos reales; desplegar relays en una red real; limitar cuánto guarda el relay las lápidas; y ajustar la conflation para bajar el atraso. Muchas gracias. ¿Preguntas?
