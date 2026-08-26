# Avisos de DJ Coach

Esta guía describe los avisos que el Coach puede generar actualmente usando los
datos MIDI enviados por Traktor.

## Cómo decide si un deck es audible

Antes de evaluar una transición o los graves, DJ Coach estima si cada deck se
está escuchando. Para considerarlo audible necesita:

- una canción cargada (`LOADED`);
- reproducción activa (`PLAY`);
- volumen de canal por encima del 5%;
- que el crossfader no esté completamente cerrado hacia el deck contrario.

Es una estimación del estado del mixer. No confirma que exista señal de audio
real ni mide su volumen acústico.

## Avisos implementados

### Ambos graves abiertos

- **Regla interna:** `bass_overlap`
- **Condición:** Deck A y Deck B audibles, con ambos LOW por encima del 80%.
- **Tiempo requerido:** 1,5 segundos continuos.
- **Mensaje:** “Ambos graves están abiertos; bajá el LOW de uno de los decks.”
- **Objetivo:** evitar una mezcla cargada o embarrada en frecuencias graves.

### Falta de graves

- **Regla interna:** `bass_gap`
- **Condición:** Deck A y Deck B audibles, con ambos LOW por debajo del 25%.
- **Tiempo requerido:** 1,5 segundos continuos.
- **Mensaje:** “Los dos LOW están cerrados; recuperá gradualmente el grave de un deck.”
- **Objetivo:** detectar una pérdida prolongada de energía grave durante la mezcla.

### Transición demasiado rápida

- **Regla interna:** `transition_too_fast`
- **Condición:** termina el período en el que ambos decks eran audibles y la
  transición duró menos de 4 segundos.
- **Mensaje:** “La transición duró X.Xs; probá hacerla más progresiva.”
- **Objetivo:** señalar un cambio que podría sentirse abrupto.

El Coach espera un segundo para confirmar que la transición realmente terminó.
Ese segundo de confirmación no se suma a la duración informada.

### Transición demasiado larga

- **Regla interna:** `transition_too_slow`
- **Condición:** ambos decks permanecen audibles durante 45 segundos.
- **Mensaje:** “La transición lleva demasiado tiempo; definí qué deck queda sonando.”
- **Objetivo:** evitar que dos canciones permanezcan superpuestas sin una
  dirección clara durante demasiado tiempo.

### Posible desfase

- **Regla interna:** `beats_out_of_phase`
- **Condición:** ambos decks audibles y al menos un valor `PHASE` se aleja 12 o
  más unidades MIDI del centro aproximado (`63/64`).
- **Tiempo requerido:** 1 segundo continuo.
- **Mensaje:** “Deck A/B está fuera de fase (MIDI X); corregí la alineación.”
- **Objetivo:** advertir una posible desalineación rítmica.

Este aviso es **experimental**. Todavía no se calibró completamente cómo Traktor
representa la dirección de Phase, por eso el Coach no afirma si el deck está
adelantado o atrasado. Aunque se use Sync, puede servir para detectar una grilla
mal alineada o una corrección pendiente.

Si el Coach ya emitió este aviso y Phase vuelve a la zona central mientras ambos
decks continúan audibles, muestra la confirmación positiva: “BIEN: La fase volvió
a una zona alineada.” Detener un deck o cerrar su volumen no cuenta como una
corrección de fase.

### Movimiento abrupto de un fader

- **Regla interna:** `fader_abrupt_change`
- **Controles observados:** volumen del Deck A, volumen del Deck B y crossfader.
- **Condición:** el control recorre al menos el 45% de su rango en 0,35 segundos.
- **Mensaje:** “Movimiento abrupto en [control]; hacé el cambio más gradual.”
- **Objetivo:** detectar cambios de nivel o de deck potencialmente bruscos.

Los volúmenes se evalúan solamente cuando su deck está cargado y reproduciendo.
El crossfader se evalúa cuando al menos uno de los decks está cargado y
reproduciendo.

### Canción próxima a terminar

- **Regla interna:** `track_end_warning`
- **Condición:** Traktor activa `Track End Warning` para el Deck A o Deck B.
- **Mappings:** CC34 para Deck A y CC35 para Deck B.
- **Mensaje:** “La canción del Deck A/B está por terminar; prepará la transición.”
- **Objetivo:** dar tiempo para cargar o iniciar la siguiente canción.

El momento exacto del aviso depende de la configuración y del comportamiento de
`Track End Warning` dentro de Traktor.

### Riesgo de silencio por volumen

- **Regla interna:** `silence_low_volumes`
- **Condición:** hay al menos un deck cargado y en PLAY, y todos los decks que
  están reproduciendo tienen su VOLUME por debajo o igual al 5%.
- **Tiempo requerido:** 0,75 segundos continuos.
- **Mensaje:** “Riesgo de silencio: los decks en PLAY tienen el VOLUME cerrado.”

### Riesgo de silencio por crossfader

- **Regla interna:** `silence_crossfader`
- **Condición:** uno o más decks están cargados y en PLAY con volumen abierto,
  pero el crossfader está completamente hacia el lado que los bloquea.
- **Tiempo requerido:** 0,75 segundos continuos.
- **Mensaje:** indica específicamente qué deck está bloqueando el crossfader.

### Riesgo de silencio por EQ

- **Regla interna:** `silence_eq_cut`
- **Condición:** un deck está cargado, en PLAY, con volumen y crossfader
  abiertos, pero LOW, MID y HIGH están simultáneamente al 5% o menos.
- **Tiempo requerido:** 0,75 segundos continuos.
- **Mensaje:** “Riesgo de silencio en Deck A/B: LOW, MID y HIGH están al mínimo.”

Estos tres avisos indican un **riesgo estimado**. No garantizan silencio real,
porque algunos modelos de EQ de Traktor pueden no cortar completamente todas
las frecuencias y DJ Coach todavía no recibe un medidor de señal de audio.

## Estados informativos

Además de los avisos, la pantalla puede mostrar estos estados:

- `Esperando LOADED, PLAY, VOLUME y CROSSFADER...`: todavía faltan datos para
  calcular la audibilidad.
- `Transición en curso...`: ambos decks parecen audibles.
- `Mixer estable. Sin avisos.`: hay datos suficientes y ninguna regla está
  disparada.

## Cómo se evitan avisos repetidos

- Los avisos permanecen destacados durante 6 segundos.
- Graves y Phase tienen un cooldown de 8 segundos.
- Movimientos de fader tienen un cooldown de 5 segundos por control.
- Track End tiene un cooldown de 15 segundos por deck.
- Los riesgos de silencio tienen un cooldown de 8 segundos.
- Una misma condición normalmente debe desaparecer antes de volver a generar
  otro aviso.
- El frontend y la terminal muestran los avisos recientes.
- Los JSON de sesión guardan cada aviso y un resumen en `warnings_by_rule`.

## Datos visibles que no generan avisos todavía

- MID y HIGH.
- GAIN.
- FX/FILTER y FX ON.
- Monitor Cue y Cue Play.
- Loop y Sync.
- Beat Phase.
- Posición porcentual de la canción (`Seek Position`, CC32/CC33).

Estos datos se reciben y se muestran, pero todavía no existe una regla fiable
que determine por sí sola si su uso musical es correcto o incorrecto.

## Avisos que aún no son posibles

Con los mappings actuales todavía no se puede evaluar de forma fiable:

- clipping o saturación real;
- volumen acústico real de cada canción;
- calidad del audio;
- fraseo y estructura musical;
- compatibilidad armónica;
- tiempo restante exacto en minutos y segundos;
- elección artística de efectos, loops o ecualización.

Para esas funciones harán falta más salidas de Traktor, metadatos de las pistas
o análisis directo del audio.
