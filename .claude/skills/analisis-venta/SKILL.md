---
name: analisis-venta
description: Analiza si una o varias posiciones del portafolio de Matías deberían venderse. Úsalo SIEMPRE que se discuta vender, trimear, rotar o liberar liquidez de una posición existente — nunca improvises el razonamiento desde cero en el chat. Invocar con /analisis-venta o cuando el usuario pregunte "qué vendo", "debería vender X", "cómo liberar liquidez", etc.
---

# Análisis de venta — proceso obligatorio

Este skill existe porque el 15 de julio de 2026 se dio una recomendación
contradictoria: vender PANW después de establecer con datos que PANW era
fundamentalmente MEJOR que CRWD (P/E 45x vs 91x, margen FCF 37,6% vs 25,7%),
usando el momentum técnico de PANW como justificación. Fue un error real de
razonamiento, no una diferencia de opinión — dos criterios distintos
(fundamentales vs timing técnico) se mezclaron sin verificar que apuntaran
en la misma dirección.

**Fuente de verdad**: `intelligence/config/investor_profile.yaml`, sección
`criterios_venta`. Este skill OPERACIONALIZA esa política — léela primero,
completa siempre, no la resumas de memoria.

## Regla de Matías (cítala, no la parafrasees mal)

> "No vendo solo por rentabilidad, a no ser que la industria o mi tesis ya
> no tenga sentido en esa posición, o que sea clarísimo que hay que vender
> para tomar ganancias."

## Proceso — en este orden, sin saltarse pasos

Para CADA ticker candidato, completa las 3 preguntas en orden. Detente en
la primera que dé un "sí" con evidencia real — no sigas buscando razones
adicionales para justificar una conclusión ya tomada.

### 1. ¿La tesis está rota?
Lee la vertical del ticker en `investor_profile.yaml` (campo `tesis` y
`horizonte_venta`). Pregunta: ¿la razón original por la que existe esta
posición sigue siendo cierta hoy? Si no — vender, punto, sin importar
timing técnico ni ganancia/pérdida actual.

### 2. ¿Hay una señal OBJETIVA de toma de ganancias?
NO cuenta por sí sola: "subió mucho", "está cerca de su máximo", "RSI
alto". Eso es la posición comportándose bien (O'Neil: "si actúa bien, deja
correr el resto"). SÍ cuenta: valoración desconectada de fundamentales
(PEG >> 1 con crecimiento desacelerando — verifica con datos reales, no
asumas), o extensión fuerte CON signos reales de agotamiento (no solo "está
arriba"). Si aplica: sugiere toma de ganancias PARCIAL (25-30%), no venta
total automática.

### 3. ¿Solapa con otra posición de MAYOR convicción declarada?
Si el ticker cumple el mismo rol temático que otra posición que Matías ya
declaró como convicción más alta (ej. ambos son "el pick de ciberseguridad"
o "el pick de GLP-1"):
  a. Identifica AMBOS tickers en conflicto.
  b. Pull datos reales de AMBOS en LAS MISMAS métricas: P/E forward,
     margen (FCF o neto), crecimiento de ingresos, ROE. Usa yfinance
     (`.info`), nunca la memoria/entrenamiento.
  c. Determina cuál gana la comparación en la mayoría de las métricas.
  d. **La recomendación es vender la que PIERDE la comparación — nunca
     la que gana, sin importar qué tan bueno se vea su momentum técnico.**
     Si el momentum técnico de la que gana es fuerte, eso es una razón
     para venderla MENOS, no más.

## Uso del timing técnico (RSI, momentum, distancia de máximo)

Solo entra DESPUÉS de que 1, 2 o 3 ya justificaron una venta. Sirve para
decidir CUÁNDO ejecutar (vender en fortaleza en vez de pánico), nunca para
decidir SI vender. Si no hay justificación de 1-3, el timing técnico NO
es suficiente por sí solo — dilo explícitamente en vez de usarlo como
justificación de respaldo.

## Antes de responder — auto-chequeo obligatorio

Antes de escribir la recomendación final, relee lo que vas a decir y
verifica: ¿algún argumento que di (fundamentales, timing, comparación)
contradice la conclusión? Si dijiste "X es mejor que Y" en algún punto,
¿la recomendación final es consistente con eso? Si hay contradicción,
corrígela ANTES de mostrarla — no dejes que el usuario la encuentre.

## Formato de salida

Para cada ticker: cuál de los 3 pasos activó la recomendación (cítalo
explícitamente: "Paso 3: solapa con LLY"), los datos reales que lo
sustentan, y si el caso es limpio o tiene matices (ej. trade-off
growth-vs-value real, no un barrido limpio). Si un ticker NO cumple
ninguno de los 3 pasos, dilo explícitamente — "no cumple el criterio,
no se recomienda vender" — en vez de omitirlo en silencio.
