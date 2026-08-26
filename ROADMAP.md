# Roadmap de DJ Coach

Este archivo sirve como lista de trabajo del proyecto. Se actualiza marcando las
casillas a medida que cada función queda implementada y probada físicamente con
Traktor.

## Leyenda

- [x] Implementado y comprobado.
- [ ] Pendiente.
- **Experimental:** funciona, pero todavía necesita calibración o más sesiones
  reales.

## 1. Conexión e infraestructura

- [x] Proyecto compatible con Python 3.12.
- [x] Conexión automática al puerto MIDI que contiene `djCoach`.
- [x] Modo `--raw` para diagnosticar mensajes MIDI.
- [x] Modo `--debug` para ver el último mensaje recibido.
- [x] Lector MIDI en segundo plano para consola y frontend.
- [x] Estado desconocido `---` diferenciado de un valor MIDI real igual a cero.
- [x] Pruebas automatizadas.
- [x] Guardado de sesiones JSON.
- [x] Frontend web local con NiceGUI.
- [x] Script `iniciar_frontend.bat`.

## 2. Estado del mixer

- [x] Deck A: LOW, MID, HIGH, GAIN, FX/FILTER y VOLUME.
- [x] Deck B: LOW, MID, HIGH, GAIN, FX/FILTER y VOLUME.
- [x] FX ON de ambos decks.
- [x] Monitor Cue de ambos decks.
- [x] Crossfader global.
- [x] Conservación de MIDI, valor normalizado y porcentaje.
- [x] Estimación local de audibilidad por deck.
- [ ] Medidor de señal real del Deck A.
- [ ] Medidor de señal real del Deck B.
- [ ] Medidor de salida Master.
- [ ] Detección real de clipping o saturación.

Los puntos pendientes requieren mappings de medidores disponibles en Traktor o
captura/análisis de audio. El estado actual solo estima la audibilidad mediante
Play, Loaded, volumen y crossfader.

## 3. Transporte y estado de las canciones

- [x] Loaded de ambos decks.
- [x] Play/Pause de ambos decks.
- [x] Cue de transporte de ambos decks.
- [x] Loop activo de ambos decks.
- [x] Sync de ambos decks.
- [x] Track End Warning de ambos decks.
- [x] Posición porcentual mediante Seek Position.
- [x] Barra de progreso en el frontend.
- [ ] Nombre y artista del track cargado en cada deck.
- [ ] Ruta del archivo cargado en cada deck.
- [ ] Duración total de cada canción.
- [ ] Tiempo transcurrido y restante en minutos/segundos.
- [ ] Detectar saltos de posición, BeatJump y Hotcues de forma explícita.
- [ ] Conocer tamaño y posición exacta de un loop.

## 4. Tempo, beats y compases

- [x] Phase de ambos decks.
- [x] Beat Phase de ambos decks.
- [x] Recepción de MIDI Clock desde Traktor.
- [x] BPM estabilizado del Master Clock.
- [x] BPM actual individual de cada deck mediante Beat Phase.
- [x] Uso del Master BPM cuando el deck tiene Sync activo.
- [x] Uso de la medición independiente cuando Sync está apagado.
- [x] Identificación interna de cada nuevo beat mediante el ciclo de Beat Phase.
- [x] Mostrar un contador de beats por deck en el frontend.
- [ ] Reiniciar correctamente la cuenta al usar Cue, Seek, loops o BeatJump.
- [x] Identificar el downbeat mediante marcado manual del próximo beat.
- [ ] Identificar automáticamente el downbeat desde Traktor o el análisis.
- [x] Mostrar `beat 1/4`, `2/4`, `3/4` y `4/4`.
- [x] Contar compases desde el downbeat marcado.
- [x] Contar bloques de 4, 8, 16 y 32 compases.
- [ ] Detectar o configurar canciones que no estén en 4/4.
- [ ] Comparar BPM individual contra Master y avisar deriva real.

### Próximo paso recomendado

Hacer que Cue, Seek, loops y BeatJump mantengan o reinicien correctamente el
contador. Después se podrá intentar obtener o inferir automáticamente el
downbeat desde Traktor o desde el análisis de la canción.

## 5. BPM original y metadatos

- [ ] Obtener el BPM original analizado de cada canción.
- [ ] Distinguir claramente BPM original y BPM actual reproducido.
- [ ] Calcular el porcentaje de aceleración o desaceleración.
- [ ] Avisar si el cambio de tempo supera un umbral configurable.
- [ ] Leer título, artista, duración, tonalidad y BPM desde los archivos.
- [ ] Investigar lectura segura de la colección de Traktor.
- [ ] Asociar automáticamente el archivo correcto con Deck A y Deck B.
- [ ] Incorporar una selección manual de track como alternativa inicial.

Esta etapa es necesaria porque los mappings MIDI actuales no entregan el nombre
ni la ruta del archivo, y `Tempo Adjust` no equivale por sí solo al BPM original.

## 6. Análisis de onda y estructura musical

- [ ] Elegir una carpeta o biblioteca de canciones para analizar.
- [ ] Crear un analizador offline que no interfiera con la sesión en vivo.
- [ ] Guardar resultados en una caché JSON por canción.
- [ ] Detectar beats y comparar el resultado con el Beatgrid de Traktor.
- [ ] Calcular una curva de energía.
- [ ] Detectar posibles intros y outros.
- [ ] Detectar breakdowns, subidas y drops.
- [ ] Estimar límites de frases musicales.
- [ ] Estimar presencia de voces para evitar superposiciones vocales.
- [ ] Detectar tonalidad para mezcla armónica.
- [ ] Mostrar una forma de onda o línea temporal estructural en el frontend.
- [ ] Sincronizar el mapa analizado con Seek Position y los beats en vivo.

El análisis será probabilístico: debe presentar recomendaciones, no afirmar que
una decisión artística es obligatoriamente correcta o incorrecta.

## 7. Motor del Coach

### Implementado

- [x] Aviso por ambos graves abiertos.
- [x] Aviso por ambos graves cerrados.
- [x] Transición demasiado rápida.
- [x] Transición demasiado larga.
- [x] Posible desfase.
- [x] Confirmación cuando la fase vuelve a alinearse.
- [x] Movimiento abrupto de volumen o crossfader.
- [x] Canción próxima a terminar.
- [x] Riesgo de silencio por volumen cerrado.
- [x] Riesgo de silencio por crossfader bloqueando un deck activo.
- [x] Riesgo de silencio por LOW, MID y HIGH al mínimo.
- [x] Cooldowns para evitar avisos repetidos.
- [x] Historial visual y registro por sesión.

La interpretación de la dirección de Phase continúa **experimental**: todavía
no se afirma si un deck va adelantado o atrasado.

### Pendiente

- [ ] Avisar deriva de BPM solamente cuando sea persistente y significativa.
- [ ] Confirmar positivamente cuando el BPM vuelve a sincronizarse.
- [ ] Recomendar el próximo beat o compás para iniciar una transición.
- [ ] Mostrar una cuenta regresiva en beats y compases.
- [ ] Recomendar intercambio de graves en una frontera de frase.
- [ ] Avisar si dos drops importantes van a superponerse.
- [ ] Avisar superposición probable de voces.
- [ ] Recomendar intro/outro compatibles.
- [ ] Considerar diferencia de energía entre las canciones.
- [ ] Considerar compatibilidad armónica.
- [ ] Permitir perfiles de Coach: conservador, equilibrado y creativo.
- [ ] Permitir configurar o desactivar cada regla y sus umbrales.

## 8. Frontend y revisión de sesiones

- [x] Dashboard de ambos decks.
- [x] Crossfader visual.
- [x] Barras de progreso.
- [x] Master BPM y BPM por deck.
- [x] Estado de controles booleanos.
- [x] Mensaje principal del Coach.
- [x] Historial de avisos recientes.
- [ ] Pantalla de configuración de reglas y umbrales.
- [ ] Pantalla para seleccionar o asociar canciones con los decks.
- [ ] Vista rítmica con beat, compás y frase.
- [ ] Vista de estructura/onda de cada canción.
- [ ] Historial completo de la sesión dentro del frontend.
- [ ] Resumen posterior con transiciones, avisos y mejoras sugeridas.
- [ ] Gráficos de evolución de volumen, EQ, crossfader y Phase.
- [ ] Exportación de un informe legible de la sesión.

## Orden de implementación sugerido

1. [x] Contador de beats y compases con downbeat manual.
2. [ ] Manejo de Cue, Seek y Loop dentro del contador.
3. [ ] Identificación manual del track y lectura de sus metadatos.
4. [ ] BPM original y porcentaje de cambio de tempo.
5. [ ] Analizador offline de energía y estructura.
6. [ ] Línea temporal sincronizada en el frontend.
7. [ ] Recomendaciones de transición por compás y frase.
8. [ ] Automatización de la identificación del track cargado.
9. [ ] Medidores o análisis de audio para clipping y señal real.

## Fuera de alcance por ahora

- Controlar Traktor automáticamente sin una decisión explícita del usuario.
- Mover faders, EQ o crossfader desde DJ Coach.
- Considerar una recomendación automática como una regla artística absoluta.
- Enviar audio, sesiones o biblioteca musical a servicios externos.
