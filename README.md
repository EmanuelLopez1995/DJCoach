# DJ Coach

Monitor local del estado MIDI del mixer de Traktor. Por ahora no utiliza IA ni
analiza audio.

El estado y los próximos pasos del proyecto se mantienen en
[docs/ROADMAP.md](docs/ROADMAP.md). Los avisos actuales están documentados en
[docs/AVISOS_COACH.md](docs/AVISOS_COACH.md).
La separación de responsabilidades se explica en
[docs/PRODUCT_ARCHITECTURE.md](docs/PRODUCT_ARCHITECTURE.md).

## Dirección del producto

DJ Coach se está organizando alrededor de lecciones grabadas:

```text
Profesor mezcla en Traktor
→ DJ Coach registra una referencia
→ Alumno practica con los mismos tracks
→ DJ Coach compara la técnica y explica diferencias
```

Traktor continúa siendo el entorno donde se mezcla. La aplicación administra
tracks, lecciones, grabaciones, comparación y feedback.

## Ejecutar

Con `loopMIDI` abierto y el puerto `djCoach` disponible:

```powershell
python D:\DJCoach\dj_coach.py
```

Para mostrar el último mensaje MIDI crudo:

```powershell
python D:\DJCoach\dj_coach.py --debug
```

Para aislar problemas de entrada usando el lector bloqueante original:

```powershell
python D:\DJCoach\dj_coach.py --raw
```

Antes de abrir DJ Coach, cerrá otras instancias de `python dj_coach.py`; una
instancia anterior puede quedarse conectada al mismo puerto MIDI.

Al salir normalmente con `Ctrl+C`, la sesión se guarda en `sessions/` como JSON.

## Frontend web

La interfaz visual local reutiliza el mismo lector MIDI, estado, reglas y
grabador de sesiones. Se ejecuta dentro del entorno virtual `.venv`.

La forma más sencilla de iniciarla es hacer doble clic en:

```text
iniciar_frontend.bat
```

O desde PowerShell:

```powershell
D:\DJCoach\.venv\Scripts\python.exe D:\DJCoach\dj_coach_web.py
```

Se abre automáticamente en `http://127.0.0.1:8080`.

Rutas iniciales:

| Ruta | Función |
|---|---|
| `/` | Entrada del producto: Profesor, Alumno y diagnóstico |
| `/lessons/new` | Selección de tracks y creación de un borrador |
| `/lessons/{id}` | Preparación y verificación de ambos decks |
| `/lessons/{id}/record` | Grabación de la referencia MIDI del profesor |
| `/practice` | Biblioteca local de lecciones |
| `/monitor` | Dashboard técnico MIDI existente |

Para arrancarla sin abrir el navegador:

```powershell
D:\DJCoach\.venv\Scripts\python.exe D:\DJCoach\dj_coach_web.py --no-open
```

No ejecutes simultáneamente el frontend y `dj_coach.py`: ambos intentarían
escuchar el mismo puerto MIDI. Al cerrar el servidor con `Ctrl+C`, también se
guarda la sesión JSON.

## Mappings actuales

Todos están en el canal MIDI 1 de Traktor (`channel=0` en Mido).

| CC | Control |
|---:|---|
| 1–6 | Deck A: LOW, MID, HIGH, GAIN, FX/FILTER, VOLUME |
| 7–8 | Deck A: FX ON, CUE |
| 9–13 | Deck B: LOW, MID, HIGH, GAIN, FX/FILTER |
| 14–15 | Deck B: FX ON, CUE |
| 16 | Crossfader global |
| 17 | Deck B VOLUME |
| 18 | Deck A PLAY |
| 19 | Deck B PLAY |
| 20–21 | Deck A/B: DECK IS LOADED |
| 22–23 | Deck A/B: CUE de transporte |
| 24–25 | Deck A/B: IS IN ACTIVE LOOP |
| 26–27 | Deck A/B: SYNC ON |
| 28–29 | Deck A/B: PHASE |
| 30–31 | Deck A/B: BEAT PHASE |
| 32–33 | Deck A/B: SEEK POSITION / progreso de canción |
| 34–35 | Deck A/B: TRACK END WARNING |

## Lógica local actual

- Un valor se muestra como `---` hasta que Traktor lo envía por primera vez.
- Cada cambio conserva MIDI, porcentaje, valor normalizado y timestamp.
- La audibilidad es una **estimación** basada en Loaded, Play, volumen de canal
  y crossfader.
- Una transición comienza cuando ambos decks parecen audibles y termina tras un
  segundo fuera de esa condición.
- `bass_overlap`: ambos LOW por encima del 80% durante 1,5 segundos.
- `bass_gap`: ambos LOW por debajo del 25% durante 1,5 segundos.
- `transition_too_fast`: ambos decks dejan de solaparse antes de 4 segundos.
- `transition_too_slow`: ambos decks permanecen audibles durante 45 segundos.
- `beats_out_of_phase`: Phase se aleja al menos 12 unidades MIDI del centro
  durante un segundo. El aviso no afirma si el deck va adelantado o atrasado
  porque todavía falta calibrar la dirección real que informa Traktor.
- `phase_recovered`: después de un aviso de fase, confirma cuando ambos decks
  siguen audibles y Phase regresa a la zona central.
- `fader_abrupt_change`: el volumen de un deck o el crossfader recorre al menos
  el 45% en una ventana de 0,35 segundos.
- `track_end_warning`: Traktor informa que la canción de un deck está próxima a
  terminar.
- `silence_low_volumes`: los decks en PLAY tienen el volumen cerrado.
- `silence_crossfader`: el crossfader bloquea todos los decks activos con
  volumen abierto.
- `silence_eq_cut`: LOW, MID y HIGH están al mínimo en un deck activo.

Los avisos usan tiempos de permanencia y cooldowns para evitar falsos positivos
y mensajes repetidos. Se muestran durante seis segundos, quedan en el historial
del dashboard y se guardan en el JSON de sesión con un resumen por regla.

Todavía no se pueden evaluar con los mappings actuales: clipping, calidad de
audio, estructura/fraseo musical ni tiempo restante exacto en minutos. Esos
avisos requieren nuevos datos de Traktor o análisis de audio.

Play ya confirma el estado de reproducción de Traktor. La estimación todavía no
mide señal de audio real; para eso harán falta medidores de deck o análisis de
audio.

Phase y Beat Phase se conservan como MIDI crudo, normalizado y porcentaje. Como
pueden emitir a alta frecuencia, el estado procesa todos los mensajes, el
dashboard se limita a 20 actualizaciones por segundo y la sesión muestrea esos
CC a 10 eventos por segundo.

El Master Clock MIDI no usa CC: Traktor envía 24 pulsos `clock` por beat. DJ
Coach mide el intervalo de esos pulsos para calcular y mostrar el BPM actual. Si
los pulsos se interrumpen durante medio segundo, el reloj se muestra detenido.
La estimación usa regresión sobre hasta 16 beats, una mediana de mediciones y
suavizado para evitar que el agrupamiento de mensajes de Windows/loopMIDI se
muestre incorrectamente como cambios de BPM.

Además, CC30 y CC31 (`Beat Phase`) completan un ciclo en cada beat. DJ Coach
detecta el salto real de valor alto a bajo observado en Traktor y calcula por
separado el BPM actual de Deck A y Deck B. Esto permite medir decks sin Sync y
compararlos posteriormente con el Master Clock.

Cuando un deck informa `SYNC ON`, el BPM mostrado usa directamente el Master
Clock, porque esa es la referencia efectiva de reproducción. Con Sync apagado,
se usa la medición independiente de Beat Phase, promediada sobre ciclos estables
para reducir el jitter de los valores MIDI discretos.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

## Estructura del proyecto

```text
djcoach/
  domain/       modelos Track, Lesson y Take
  lessons/      persistencia y servicios de lecciones
  tracks/       catálogo local de canciones
  web/          páginas del nuevo producto
data/
  tracks/demo/  audios locales de prueba, ignorados por Git
  lessons/      lecciones JSON locales
  takes/        referencias MIDI grabadas por el profesor
  attempts/     intentos de alumnos
docs/           roadmap, avisos y referencias de Traktor
tests/          pruebas automatizadas
```

Los archivos raíz `dj_coach.py`, `dj_coach_runtime.py` y `dj_coach_web.py`
continúan funcionando como motor MIDI, runtime y punto de entrada compatible.
