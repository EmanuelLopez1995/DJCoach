# Roadmap de DJ Coach

Este archivo sirve como lista de trabajo del proyecto. Se actualiza marcando las
casillas a medida que cada función queda implementada y probada físicamente con
Traktor.

## Leyenda

- [x] Implementado y comprobado.
- [ ] Pendiente.
- **Experimental:** funciona, pero todavía necesita calibración o más sesiones
  reales.

## Nueva prioridad: lecciones grabadas

- [x] Mantener Traktor como superficie donde profesor y alumno mezclan.
- [x] Separar la entrada del producto y el monitor técnico `/monitor`.
- [x] Crear modelos versionados `TrackReference`, `Lesson` y `Take`.
- [x] Crear catálogo local con los dos tracks demo.
- [x] Crear persistencia JSON local para lecciones.
- [x] Crear pantalla Profesor para seleccionar tracks y guardar un borrador.
- [x] Crear biblioteca inicial de lecciones para el Alumno.
- [x] Pantalla de preparación con conexión MIDI, `Loaded` por deck y confirmación manual de nombres.
- [ ] Agregar verificación de downbeats antes de grabar.
- [ ] **Experimental:** grabar un reference take desde el runtime; implementado,
  pendiente de una prueba física completa con Traktor y la Z1.
- [ ] Guardar estado inicial y eventos con tiempo y beat musical.
- [x] Extraer y ordenar en una sola cronología los gestos de mixer,
  transporte y transición de una toma.
- [ ] Interpretar landmarks de alto nivel: entrada, bass swap, FX y salida.
- [x] Grabar un student attempt guiado y vinculado a la lección.
- [x] Mostrar una consigna actual y una próxima sin revelar la cronología completa.
- [x] Agrupar acciones simultáneas y mostrarlas en carriles Deck A, Deck B y Mixer.
- [x] Mantener visibles el momento anterior, el actual y el próximo.
- [x] Sincronizar el inicio de la guía con el primer `PLAY` de Deck A.
- [x] Comparar el estado inicial del alumno contra la referencia antes de practicar.
- [x] Guiar cada ajuste inicial y bloquear el intento hasta que coincida.
- [x] Representar la calibración como una Kontrol Z1: perillas, faders,
  crossfader y botones con posición actual/objetivo.
- [x] Revalidar atómicamente el mixer al pulsar Iniciar intento.
- [x] Impedir referencias nuevas cuando faltan valores MIDI iniciales esenciales.
- [ ] Comparar reference take contra student attempt con tolerancias.
- [ ] Mostrar feedback concreto por técnica.
- [ ] Permitir repetir y conservar el historial de intentos.
- [ ] Crear visualización Ghost después de validar la comparación.

La arquitectura de esta dirección está documentada en
[PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md). El inventario técnico que
sigue continúa siendo válido como infraestructura y backlog secundario.

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
- [x] Pantalla inicial para seleccionar canciones y crear una lección.
- [ ] Vista rítmica con beat, compás y frase.
- [ ] Vista de estructura/onda de cada canción.
- [ ] Historial completo de la sesión dentro del frontend.
- [ ] Resumen posterior con transiciones, avisos y mejoras sugeridas.
- [ ] Gráficos de evolución de volumen, EQ, crossfader y Phase.
- [ ] Exportación de un informe legible de la sesión.

## Orden de implementación actual

1. [x] Modelos, catálogo, borrador de lección y rutas del producto.
2. [x] Preparación inicial con verificaciones y avance guiado.
3. [ ] Grabación del reference take implementada; pendiente de validación física.
4. [x] Extracción inicial de gestos y revisión del profesor.
5. [ ] Interpretación de landmarks técnicos de alto nivel.
6. [x] Grabación guiada de un intento del alumno.
7. [ ] Calibrar con sesiones reales la comparación tolerante y el informe inicial.
8. [ ] Historial de reintentos.
9. [ ] Ghost visual.
10. [ ] Identificación automática del track cargado en Traktor.
11. [ ] Análisis musical avanzado de archivos y audio.

## Fuera de alcance por ahora

- Controlar Traktor automáticamente sin una decisión explícita del usuario.
- Mover faders, EQ o crossfader desde DJ Coach.
- Considerar una recomendación automática como una regla artística absoluta.
- Enviar audio, sesiones o biblioteca musical a servicios externos.
