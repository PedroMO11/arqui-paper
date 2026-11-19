# Presentación en Overleaf

1. En Overleaf, elige **New Project → Upload Project** y sube el contenido de `slides/` conservando la carpeta `fig/`.
2. Selecciona `main.tex` como documento principal y el compilador **pdfLaTeX**. No requiere shell-escape.
3. Compila dos veces, para que el pie muestre el total de diapositivas (`n/19`). Revisa el log: no debe haber errores ni `Overfull` mayores a 5 pt.
4. Para ensayar con el guion, cambia `hide notes` por `show only notes` en `preamble.tex`. Antes de exponer, vuelve a `hide notes`.

## Reparto y tiempos (17:20 de 20:00)

| Bloque | Expone | Diapositivas | Tiempo |
|---|---|---|---|
| Contexto, problema, relays y state-based resume | Pedro | 1–10 | 0:00–8:45 |
| Réplicas, hipótesis, cómo lo probamos, resultados y conclusión | Nicolás | 11–19 | 8:45–17:20 |

El guion completo está en `GUION.md`, y cada diapositiva lo tiene también en su `\note{...}` con su minuto.
