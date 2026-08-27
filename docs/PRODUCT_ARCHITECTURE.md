# Arquitectura del producto

## Decisión principal

El profesor y el alumno mezclan en **Traktor**. DJ Coach no intenta reemplazar
la interfaz ni el motor de audio de Traktor: observa MIDI, organiza lecciones,
graba ejecuciones y compara técnicas.

```text
Traktor
  acciones reales del DJ
        ↓ MIDI
DJ Coach Runtime
  estado + reloj musical
        ↓
Take Recorder
  referencia del profesor o intento del alumno
        ↓
Feature Extractor
  entrada, curvas, bass swap, FX y salida
        ↓
Comparator
  diferencias con tolerancias musicales
        ↓
Feedback
  observaciones concretas de la técnica
```

## Contextos principales

### MIDI y ritmo

Responsable de recibir Traktor, mantener el estado del mixer y expresar eventos
en tiempo cronológico y musical. El monitor `/monitor` permite inspeccionarlo
sin mezclarlo con la experiencia principal del producto.

### Tracks

Indexa canciones locales y crea referencias reproducibles. El MVP utiliza una
ruta local y SHA-256 para garantizar que profesor y alumno elijan los mismos
archivos. Los audios no se incluyen en Git.

### Lessons

Una `Lesson` define nombre, descripción, dos tracks y la ejecución de referencia
del profesor. Su formato JSON incluye `schema_version` para permitir migraciones.

### Takes

Un `Take` es una ejecución grabada. Puede tener rol `teacher` o `student` y
contiene estado inicial, eventos y características técnicas extraídas.

### Evaluation

Comparará un take del alumno contra la referencia de la lección. Trabajará con
landmarks y curvas tolerantes, no con igualdad exacta entre valores MIDI.

### Práctica guiada

La referencia aprobada se transforma en `GuidanceMoment`: una ventana musical
que puede contener varias acciones coordinadas. La interfaz conserva un solo
reloj, pero divide cada momento en carriles Deck A, Deck B y Mixer. Las acciones
simultáneas se completan independientemente y la vista solo revela el momento
anterior, el actual y el próximo.

Antes de iniciar, un contrato de estado compara el mixer actual contra el
`initial_state` de la referencia: EQ, Gain, Filter, volúmenes, transporte,
Crossfader, posición de tracks y Master Clock/BPM. Los continuos aceptan una
tolerancia pequeña y los estados ON/OFF deben coincidir exactamente. La misma
validación se repite al pulsar Iniciar para evitar cambios entre pantallas.

## Persistencia local

```text
data/tracks/demo/   canciones locales de prueba
data/lessons/       definición de lecciones
data/takes/         tomas de referencia del profesor
data/attempts/      intentos de alumnos
sessions/           sesiones del monitor anterior
```

Los JSON de `lessons`, `takes` y `attempts`, así como los audios, son datos
locales y no se versionan. Los modelos y sus esquemas sí forman parte del
código.

## Compatibilidad durante la migración

Los puntos de entrada actuales permanecen operativos:

- `dj_coach.py`: consola y motor MIDI existente.
- `dj_coach_runtime.py`: runtime compartido.
- `dj_coach_web.py`: servidor web.

La lógica nueva se incorpora dentro del paquete `djcoach/`. Cuando el flujo de
lecciones esté estable, el motor MIDI podrá moverse internamente al paquete
manteniendo wrappers compatibles en la raíz.

## Alcance inmediato

1. Crear una lección con dos tracks locales.
2. Preparar y grabar una referencia del profesor.
3. Extraer entrada, volumen, LOW/bass swap, FX, crossfader y salida.
4. Grabar un intento del alumno.
5. Comparar ambos en beats con tolerancias.
6. Mostrar feedback concreto y permitir reintentar.

La práctica guiada presenta los mismos momentos y outcomes del motor mediante
una capa pedagógica: agrupa movimientos por intención, prioriza la acción actual,
resume solamente el siguiente momento y mantiene una timeline compacta. Esta
capa no cambia el orden, las tolerancias ni la detección MIDI de las consignas.
El mixer pedagógico consume el snapshot vivo del mismo runtime: el indicador del
alumno representa el MIDI actual y el ghost representa el target almacenado en
la acción del profesor. La futura trayectoria animada podrá extender este
componente sin modificar el contrato de evaluación existente.

No se agrega IA, cloud ni análisis avanzado de audio hasta completar este ciclo.
