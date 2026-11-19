# Presentación en Overleaf

1. En Overleaf se crea un proyecto con **New Project → Upload Project** y se sube el contenido de `slides/` con la carpeta `fig/`.
2. El documento principal es `main.tex` y el compilador es pdfLaTeX, sin shell-escape.
3. Se compila dos veces para que el pie muestre el total de diapositivas (`n/19`). El log no debe tener errores ni `Overfull` mayores a 5 pt.
4. Para ensayar con el guion se cambia `hide notes` por `show only notes` en `preamble.tex`, y antes de exponer se vuelve a `hide notes`.

## Reparto y tiempos (17:20 de 20:00)

| Bloque | Expone | Diapositivas | Tiempo |
|---|---|---|---|
| Contexto, problema, relays y state-based resume | Pedro | 1–10 | 0:00–8:45 |
| Réplicas, hipótesis, evaluación, resultados y conclusión | Nicolás | 11–19 | 8:45–17:20 |

El guion completo está en `GUION.md`, y cada diapositiva lo repite en su `\note{...}` con su minuto.
