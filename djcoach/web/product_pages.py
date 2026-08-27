"""Páginas principales del producto, separadas del monitor técnico MIDI."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from nicegui import ui

from djcoach.config import DEMO_TRACKS_DIRECTORY, ensure_data_directories
from djcoach.domain import Lesson
from djcoach.lessons import (
    LessonRepository,
    ReferenceTakeRecorder,
    TakeRepository,
    AttemptRepository,
    GuidedPracticeRecorder,
    FEATURE_SCHEMA_VERSION,
    evaluate_preparation,
    extract_take_features,
)
from djcoach.tracks import TrackCatalog


PRODUCT_CSS = """
.product-page { width:min(1120px,calc(100vw - 32px)); margin:0 auto; padding:42px 0 70px; }
.product-header { margin-bottom:28px; }.product-header h1 { margin:5px 0 8px; font-size:42px; }.product-header p { max-width:760px; color:#95a2b3; font-size:16px; }
.product-kicker { color:#36d7ff; font-size:10px; font-weight:800; letter-spacing:.22em; }
.mode-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:18px; }.mode-card { min-height:210px; padding:22px; border:1px solid #263140; border-radius:18px; background:linear-gradient(160deg,#141b25,#0b1017); }.mode-card h2 { margin:12px 0 8px; }.mode-card p { min-height:62px; color:#8996a7; }.mode-card.teacher { border-top:2px solid #36d7ff; }.mode-card.student { border-top:2px solid #ff4fd8; }.mode-card.monitor { border-top:2px solid #ffb648; }
.lesson-form,.lesson-summary { padding:24px; border:1px solid #263140; border-radius:18px; background:#101720; }.lesson-form { display:grid; gap:16px; }.lesson-tracks { display:grid; grid-template-columns:1fr 1fr; gap:16px; }.lesson-list { display:grid; gap:12px; }.lesson-row { display:flex; justify-content:space-between; align-items:center; padding:16px; border:1px solid #263140; border-radius:13px; background:#101720; }.empty-library { padding:28px; border:1px dashed #344154; border-radius:14px; color:#8996a7; text-align:center; }
.steps { display:grid; gap:9px; margin:20px 0; }.step { padding:12px 14px; border-radius:10px; background:#0b1118; color:#aeb9c7; }.step strong { color:#36d7ff; margin-right:8px; }
.stage-chip { display:inline-flex; width:max-content; padding:6px 10px; border:1px solid #31506a; border-radius:999px; color:#7ddfff; font-size:11px; font-weight:800; letter-spacing:.08em; }
.prep-intro { color:#aeb9c7; line-height:1.55; }
.prep-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:18px 0; }
.track-check-card { padding:16px; border:1px solid #263140; border-radius:14px; background:#0b1118; }
.track-check-card .deck-name { color:#7ddfff; font-size:11px; font-weight:800; letter-spacing:.1em; }
.track-check-card .track-name { min-height:48px; margin:7px 0 12px; color:#f4f7fb; font-size:16px; line-height:1.4; }
.readiness-list { display:grid; gap:9px; padding:14px; border:1px solid #263140; border-radius:14px; background:#0b1118; }
.readiness-line { color:#aeb9c7; font-size:14px; }
.prep-note { padding:13px 15px; border-left:3px solid #ffb648; border-radius:8px; background:#17130c; color:#c9b58e; line-height:1.5; }
.prep-actions { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:18px; }
.ready-message { min-height:24px; color:#8fa0b5; }
.record-panel { display:grid; gap:14px; margin-top:18px; padding:18px; border:1px solid #263140; border-radius:14px; background:#0b1118; }
.record-status { font-size:20px; font-weight:800; color:#f4f7fb; }
.record-metrics { display:flex; flex-wrap:wrap; gap:10px; }.record-metric { min-width:145px; padding:12px; border:1px solid #263140; border-radius:10px; color:#aeb9c7; }.record-metric strong { display:block; margin-top:4px; color:#f4f7fb; font-size:18px; }
.record-help { color:#93a1b3; line-height:1.5; }
.review-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:18px 0; }.review-metric { padding:15px; border:1px solid #263140; border-radius:12px; background:#0b1118; color:#8fa0b5; }.review-metric strong { display:block; margin-top:5px; color:#f4f7fb; font-size:21px; }
.review-section { display:grid; gap:10px; margin-top:24px; }.review-section h2 { margin:0; font-size:19px; }.timeline-row { display:grid; grid-template-columns:80px 150px 1fr; gap:12px; align-items:center; padding:11px 13px; border:1px solid #263140; border-radius:10px; background:#0b1118; }.timeline-time { color:#7ddfff; font-family:monospace; }.timeline-target { color:#c8d2df; font-weight:700; }.timeline-detail { color:#94a2b3; }
.approval-panel { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:14px; margin-top:24px; padding:18px; border:1px solid #31506a; border-radius:14px; background:#0d1821; }.approval-state { color:#aeb9c7; }
.guidance-card { display:grid; gap:10px; margin:20px 0; padding:24px; border:1px solid #ff4fd8; border-radius:18px; background:linear-gradient(145deg,#18101b,#0b1118); }.guidance-state { color:#ff83e4; font-size:11px; font-weight:800; letter-spacing:.14em; }.guidance-action { min-height:58px; color:#fff; font-size:26px; font-weight:800; line-height:1.25; }.guidance-time { color:#ffb4ed; font-family:monospace; }.next-action { padding:14px; border:1px solid #263140; border-radius:11px; color:#93a1b3; background:#0b1118; }.practice-progress { color:#94a2b3; }
.moment-shell { display:grid; gap:9px; }.moment-title { color:#8fa0b5; font-size:10px; font-weight:800; letter-spacing:.14em; }.moment-lanes { display:grid; grid-template-columns:repeat(3,1fr); gap:9px; }.moment-lane { min-height:72px; padding:11px; border:1px solid #263140; border-radius:11px; background:#0b1118; }.moment-lane.deck-a { border-top:2px solid #36d7ff; }.moment-lane.deck-b { border-top:2px solid #ff4fd8; }.moment-lane.mixer { border-top:2px solid #ffb648; }.lane-title { margin-bottom:7px; color:#8996a7; font-size:10px; font-weight:800; letter-spacing:.1em; }.lane-action { display:flex; gap:7px; margin-top:5px; color:#edf2f7; line-height:1.35; }.lane-action.done { color:#58e5a3; }.lane-action.missed { color:#ffb648; }.moment-empty { color:#657386; }.moment-previous,.moment-next { padding:13px; border:1px solid #263140; border-radius:13px; background:#0b1118; opacity:.86; }.moment-current { padding:16px; border:1px solid #ff4fd8; border-radius:15px; background:#120d16; }
.result-score { color:#ff4fd8; font-size:48px; font-weight:900; }.result-row { display:grid; grid-template-columns:34px 1fr auto; gap:10px; align-items:center; padding:11px 13px; border:1px solid #263140; border-radius:10px; background:#0b1118; }.result-ok { color:#58e5a3; }.result-missed { color:#ffb648; }
@media(max-width:800px){.mode-grid,.lesson-tracks{grid-template-columns:1fr}.product-header h1{font-size:32px}}
@media(max-width:800px){.prep-grid,.review-grid,.moment-lanes{grid-template-columns:1fr}.timeline-row{grid-template-columns:70px 1fr}.timeline-detail{grid-column:1/-1}}
"""


CONTROL_LABELS = {
    "low": "LOW",
    "mid": "MID",
    "high": "HIGH",
    "gain": "GAIN",
    "fx_adjust": "FX / FILTER",
    "volume": "VOLUME",
    "crossfader": "CROSSFADER",
    "play": "PLAY",
    "transport_cue": "CUE PLAY",
    "loop_active": "LOOP",
    "sync": "SYNC",
    "fx_on": "FX ON",
    "cue": "MONITOR CUE",
    "loaded": "LOADED",
    "track_end": "TRACK END",
}


def format_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return "---"
    value = max(0, int(round(float(seconds))))
    minutes, remaining_seconds = divmod(value, 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"


def section_label(section: str | None) -> str:
    return {
        "deck_a": "Deck A",
        "deck_b": "Deck B",
        "mixer": "Mixer",
    }.get(section or "", section or "General")


def render_guidance_moment(
    moment: dict[str, Any] | None,
    title: str,
    variant: str,
) -> str:
    if moment is None:
        return (
            f'<div class="moment-shell moment-{variant}">'
            f'<div class="moment-title">{escape(title)}</div>'
            '<div class="moment-empty">---</div></div>'
        )
    lanes = []
    for section, css_class, label in (
        ("deck_a", "deck-a", "DECK A"),
        ("deck_b", "deck-b", "DECK B"),
        ("mixer", "mixer", "MIXER / GLOBAL"),
    ):
        actions = [
            action for action in moment["actions"] if action["section"] == section
        ]
        rendered_actions = []
        for action in actions:
            outcome = action.get("outcome")
            if outcome and outcome["status"] == "completed":
                icon, state_class = "✓", "done"
            elif outcome:
                icon, state_class = "△", "missed"
            else:
                icon, state_class = "○", ""
            rendered_actions.append(
                f'<div class="lane-action {state_class}"><span>{icon}</span>'
                f'<span>{escape(str(action["instruction"]))}</span></div>'
            )
        body = "".join(rendered_actions) or '<div class="moment-empty">Sin acción</div>'
        lanes.append(
            f'<div class="moment-lane {css_class}"><div class="lane-title">'
            f'{label}</div>{body}</div>'
        )
    return (
        f'<div class="moment-shell moment-{variant}">'
        f'<div class="moment-title">{escape(title)}</div>'
        f'<div class="moment-lanes">{"".join(lanes)}</div></div>'
    )


def product_shell(title: str, subtitle: str) -> None:
    ui.add_css(PRODUCT_CSS)
    with ui.element("header").classes("product-header"):
        ui.label("DJ COACH · LECCIONES GRABADAS").classes("product-kicker")
        ui.html(f"<h1>{title}</h1><p>{subtitle}</p>", sanitize=True)


def register_product_pages(runtime: Any) -> None:
    ensure_data_directories()
    catalog = TrackCatalog(DEMO_TRACKS_DIRECTORY)
    repository = LessonRepository()
    take_repository = TakeRepository()
    attempt_repository = AttemptRepository()
    reference_recorder = ReferenceTakeRecorder(
        runtime, repository, take_repository
    )
    guided_practice = GuidedPracticeRecorder(
        runtime, repository, take_repository, attempt_repository
    )

    @ui.page("/")
    def home_page() -> None:
        ui.add_css(PRODUCT_CSS)
        with ui.column().classes("product-page"):
            product_shell(
                "Aprendé una técnica. Intentala. Comparala.",
                "El profesor mezcla en Traktor; DJ Coach registra su técnica para que el alumno pueda practicarla con los mismos tracks.",
            )
            with ui.element("div").classes("mode-grid"):
                with ui.element("section").classes("mode-card teacher"):
                    ui.label("PROFESOR").classes("product-kicker")
                    ui.html("<h2>Grabar lección</h2><p>Elegí dos tracks y prepará una demostración de referencia.</p>")
                    ui.button(
                        "NUEVA LECCIÓN",
                        on_click=lambda: ui.navigate.to("/lessons/new"),
                    )
                with ui.element("section").classes("mode-card student"):
                    ui.label("ALUMNO").classes("product-kicker")
                    ui.html("<h2>Practicar</h2><p>Elegí una lección e intentá replicar la técnica del profesor.</p>")
                    ui.button(
                        "VER LECCIONES",
                        on_click=lambda: ui.navigate.to("/practice"),
                    )
                with ui.element("section").classes("mode-card monitor"):
                    ui.label("DIAGNÓSTICO").classes("product-kicker")
                    ui.html("<h2>Monitor MIDI</h2><p>Revisá en tiempo real todos los datos que llegan desde Traktor.</p>")
                    ui.button(
                        "ABRIR MONITOR",
                        on_click=lambda: ui.navigate.to("/monitor"),
                    )

    @ui.page("/lessons/new")
    def new_lesson_page() -> None:
        paths = catalog.list_paths()
        options = {str(path): path.stem for path in paths}
        with ui.column().classes("product-page"):
            product_shell(
                "Nueva lección",
                "Seleccioná los tracks que vas a cargar manualmente en Traktor. La grabación de referencia se conectará a este borrador.",
            )
            ui.button("← INICIO", on_click=lambda: ui.navigate.to("/")).props("flat")
            with ui.element("section").classes("lesson-form"):
                name = ui.input("Nombre de la lección").props("outlined")
                description = ui.textarea("Descripción o técnica").props("outlined")
                with ui.element("div").classes("lesson-tracks"):
                    deck_a = ui.select(options, label="Track · Deck A").props("outlined")
                    deck_b = ui.select(options, label="Track · Deck B").props("outlined")

                if not paths:
                    ui.label(
                        f"No hay audios en {DEMO_TRACKS_DIRECTORY}"
                    ).classes("text-warning")

                def create_lesson() -> None:
                    lesson_name = (name.value or "").strip()
                    if not lesson_name or not deck_a.value or not deck_b.value:
                        ui.notify("Completá el nombre y ambos tracks", type="warning")
                        return
                    if deck_a.value == deck_b.value:
                        ui.notify("Seleccioná dos tracks diferentes", type="warning")
                        return
                    lesson = Lesson(
                        name=lesson_name,
                        description=(description.value or "").strip(),
                        deck_a_track=catalog.reference_for(Path(deck_a.value)),
                        deck_b_track=catalog.reference_for(Path(deck_b.value)),
                    )
                    repository.save(lesson)
                    ui.notify("Borrador de lección creado", type="positive")
                    ui.navigate.to(f"/lessons/{lesson.id}")

                ui.button("CREAR BORRADOR", on_click=create_lesson).props(
                    "unelevated color=cyan"
                )

    @ui.page("/lessons/{lesson_id}")
    def lesson_detail_page(lesson_id: str) -> None:
        with ui.column().classes("product-page"):
            try:
                lesson = repository.get(lesson_id)
            except FileNotFoundError:
                product_shell("Lección no encontrada", "El archivo local no existe.")
                ui.button("VOLVER", on_click=lambda: ui.navigate.to("/"))
                return
            product_shell(lesson.name, lesson.description or "Borrador de lección")
            ui.button("← LECCIONES", on_click=lambda: ui.navigate.to("/practice")).props("flat")
            with ui.element("section").classes("lesson-summary"):
                ui.label("ETAPA 1 DE 3 · PREPARAR").classes("stage-chip")
                ui.label(
                    "Cargá estos dos tracks en Traktor. DJ Coach detectará automáticamente "
                    "cuándo cada deck informa LOADED."
                ).classes("prep-intro")

                with ui.element("div").classes("prep-grid"):
                    with ui.element("article").classes("track-check-card"):
                        ui.label("DECK A").classes("deck-name")
                        ui.label(lesson.deck_a_track.title).classes("track-name")
                        deck_a_confirm = ui.checkbox(
                            "Confirmo que este nombre aparece en Deck A"
                        )
                    with ui.element("article").classes("track-check-card"):
                        ui.label("DECK B").classes("deck-name")
                        ui.label(lesson.deck_b_track.title).classes("track-name")
                        deck_b_confirm = ui.checkbox(
                            "Confirmo que este nombre aparece en Deck B"
                        )

                with ui.element("div").classes("readiness-list"):
                    midi_status = ui.label().classes("readiness-line")
                    deck_a_status = ui.label().classes("readiness-line")
                    deck_b_status = ui.label().classes("readiness-line")
                    names_status = ui.label().classes("readiness-line")

                ui.label(
                    "El MIDI confirma que existe un track cargado, pero no transmite su "
                    "título. Por ahora, los nombres se verifican con las dos casillas de arriba."
                ).classes("prep-note")

                with ui.element("div").classes("prep-actions"):
                    continue_button = ui.button(
                        "CONTINUAR A GRABACIÓN",
                        on_click=lambda: ui.navigate.to(
                            f"/lessons/{lesson.id}/record"
                        ),
                    ).props("unelevated color=cyan")
                    ui.button(
                        "MONITOR MIDI (OPCIONAL)",
                        on_click=lambda: ui.navigate.to("/monitor"),
                    ).props("flat")
                readiness_message = ui.label().classes("ready-message")

                def refresh_preparation() -> None:
                    status = evaluate_preparation(
                        runtime.snapshot(),
                        bool(deck_a_confirm.value),
                        bool(deck_b_confirm.value),
                    )

                    def mark(value: bool) -> str:
                        return "✓" if value else "○"

                    midi_status.set_text(
                        f"{mark(status.midi_connected)} Puerto MIDI djCoach conectado"
                    )
                    deck_a_status.set_text(
                        f"{mark(status.deck_a_loaded)} Traktor informa un track cargado en Deck A"
                    )
                    deck_b_status.set_text(
                        f"{mark(status.deck_b_loaded)} Traktor informa un track cargado en Deck B"
                    )
                    both_names = (
                        status.deck_a_name_confirmed
                        and status.deck_b_name_confirmed
                    )
                    names_status.set_text(
                        f"{mark(both_names)} Nombres de ambos tracks confirmados"
                    )
                    continue_button.set_enabled(status.ready)
                    readiness_message.set_text(
                        "✓ Todo listo. Ya podés pasar a grabar la referencia."
                        if status.ready
                        else "Completá los puntos pendientes para continuar."
                    )

                deck_a_confirm.on_value_change(lambda _event: refresh_preparation())
                deck_b_confirm.on_value_change(lambda _event: refresh_preparation())
                refresh_preparation()
                ui.timer(0.5, refresh_preparation)

    @ui.page("/lessons/{lesson_id}/record")
    def lesson_record_page(lesson_id: str) -> None:
        with ui.column().classes("product-page"):
            try:
                lesson = repository.get(lesson_id)
            except FileNotFoundError:
                product_shell("Lección no encontrada", "El archivo local no existe.")
                ui.button("VOLVER", on_click=lambda: ui.navigate.to("/"))
                return
            product_shell(
                lesson.name,
                "La preparación terminó. Esta será la pantalla para registrar la demostración del profesor.",
            )
            ui.button(
                "← VOLVER A PREPARAR",
                on_click=lambda: ui.navigate.to(f"/lessons/{lesson.id}"),
            ).props("flat")
            with ui.element("section").classes("lesson-summary"):
                ui.label("ETAPA 2 DE 3 · GRABAR REFERENCIA").classes("stage-chip")
                ui.label(f"Deck A · {lesson.deck_a_track.title}")
                ui.label(f"Deck B · {lesson.deck_b_track.title}")
                with ui.element("div").classes("steps"):
                    ui.html('<div class="step"><strong>✓</strong>Tracks preparados en Traktor.</div>')
                    ui.html('<div class="step"><strong>2</strong>Presioná Iniciar y realizá la mezcla completa desde Traktor.</div>')
                    ui.html('<div class="step"><strong>3</strong>Cuando termine la demostración, volvé y presioná Detener y guardar.</div>')

                with ui.element("div").classes("record-panel"):
                    recording_status = ui.label().classes("record-status")
                    with ui.element("div").classes("record-metrics"):
                        with ui.element("div").classes("record-metric"):
                            ui.label("DURACIÓN")
                            duration_value = ui.label("0.0 s").classes("text-h6")
                        with ui.element("div").classes("record-metric"):
                            ui.label("EVENTOS CAPTURADOS")
                            event_value = ui.label("0").classes("text-h6")
                    recording_help = ui.label().classes("record-help")
                    with ui.element("div").classes("prep-actions"):
                        start_button = ui.button("INICIAR GRABACIÓN").props(
                            "unelevated color=negative"
                        )
                        stop_button = ui.button("DETENER Y GUARDAR").props(
                            "unelevated color=positive"
                        )
                        review_button = ui.button(
                            "REVISAR REFERENCIA",
                            on_click=lambda: ui.navigate.to(
                                f"/lessons/{lesson.id}/review"
                            ),
                        ).props("outline color=cyan")
                        ui.button(
                            "MONITOR MIDI (OPCIONAL)",
                            on_click=lambda: ui.navigate.to("/monitor"),
                        ).props("flat")

                def start_recording() -> None:
                    try:
                        reference_recorder.start(lesson.id)
                    except RuntimeError as error:
                        ui.notify(str(error), type="warning")
                        return
                    ui.notify(
                        "Grabación iniciada. Realizá la mezcla en Traktor.",
                        type="positive",
                    )
                    refresh_recording()

                def stop_recording() -> None:
                    try:
                        take = reference_recorder.stop(lesson.id)
                    except RuntimeError as error:
                        ui.notify(str(error), type="warning")
                        return
                    ui.notify(
                        f"Referencia guardada con {len(take.events)} eventos.",
                        type="positive",
                    )
                    refresh_recording()

                start_button.on_click(start_recording)
                stop_button.on_click(stop_recording)

                def refresh_recording() -> None:
                    status = reference_recorder.status(lesson.id)
                    state = status["state"]
                    duration_value.set_text(
                        f'{float(status["elapsed_seconds"]):.1f} s'
                    )
                    event_value.set_text(str(status["event_count"]))
                    start_button.set_enabled(state in {"idle", "recorded"})
                    stop_button.set_enabled(state == "recording")
                    review_button.set_visibility(state == "recorded")
                    if state == "recording":
                        recording_status.set_text("● GRABANDO REFERENCIA")
                        recording_help.set_text(
                            "DJ Coach está registrando los controles y el transporte. "
                            "Podés trabajar normalmente en Traktor."
                        )
                    elif state == "recorded":
                        recording_status.set_text("✓ REFERENCIA GUARDADA")
                        recording_help.set_text(
                            f'Toma {status["take_id"]}. Podés iniciar otra si querés reemplazarla.'
                        )
                    elif state == "locked":
                        recording_status.set_text("OTRA LECCIÓN ESTÁ GRABANDO")
                        recording_help.set_text(
                            "Detené la grabación activa antes de comenzar esta lección."
                        )
                    else:
                        recording_status.set_text("LISTO PARA GRABAR")
                        recording_help.set_text(
                            "La captura comienza solamente cuando presiones Iniciar grabación."
                        )

                refresh_recording()
                ui.timer(0.25, refresh_recording)

                ui.label(
                    "No necesitás operar el Monitor MIDI. Abrilo solo si algún movimiento "
                    "de Traktor no aumenta el contador de eventos."
                ).classes("prep-note")

    @ui.page("/lessons/{lesson_id}/review")
    def lesson_review_page(lesson_id: str) -> None:
        with ui.column().classes("product-page"):
            try:
                lesson = repository.get(lesson_id)
                if not lesson.reference_take_id:
                    raise FileNotFoundError
                take = take_repository.get(lesson.reference_take_id)
            except FileNotFoundError:
                product_shell(
                    "Referencia no encontrada",
                    "Esta lección todavía no tiene una toma guardada.",
                )
                ui.button(
                    "VOLVER",
                    on_click=lambda: ui.navigate.to(
                        f"/lessons/{lesson_id}/record"
                    ),
                )
                return

            if take.features.get("schema_version") != FEATURE_SCHEMA_VERSION:
                take.features = extract_take_features(take)
                take_repository.save(take)
            features = take.features
            transition = features.get("transition")

            product_shell(
                lesson.name,
                "Revisá la técnica detectada antes de habilitarla para practicar.",
            )
            ui.button(
                "← VOLVER A GRABACIÓN",
                on_click=lambda: ui.navigate.to(
                    f"/lessons/{lesson.id}/record"
                ),
            ).props("flat")
            with ui.element("section").classes("lesson-summary"):
                ui.label("ETAPA 3 DE 3 · REVISAR Y APROBAR").classes(
                    "stage-chip"
                )
                ui.label(
                    "DJ Coach agrupó los mensajes MIDI en acciones legibles. "
                    "Los controles y estados aparecen juntos en el orden en que actuó el profesor."
                ).classes("prep-intro")

                with ui.element("div").classes("review-grid"):
                    with ui.element("div").classes("review-metric"):
                        ui.label("DURACIÓN TOTAL")
                        ui.html(f"<strong>{format_seconds(take.duration_seconds)}</strong>")
                    with ui.element("div").classes("review-metric"):
                        ui.label("ACCIONES MIDI")
                        ui.html(
                            f'<strong>{features.get("meaningful_event_count", 0)}</strong>'
                        )
                    with ui.element("div").classes("review-metric"):
                        ui.label("GESTOS AGRUPADOS")
                        ui.html(f'<strong>{len(features.get("gestures", []))}</strong>')
                    with ui.element("div").classes("review-metric"):
                        ui.label("TRANSICIÓN")
                        ui.html(
                            f'<strong>{format_seconds(transition.get("duration_seconds") if transition else None)}</strong>'
                        )

                with ui.element("section").classes("review-section"):
                    ui.html("<h2>Resumen de la transición</h2>")
                    if transition:
                        end_text = (
                            format_seconds(transition.get("ended_at"))
                            if transition.get("completed")
                            else "sin cierre detectado"
                        )
                        ui.label(
                            f'Comenzó en {format_seconds(transition.get("started_at"))}, '
                            f'terminó en {end_text} y duró '
                            f'{format_seconds(transition.get("duration_seconds"))}.'
                        ).classes("prep-intro")
                    else:
                        ui.label(
                            "No se detectó una transición completa con las reglas actuales."
                        ).classes("prep-note")

                with ui.element("section").classes("review-section"):
                    ui.html("<h2>Secuencia técnica del profesor</h2>")
                    timeline = features.get("timeline", [])
                    if not timeline:
                        ui.label("No se detectaron acciones para mostrar.")
                    for event in timeline:
                        event_type = event["type"]
                        if event_type == "control_gesture":
                            direction = {
                                "increase": "subió",
                                "decrease": "bajó",
                                "movement": "se movió",
                            }.get(event["direction"], "se movió")
                            target = (
                                f'{section_label(event["section"])} · '
                                f'{CONTROL_LABELS.get(event["control"], event["control"].upper())}'
                            )
                            detail = (
                                f'{direction} MIDI {event["start_value"]} → '
                                f'{event["end_value"]}; rango '
                                f'{event["minimum_value"]}-{event["maximum_value"]}'
                            )
                        elif event_type == "transport_change":
                            target = (
                                f'{section_label(event["section"])} · '
                                f'{CONTROL_LABELS.get(event["control"], event["control"].upper())}'
                            )
                            detail = "ON" if event["active"] else "OFF"
                        elif event_type == "transition_started":
                            target = "TRANSICIÓN"
                            detail = "Comienzo detectado"
                        else:
                            target = "TRANSICIÓN"
                            detail = "Final detectado"
                        with ui.element("div").classes("timeline-row"):
                            ui.label(format_seconds(event["elapsed_seconds"])).classes(
                                "timeline-time"
                            )
                            ui.label(target).classes("timeline-target")
                            ui.label(detail).classes("timeline-detail")

                with ui.element("div").classes("approval-panel"):
                    approval_state = ui.label().classes("approval-state")
                    approve_button = ui.button("APROBAR REFERENCIA").props(
                        "unelevated color=positive"
                    )

                def approve_reference() -> None:
                    current_lesson = repository.get(lesson.id)
                    now = datetime.now().astimezone().isoformat(
                        timespec="milliseconds"
                    )
                    current_lesson.status = "ready_for_practice"
                    current_lesson.approved_at = now
                    current_lesson.updated_at = now
                    repository.save(current_lesson)
                    approval_state.set_text(
                        "✓ Referencia aprobada y lista para la futura práctica del alumno."
                    )
                    approve_button.set_enabled(False)
                    ui.notify("Referencia aprobada", type="positive")

                approve_button.on_click(approve_reference)
                already_approved = lesson.status == "ready_for_practice"
                approve_button.set_enabled(not already_approved)
                approval_state.set_text(
                    "✓ Referencia aprobada y lista para practicar."
                    if already_approved
                    else "Confirmá que este resumen representa la técnica enseñada."
                )

    @ui.page("/practice/{lesson_id}/prepare")
    def practice_prepare_page(lesson_id: str) -> None:
        with ui.column().classes("product-page"):
            try:
                lesson = repository.get(lesson_id)
                if lesson.status != "ready_for_practice":
                    raise FileNotFoundError
            except FileNotFoundError:
                product_shell(
                    "Práctica no disponible",
                    "La referencia todavía no está aprobada.",
                )
                ui.button("VOLVER", on_click=lambda: ui.navigate.to("/practice"))
                return
            product_shell(
                lesson.name,
                "Prepará en Traktor los mismos tracks utilizados por el profesor.",
            )
            ui.button(
                "← LECCIONES", on_click=lambda: ui.navigate.to("/practice")
            ).props("flat")
            with ui.element("section").classes("lesson-summary"):
                ui.label("PRÁCTICA GUIADA · PREPARAR").classes("stage-chip")
                with ui.element("div").classes("prep-grid"):
                    with ui.element("article").classes("track-check-card"):
                        ui.label("DECK A").classes("deck-name")
                        ui.label(lesson.deck_a_track.title).classes("track-name")
                        confirm_a = ui.checkbox(
                            "Confirmo el nombre visible en Deck A"
                        )
                    with ui.element("article").classes("track-check-card"):
                        ui.label("DECK B").classes("deck-name")
                        ui.label(lesson.deck_b_track.title).classes("track-name")
                        confirm_b = ui.checkbox(
                            "Confirmo el nombre visible en Deck B"
                        )
                ready_to_start = ui.checkbox(
                    "Ambos decks están pausados y ubicados donde comenzará la práctica"
                )
                with ui.element("div").classes("readiness-list"):
                    midi_line = ui.label().classes("readiness-line")
                    deck_a_line = ui.label().classes("readiness-line")
                    deck_b_line = ui.label().classes("readiness-line")
                    names_line = ui.label().classes("readiness-line")
                    start_line = ui.label().classes("readiness-line")
                continue_button = ui.button(
                    "COMENZAR PRÁCTICA GUIADA",
                    on_click=lambda: ui.navigate.to(
                        f"/practice/{lesson.id}/guided"
                    ),
                ).props("unelevated color=pink")

                def refresh_student_preparation() -> None:
                    status = evaluate_preparation(
                        runtime.snapshot(), bool(confirm_a.value), bool(confirm_b.value)
                    )
                    mark = lambda value: "✓" if value else "○"
                    midi_line.set_text(
                        f"{mark(status.midi_connected)} Puerto MIDI conectado"
                    )
                    deck_a_line.set_text(
                        f"{mark(status.deck_a_loaded)} Track cargado en Deck A"
                    )
                    deck_b_line.set_text(
                        f"{mark(status.deck_b_loaded)} Track cargado en Deck B"
                    )
                    names_ok = (
                        status.deck_a_name_confirmed
                        and status.deck_b_name_confirmed
                    )
                    names_line.set_text(
                        f"{mark(names_ok)} Nombres confirmados"
                    )
                    start_line.set_text(
                        f"{mark(bool(ready_to_start.value))} Decks pausados y listos para iniciar"
                    )
                    continue_button.set_enabled(
                        status.ready and bool(ready_to_start.value)
                    )

                confirm_a.on_value_change(
                    lambda _event: refresh_student_preparation()
                )
                confirm_b.on_value_change(
                    lambda _event: refresh_student_preparation()
                )
                ready_to_start.on_value_change(
                    lambda _event: refresh_student_preparation()
                )
                refresh_student_preparation()
                ui.timer(0.5, refresh_student_preparation)

    @ui.page("/practice/{lesson_id}/guided")
    def guided_practice_page(lesson_id: str) -> None:
        with ui.column().classes("product-page"):
            try:
                lesson = repository.get(lesson_id)
                if lesson.status != "ready_for_practice":
                    raise FileNotFoundError
            except FileNotFoundError:
                product_shell("Práctica no disponible", "La lección no está aprobada.")
                return
            product_shell(
                lesson.name,
                "La app mostrará solamente la acción actual y la siguiente.",
            )
            ui.button(
                "← VOLVER A PREPARAR",
                on_click=lambda: ui.navigate.to(
                    f"/practice/{lesson.id}/prepare"
                ),
            ).props("flat")
            with ui.element("section").classes("lesson-summary"):
                ui.label("PRÁCTICA GUIADA · INTENTO DEL ALUMNO").classes(
                    "stage-chip"
                )
                ui.label(
                    "Presioná Iniciar intento y luego comenzá el Deck A desde Traktor. "
                    "Ese PLAY sincroniza el reloj de la guía."
                ).classes("prep-intro")
                previous_moment = ui.html(
                    render_guidance_moment(None, "ANTERIOR", "previous"),
                    sanitize=False,
                ).classes("w-full")
                with ui.element("div").classes("guidance-card"):
                    guidance_state = ui.label("LISTO").classes("guidance-state")
                    current_time = ui.label().classes("guidance-time")
                    current_moment = ui.html(
                        render_guidance_moment(None, "AHORA", "current"),
                        sanitize=False,
                    ).classes("w-full")
                next_moment = ui.html(
                    render_guidance_moment(None, "PRÓXIMO", "next"),
                    sanitize=False,
                ).classes("w-full")
                practice_progress = ui.label().classes("practice-progress")
                with ui.element("div").classes("prep-actions"):
                    start_attempt_button = ui.button("INICIAR INTENTO").props(
                        "unelevated color=pink"
                    )
                    stop_attempt_button = ui.button(
                        "DETENER Y VER RESULTADO"
                    ).props("unelevated color=positive")

                def start_attempt() -> None:
                    try:
                        guided_practice.start(lesson.id)
                    except (RuntimeError, ValueError) as error:
                        ui.notify(str(error), type="warning")
                        return
                    ui.notify(
                        "Intento iniciado. Ahora pulsá PLAY en Deck A.",
                        type="positive",
                    )
                    refresh_guidance()

                def stop_attempt() -> None:
                    try:
                        attempt = guided_practice.stop(lesson.id)
                    except RuntimeError as error:
                        ui.notify(str(error), type="warning")
                        return
                    ui.navigate.to(
                        f"/practice/{lesson.id}/result/{attempt.id}"
                    )

                start_attempt_button.on_click(start_attempt)
                stop_attempt_button.on_click(stop_attempt)

                def refresh_guidance() -> None:
                    status = guided_practice.status(lesson.id)
                    state = status["state"]
                    active = state != "idle"
                    start_attempt_button.set_enabled(not active)
                    stop_attempt_button.set_enabled(active)
                    if state == "idle":
                        guidance_state.set_text("LISTO PARA EMPEZAR")
                        previous_moment.set_content(
                            render_guidance_moment(None, "ANTERIOR", "previous")
                        )
                        current_time.set_text("")
                        current_moment.set_content(
                            render_guidance_moment(None, "AHORA", "current")
                        )
                        next_moment.set_content(
                            render_guidance_moment(None, "PRÓXIMO", "next")
                        )
                        practice_progress.set_text("")
                        return
                    if state == "waiting_for_play":
                        guidance_state.set_text("ESPERANDO SINCRONIZACIÓN")
                        current_time.set_text("La guía comenzará con ese evento")
                        previous_moment.set_content(
                            render_guidance_moment(None, "ANTERIOR", "previous")
                        )
                        play_moment = {
                            "actions": [
                                {
                                    "section": "deck_a",
                                    "instruction": "Pulsá PLAY en Deck A",
                                    "outcome": None,
                                }
                            ]
                        }
                        current_moment.set_content(
                            render_guidance_moment(play_moment, "AHORA", "current")
                        )
                        next_moment.set_content(
                            render_guidance_moment(None, "PRÓXIMO", "next")
                        )
                    elif state == "guidance_complete":
                        guidance_state.set_text("SECUENCIA COMPLETADA")
                        current_time.set_text("✓ Todas las consignas fueron recorridas")
                        previous_moment.set_content(
                            render_guidance_moment(
                                status.get("previous"), "ANTERIOR", "previous"
                            )
                        )
                        current_moment.set_content(
                            render_guidance_moment(None, "AHORA", "current")
                        )
                        next_moment.set_content(
                            render_guidance_moment(None, "PRÓXIMO", "next")
                        )
                    else:
                        seconds_until = float(status["seconds_until_current"])
                        guidance_state.set_text(
                            "AHORA" if seconds_until <= 0 else "MOMENTO PRÓXIMO"
                        )
                        current_time.set_text(
                            "Ahora"
                            if seconds_until <= 0
                            else f"En {seconds_until:.0f} segundos"
                        )
                        previous_moment.set_content(
                            render_guidance_moment(
                                status.get("previous"), "ANTERIOR", "previous"
                            )
                        )
                        current_moment.set_content(
                            render_guidance_moment(
                                status.get("current"), "AHORA", "current"
                            )
                        )
                        next_moment.set_content(
                            render_guidance_moment(
                                status.get("next"), "PRÓXIMO", "next"
                            )
                        )
                    practice_progress.set_text(
                        f'{status["completed_count"]} completadas · '
                        f'{status["missed_count"]} omitidas · '
                        f'{status["total_steps"]} consignas'
                    )

                refresh_guidance()
                ui.timer(0.25, refresh_guidance)

    @ui.page("/practice/{lesson_id}/result/{attempt_id}")
    def practice_result_page(lesson_id: str, attempt_id: str) -> None:
        with ui.column().classes("product-page"):
            try:
                lesson = repository.get(lesson_id)
                attempt = attempt_repository.get(attempt_id)
                if attempt.lesson_id != lesson.id or attempt.role.value != "student":
                    raise FileNotFoundError
            except FileNotFoundError:
                product_shell("Resultado no encontrado", "El intento local no existe.")
                return
            features = attempt.features
            steps_by_id = {
                step["id"]: step for step in features.get("steps", [])
            }
            product_shell(
                "Resultado del intento",
                f"Práctica guiada de {lesson.name}",
            )
            ui.label(f'{features.get("score_percentage", 0)}%').classes(
                "result-score"
            )
            ui.label(
                f'{features.get("completed_count", 0)} de '
                f'{features.get("total_steps", 0)} consignas completadas'
            ).classes("prep-intro")
            with ui.element("section").classes("review-section"):
                for outcome in features.get("outcomes", []):
                    step = steps_by_id[outcome["step_id"]]
                    completed = outcome["status"] == "completed"
                    timing = {
                        "early": "antes",
                        "on_time": "a tiempo",
                        "late": "tarde",
                    }.get(outcome.get("timing"), "omitida")
                    with ui.element("div").classes("result-row"):
                        ui.label("✓" if completed else "○").classes(
                            "result-ok" if completed else "result-missed"
                        )
                        ui.label(step["instruction"])
                        ui.label(timing).classes(
                            "result-ok" if completed else "result-missed"
                        )
            ui.button(
                "REPETIR PRÁCTICA",
                on_click=lambda: ui.navigate.to(
                    f"/practice/{lesson.id}/prepare"
                ),
            ).props("unelevated color=pink")

    @ui.page("/practice")
    def practice_page() -> None:
        lessons = [
            lesson
            for lesson in repository.list()
            if lesson.status == "ready_for_practice"
        ]
        with ui.column().classes("product-page"):
            product_shell(
                "Biblioteca de lecciones",
                "Los borradores y las futuras demostraciones del profesor se guardan localmente.",
            )
            ui.button("← INICIO", on_click=lambda: ui.navigate.to("/")).props("flat")
            if not lessons:
                ui.html('<div class="empty-library">Todavía no hay lecciones aprobadas para practicar.</div>')
                return
            with ui.element("div").classes("lesson-list"):
                for lesson in lessons:
                    with ui.element("article").classes("lesson-row"):
                        with ui.column().classes("gap-0"):
                            ui.label(lesson.name).classes("text-h6")
                            ui.label(
                                f"{lesson.deck_a_track.title} → {lesson.deck_b_track.title}"
                            ).classes("text-caption text-grey")
                            ui.label("LISTA PARA PRACTICAR").classes("product-kicker")
                        ui.button(
                            "PRACTICAR",
                            on_click=lambda lesson_id=lesson.id: ui.navigate.to(
                                f"/practice/{lesson_id}/prepare"
                            ),
                        ).props("outline")
