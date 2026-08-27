"""Páginas principales del producto, separadas del monitor técnico MIDI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nicegui import ui

from djcoach.config import DEMO_TRACKS_DIRECTORY, ensure_data_directories
from djcoach.domain import Lesson
from djcoach.lessons import (
    LessonRepository,
    ReferenceTakeRecorder,
    evaluate_preparation,
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
@media(max-width:800px){.mode-grid,.lesson-tracks{grid-template-columns:1fr}.product-header h1{font-size:32px}}
@media(max-width:800px){.prep-grid{grid-template-columns:1fr}}
"""


def product_shell(title: str, subtitle: str) -> None:
    ui.add_css(PRODUCT_CSS)
    with ui.element("header").classes("product-header"):
        ui.label("DJ COACH · LECCIONES GRABADAS").classes("product-kicker")
        ui.html(f"<h1>{title}</h1><p>{subtitle}</p>", sanitize=True)


def register_product_pages(runtime: Any) -> None:
    ensure_data_directories()
    catalog = TrackCatalog(DEMO_TRACKS_DIRECTORY)
    repository = LessonRepository()
    reference_recorder = ReferenceTakeRecorder(runtime, repository)

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

    @ui.page("/practice")
    def practice_page() -> None:
        lessons = repository.list()
        with ui.column().classes("product-page"):
            product_shell(
                "Biblioteca de lecciones",
                "Los borradores y las futuras demostraciones del profesor se guardan localmente.",
            )
            ui.button("← INICIO", on_click=lambda: ui.navigate.to("/")).props("flat")
            if not lessons:
                ui.html('<div class="empty-library">Todavía no hay lecciones. Creá la primera desde el modo Profesor.</div>')
                return
            with ui.element("div").classes("lesson-list"):
                for lesson in lessons:
                    with ui.element("article").classes("lesson-row"):
                        with ui.column().classes("gap-0"):
                            ui.label(lesson.name).classes("text-h6")
                            ui.label(
                                f"{lesson.deck_a_track.title} → {lesson.deck_b_track.title}"
                            ).classes("text-caption text-grey")
                        ui.button(
                            "ABRIR",
                            on_click=lambda lesson_id=lesson.id: ui.navigate.to(
                                f"/lessons/{lesson_id}"
                            ),
                        ).props("outline")
