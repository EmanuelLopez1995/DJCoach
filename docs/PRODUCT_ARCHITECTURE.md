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

No se agrega IA, cloud ni análisis avanzado de audio hasta completar este ciclo.
