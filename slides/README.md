# Presentación en Overleaf

1. En Overleaf, elige **New Project → Upload Project** y sube el contenido de `slides/` conservando la carpeta `fig/`.
2. Selecciona `main.tex` como documento principal y el compilador **pdfLaTeX**. No requiere shell-escape.
3. Compila dos veces, para que el pie muestre el total de diapositivas (`n/20`). Revisa el log: no debe haber errores ni `Overfull` mayores a 5 pt.
4. Para ensayar con el guion, cambia `hide notes` por `show only notes` en `preamble.tex`. Antes de exponer, vuelve a `hide notes`.

## Reparto y tiempos (19:30 de 20:00)

| Bloque | Expone | Diapositivas | Tiempo |
|---|---|---|---|
| Contexto: exchange, order book, market data, Binance hoy | Pedro | 1–6 | 0:00–4:20 |
| Problema: tormenta, falla metaestable, evidencia | Pedro | 7–9 | 4:20–7:05 |
| Propuesta: relays, state-based resume, réplicas por región, hipótesis | Nicolás | 10–13 | 7:05–11:40 |
| Cómo lo probamos: datos reales, tamaño, simulación | Pedro | 14–16 | 11:40–14:45 |
| Resultados, por qué falló en parte, conclusión | Nicolás | 17–20 | 14:45–19:30 |

Cada diapositiva tiene su guion y su minuto exacto en `\note{...}`.
