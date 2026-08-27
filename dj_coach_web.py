"""Frontend web local para DJ Coach."""

from __future__ import annotations

import argparse
import html
from typing import Any

from nicegui import app, ui

from dj_coach import effective_deck_bpm
from dj_coach_runtime import DJCoachRuntime
from djcoach.web import register_product_pages


runtime = DJCoachRuntime()

MIXER_CONTROLS = (
    ("low", "LOW"),
    ("mid", "MID"),
    ("high", "HIGH"),
    ("gain", "GAIN"),
    ("fx_adjust", "FX / FILTER"),
    ("volume", "VOLUME"),
)

STATE_CONTROLS = (
    ("loaded", "LOADED"),
    ("play", "PLAY"),
    ("transport_cue", "CUE PLAY"),
    ("loop_active", "LOOP"),
    ("sync", "SYNC"),
    ("fx_on", "FX ON"),
    ("cue", "MON CUE"),
    ("track_end_warning", "TRACK END"),
)


def continuous_row(deck: dict[str, Any], key: str, label: str) -> str:
    control = deck[key]
    if not control["received"]:
        return f"""
        <div class="control-row unknown">
          <div class="control-head"><span>{label}</span><strong>---</strong></div>
          <div class="meter"><i style="width:0%"></i></div>
          <small>MIDI ---</small>
        </div>"""

    percentage = int(control["percentage"])
    midi_value = int(control["midi"])
    return f"""
    <div class="control-row">
      <div class="control-head"><span>{label}</span><strong>{percentage}%</strong></div>
      <div class="meter"><i style="width:{percentage}%"></i></div>
      <small>MIDI {midi_value}</small>
    </div>"""


def state_badge(deck: dict[str, Any], key: str, label: str) -> str:
    if not deck[f"{key}_received"]:
        state_class = "unknown"
        state_text = "---"
    elif deck[key]:
        state_class = "on"
        state_text = "ON"
    else:
        state_class = "off"
        state_text = "OFF"
    return f"""
    <div class="state-item {state_class}">
      <span>{label}</span><strong>{state_text}</strong>
    </div>"""


def loop_size_badge(deck: dict[str, Any]) -> str:
    control = deck["loop_size"]
    if not control["received"]:
        state_class, state_text = "unknown", "---"
    else:
        state_class, state_text = "on", str(control["label"])
    return f"""
    <div class="state-item {state_class}">
      <span>LOOP SIZE</span><strong>{html.escape(state_text)}</strong>
    </div>"""


def timing_widget(deck: dict[str, Any], key: str, label: str) -> str:
    control = deck[key]
    if not control["received"]:
        return f"""
        <div class="timing-widget unknown">
          <span>{label}</span><div class="phase-track"></div><strong>MIDI ---</strong>
        </div>"""
    percentage = int(control["percentage"])
    midi_value = int(control["midi"])
    return f"""
    <div class="timing-widget">
      <span>{label}</span>
      <div class="phase-track"><i style="left:{percentage}%"></i></div>
      <strong>MIDI {midi_value}</strong>
    </div>"""


def track_progress_widget(deck: dict[str, Any]) -> str:
    control = deck["track_progress"]
    if not control["received"]:
        return """
        <div class="track-progress unknown">
          <div><span>PROGRESO DE CANCIÓN</span><strong>---</strong></div>
          <div class="progress-track"><i style="width:0%"></i></div>
          <small>Esperando Seek Position</small>
        </div>"""
    percentage = int(control["percentage"])
    midi_value = int(control["midi"])
    return f"""
    <div class="track-progress">
      <div><span>PROGRESO DE CANCIÓN</span><strong>{percentage}%</strong></div>
      <div class="progress-track"><i style="width:{percentage}%"></i></div>
      <small>MIDI {midi_value}</small>
    </div>"""


def rhythm_widget(tempo: dict[str, Any]) -> str:
    if tempo["downbeat_armed"]:
        return """
        <div class="rhythm-widget armed">
          <div class="rhythm-empty"><strong>ESPERANDO</strong><span>El próximo beat será 1/4</span></div>
        </div>"""
    if not tempo["downbeat_set"]:
        return """
        <div class="rhythm-widget unknown">
          <div class="rhythm-empty"><strong>BEAT 1 SIN MARCAR</strong><span>Usá el botón de calibración superior</span></div>
        </div>"""

    blocks = "".join(
        f"""
        <div><span>BLOQUE {size}</span><strong>{tempo['bar_in_block'][str(size)]}/{size}</strong><small>#{tempo['block_count'][str(size)]}</small></div>"""
        for size in (4, 8, 16, 32)
    )
    return f"""
    <div class="rhythm-widget">
      <div class="rhythm-current"><span>RITMO 4/4</span><strong>{tempo['beat_in_bar']}/4</strong><small>COMPÁS {tempo['bar_count']}</small></div>
      <div class="rhythm-blocks">{blocks}</div>
    </div>"""


def deck_card(
    deck: dict[str, Any],
    tempo: dict[str, Any],
    midi_clock: dict[str, Any],
    name: str,
    accent: str,
) -> str:
    mixer = "".join(continuous_row(deck, key, label) for key, label in MIXER_CONTROLS)
    states = "".join(state_badge(deck, key, label) for key, label in STATE_CONTROLS)
    states += loop_size_badge(deck)
    timing = "".join(
        (
            timing_widget(deck, "phase", "PHASE"),
            timing_widget(deck, "beat_phase", "BEAT PHASE"),
        )
    )
    bpm, bpm_source, bpm_active = effective_deck_bpm(deck, tempo, midi_clock)
    if bpm is not None:
        bpm_value = f"{bpm:.1f}"
        bpm_status = "ACTIVO" if bpm_active else "DETENIDO"
        bpm_class = "active" if bpm_active else "stopped"
    else:
        bpm_value = "---"
        bpm_status = "CALCULANDO · BEAT PHASE"
        bpm_class = "unknown"
    return f"""
    <section class="deck-card" style="--accent:{accent}">
      <header>
        <div><span>TRACK DECK</span><h2>DECK {name}</h2></div>
        <div class="deck-bpm {bpm_class}"><strong>{bpm_value}</strong><span>BPM ACTUAL · {bpm_status} · {bpm_source}</span></div>
      </header>
      {track_progress_widget(deck)}
      {rhythm_widget(tempo)}
      <div class="mixer-grid">{mixer}</div>
      <div class="state-grid">{states}</div>
      <div class="timing-grid">{timing}</div>
    </section>"""


def crossfader_widget(crossfader: dict[str, Any]) -> str:
    if not crossfader["received"]:
        percentage = 50
        value = "---"
        marker_class = "unknown"
        position = "SIN RECIBIR"
    else:
        percentage = int(crossfader["percentage"])
        midi_value = int(crossfader["midi"])
        value = str(midi_value)
        marker_class = ""
        if midi_value == 0:
            position = "DECK A"
        elif midi_value == 127:
            position = "DECK B"
        elif 63 <= midi_value <= 64:
            position = "CENTRO"
        elif midi_value < 64:
            position = "HACIA A"
        else:
            position = "HACIA B"
    return f"""
    <section class="cross-card">
      <div class="section-kicker">MIXER</div><h3>CROSSFADER</h3>
      <div class="cross-labels"><b>A</b><span>{position}</span><b>B</b></div>
      <div class="cross-track">
        <i class="{marker_class}" style="left:{percentage}%"></i>
      </div>
      <div class="cross-value">{percentage if value != '---' else '---'}% · MIDI {value}</div>
    </section>"""


def audible_text(value: bool | None) -> str:
    if value is None:
        return "---"
    return "SÍ" if value else "NO"


def render_dashboard(snapshot: dict[str, Any]) -> str:
    connected = snapshot["status"] == "connected"
    status_class = "connected" if connected else "error"
    status_text = "TRAKTOR CONECTADO" if connected else snapshot["status"].upper()
    if snapshot["error"]:
        status_text = snapshot["error"]

    coach = snapshot["coach"]
    feedback = html.escape(str(coach["feedback"]))
    feedback_class = "warning" if feedback.startswith("AVISO") else "normal"
    raw_message = html.escape(snapshot["last_raw_message"] or "Esperando MIDI...")
    last_midi = html.escape(snapshot["last_midi_at"] or "---")
    port_name = html.escape(snapshot["port_name"] or "djCoach")
    midi_clock = snapshot["midi_clock"]
    if midi_clock["received"]:
        clock_bpm = (
            f'{float(midi_clock["bpm"]):.1f}'
            if midi_clock["bpm"] is not None
            else "---"
        )
        clock_status = "ACTIVO" if midi_clock["active"] else "DETENIDO"
        clock_class = "active" if midi_clock["active"] else "stopped"
    else:
        clock_bpm = "---"
        clock_status = "SIN RECIBIR"
        clock_class = "unknown"
    recent_warnings = coach.get("warning_history", [])[-4:]
    warnings_html = "".join(
        f'<li class="{html.escape(str(warning.get("severity", "warning")))}">'
        f'<span>{html.escape(str(warning["rule"]).replace("_", " ").upper())}</span>'
        f'{html.escape(str(warning["message"]))}</li>'
        for warning in reversed(recent_warnings)
    )
    if not warnings_html:
        warnings_html = "<li class=\"empty\">Sin avisos en esta sesión</li>"

    return f"""
    <main class="dashboard-shell">
      <header class="topbar">
        <div><div class="eyebrow">REAL-TIME MIXING MONITOR</div><h1>DJ COACH</h1></div>
        <div class="top-status">
          <div class="midi-clock {clock_class}">
            <span>MASTER CLOCK</span><strong>{clock_bpm} <small>BPM</small></strong><em>{clock_status}</em>
          </div>
          <div class="connection {status_class}"><i></i><span>{status_text}</span><small>{port_name}</small></div>
        </div>
      </header>

      <div class="decks-layout">
        {deck_card(snapshot['deck_a'], snapshot['deck_tempos']['a'], snapshot['midi_clock'], 'A', '#36d7ff')}
        {deck_card(snapshot['deck_b'], snapshot['deck_tempos']['b'], snapshot['midi_clock'], 'B', '#ff4fd8')}
      </div>

      <div class="bottom-layout">
        {crossfader_widget(snapshot['crossfader'])}
        <section class="coach-card {feedback_class}">
          <div class="section-kicker">LOCAL COACH ENGINE</div>
          <h3>{feedback}</h3>
          <div class="coach-stats">
            <div><span>DECK A AUDIBLE</span><strong>{audible_text(coach['deck_a_audible'])}</strong></div>
            <div><span>DECK B AUDIBLE</span><strong>{audible_text(coach['deck_b_audible'])}</strong></div>
            <div><span>TRANSICIÓN</span><strong>{'ACTIVA' if coach['transition_active'] else 'NO'}</strong></div>
            <div><span>EVENTOS</span><strong>{snapshot['event_count']}</strong></div>
          </div>
          <div class="warning-log">
            <span>AVISOS RECIENTES</span>
            <ul>{warnings_html}</ul>
          </div>
        </section>
      </div>

      <section class="debug-strip">
        <span>ÚLTIMO MIDI</span><code>{raw_message}</code><small>{last_midi}</small>
      </section>
    </main>"""


CSS = """
:root { color-scheme: dark; --bg:#070a0f; --panel:#10151d; --line:#252d39; --text:#f5f7fa; --muted:#7f8a99; }
body { margin:0; background:radial-gradient(circle at 50% -20%,#1a2637 0,#090d13 45%,#05070a 100%); color:var(--text); font-family:Inter,Segoe UI,sans-serif; }
.q-page { min-height:100vh !important; }
.dashboard-shell { width:min(1440px,calc(100vw - 32px)); margin:0 auto; padding:24px 0 40px; }
.topbar { display:flex; align-items:center; justify-content:space-between; gap:24px; margin-bottom:20px; }
.top-status { display:flex; align-items:stretch; gap:10px; }.midi-clock { display:grid; grid-template-columns:auto auto; column-gap:14px; align-items:center; padding:8px 14px; border:1px solid var(--line); border-radius:12px; background:#0d1219; }.midi-clock span { grid-column:1; color:var(--muted); font-size:8px; font-weight:800; letter-spacing:.12em; }.midi-clock strong { grid-column:1; font-family:Consolas,monospace; font-size:20px; }.midi-clock strong small { color:var(--muted); font-size:9px; }.midi-clock em { grid-column:2; grid-row:1/3; color:#667384; font-size:9px; font-style:normal; font-weight:800; }.midi-clock.active em { color:#32e59d; }.midi-clock.stopped em { color:#ffb648; }
.eyebrow,.section-kicker { color:#6f7c8d; font-size:10px; font-weight:800; letter-spacing:.22em; }
h1 { margin:2px 0 0; font-size:32px; letter-spacing:.04em; } h2,h3 { margin:0; }
.connection { display:grid; grid-template-columns:10px auto; column-gap:10px; align-items:center; padding:10px 14px; border:1px solid var(--line); border-radius:12px; background:#0d1219; }
.connection i { grid-row:1/3; width:9px; height:9px; border-radius:50%; background:#ff5364; box-shadow:0 0 14px #ff5364; }
.connection.connected i { background:#32e59d; box-shadow:0 0 14px #32e59d; }
.connection span { font-size:11px; font-weight:800; letter-spacing:.08em; }.connection small { color:var(--muted); }
.decks-layout { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
.deck-card,.cross-card,.coach-card,.debug-strip { background:linear-gradient(160deg,rgba(19,25,35,.97),rgba(10,14,20,.97)); border:1px solid var(--line); border-radius:18px; box-shadow:0 18px 50px rgba(0,0,0,.25); }
.deck-card { padding:20px; border-top:2px solid var(--accent); }
.deck-card header { display:flex; align-items:end; justify-content:space-between; border-bottom:1px solid var(--line); padding-bottom:14px; margin-bottom:16px; }
.deck-card header span { color:var(--accent); font-size:10px; font-weight:800; letter-spacing:.18em; }.deck-card h2 { font-size:25px; }
.deck-bpm { text-align:right; }.deck-bpm strong { display:block; color:var(--accent); font-family:Consolas,monospace; font-size:25px; line-height:1; }.deck-bpm span { display:block; margin-top:5px; color:var(--muted) !important; font-size:8px !important; letter-spacing:.1em !important; }.deck-bpm.stopped strong { color:#ffb648; }.deck-bpm.unknown { opacity:.5; }
.track-progress { margin-bottom:16px; padding:12px; border-radius:10px; background:#0a0e14; border:1px solid #1d2530; }.track-progress>div:first-child { display:flex; justify-content:space-between; align-items:center; }.track-progress span { color:var(--muted); font-size:9px; font-weight:800; letter-spacing:.12em; }.track-progress strong { color:var(--accent); font-size:18px; }.progress-track { height:7px; margin:9px 0 6px; overflow:hidden; border-radius:7px; background:#222a35; }.progress-track i { display:block; height:100%; background:var(--accent); box-shadow:0 0 12px var(--accent); }.track-progress small { color:var(--muted); font-family:Consolas,monospace; }
.rhythm-toolbar { width:min(1440px,calc(100vw - 32px)); margin:12px auto -10px; padding:10px 12px; border:1px solid var(--line); border-radius:12px; background:#0d1219; align-items:center; }.rhythm-toolbar .q-btn { font-size:10px; letter-spacing:.06em; }.rhythm-widget { display:grid; grid-template-columns:120px 1fr; gap:10px; margin-bottom:16px; padding:10px; border:1px solid #1d2530; border-radius:10px; background:#0a0e14; }.rhythm-current { display:grid; align-content:center; text-align:center; border-right:1px solid var(--line); }.rhythm-current span,.rhythm-blocks span { color:var(--muted); font-size:8px; font-weight:800; letter-spacing:.1em; }.rhythm-current strong { color:var(--accent); font-family:Consolas,monospace; font-size:28px; }.rhythm-current small { color:var(--text); }.rhythm-blocks { display:grid; grid-template-columns:repeat(4,1fr); gap:7px; }.rhythm-blocks div { display:grid; align-content:center; padding:7px; border-radius:7px; background:#111720; text-align:center; }.rhythm-blocks strong { color:var(--accent); font-family:Consolas,monospace; }.rhythm-blocks small { color:var(--muted); font-size:8px; }.rhythm-empty { grid-column:1/3; display:flex; justify-content:center; gap:10px; color:var(--muted); font-size:10px; }.rhythm-empty strong { color:var(--accent); }.rhythm-widget.armed { border-color:var(--accent); }
.mixer-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px 18px; }
.control-row { position:relative; padding:9px 10px; background:#0a0e14; border:1px solid #1d2530; border-radius:10px; }
.control-head { display:flex; justify-content:space-between; font-size:11px; letter-spacing:.08em; }.control-head strong { color:var(--accent); font-size:14px; }
.meter { height:4px; margin:8px 0 5px; overflow:hidden; border-radius:4px; background:#222a35; }.meter i { display:block; height:100%; background:var(--accent); box-shadow:0 0 10px var(--accent); }
.control-row small { color:var(--muted); font-family:Consolas,monospace; }.unknown { opacity:.52; }
.state-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-top:16px; }
.state-item { padding:8px; border-radius:9px; background:#0a0e14; border:1px solid #202833; display:flex; justify-content:space-between; gap:8px; font-size:10px; }
.state-item strong { color:#6f7c8d; }.state-item.on { border-color:color-mix(in srgb,var(--accent) 45%,#202833); }.state-item.on strong { color:var(--accent); }.state-item.off strong { color:#657080; }
.timing-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:16px; padding-top:14px; border-top:1px solid var(--line); }
.timing-widget { display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:10px; color:var(--muted); font-size:10px; }
.timing-widget strong { color:var(--text); font-family:Consolas,monospace; }.phase-track { position:relative; height:6px; border-radius:5px; background:linear-gradient(90deg,#26303d 49%,#69778a 50%,#26303d 51%); }
.phase-track i { position:absolute; top:50%; width:10px; height:10px; border-radius:50%; background:var(--accent); transform:translate(-50%,-50%); box-shadow:0 0 12px var(--accent); }
.bottom-layout { display:grid; grid-template-columns:minmax(320px,.85fr) 1.15fr; gap:18px; margin-top:18px; }.cross-card,.coach-card { padding:20px; }
.cross-card h3,.coach-card h3 { margin-top:5px; }.cross-labels { display:flex; justify-content:space-between; margin:22px 2px 8px; }.cross-labels span { color:var(--muted); font-size:11px; }
.cross-track { position:relative; height:8px; border-radius:8px; background:linear-gradient(90deg,#36d7ff,#747b88 50%,#ff4fd8); }.cross-track i { position:absolute; top:50%; width:18px; height:28px; border-radius:5px; background:#fff; transform:translate(-50%,-50%); box-shadow:0 0 18px #fff8; }.cross-track i.unknown { opacity:.35; }
.cross-value { margin-top:12px; text-align:center; color:var(--muted); font-family:Consolas,monospace; }
.coach-card { border-left:3px solid #32e59d; }.coach-card.warning { border-left-color:#ffb648; }.coach-card h3 { min-height:44px; font-size:18px; line-height:1.35; }
.coach-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-top:16px; }.coach-stats div { padding:10px; background:#0a0e14; border-radius:9px; }.coach-stats span { display:block; color:var(--muted); font-size:9px; letter-spacing:.08em; }.coach-stats strong { display:block; margin-top:5px; font-size:16px; }
.warning-log { margin-top:14px; padding-top:12px; border-top:1px solid var(--line); }.warning-log>span { color:var(--muted); font-size:9px; font-weight:800; letter-spacing:.12em; }.warning-log ul { display:grid; gap:7px; margin:9px 0 0; padding:0; list-style:none; }.warning-log li { padding:8px 10px; border-radius:8px; background:#17130d; color:#e8d7b8; font-size:11px; line-height:1.35; }.warning-log li span { display:block; color:#ffb648; font-size:8px; font-weight:800; letter-spacing:.1em; }.warning-log li.empty { background:#0a0e14; color:var(--muted); }
.warning-log li.success { background:#0d1914; color:#bcebd7; }.warning-log li.success span { color:#32e59d; }
.debug-strip { display:grid; grid-template-columns:auto 1fr auto; gap:14px; align-items:center; margin-top:18px; padding:12px 16px; }.debug-strip span { color:var(--muted); font-size:9px; font-weight:800; letter-spacing:.14em; }.debug-strip code { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#b9c4d2; }.debug-strip small { color:#667384; }
@media (max-width:900px) { .decks-layout,.bottom-layout { grid-template-columns:1fr; }.state-grid { grid-template-columns:repeat(2,1fr); }.topbar { align-items:flex-start; }.top-status { flex-direction:column; }.rhythm-widget { grid-template-columns:1fr; }.rhythm-current { border-right:0; border-bottom:1px solid var(--line); padding-bottom:8px; }.rhythm-blocks { grid-template-columns:repeat(2,1fr); }.debug-strip { grid-template-columns:1fr; }.debug-strip small { display:none; } }
"""


@ui.page("/monitor")
def monitor_page() -> None:
    ui.add_css(CSS)

    def mark_downbeat(side: str, name: str) -> None:
        runtime.arm_downbeat(side)
        ui.notify(
            f"Deck {name}: el próximo beat será 1/4",
            type="positive",
            position="top",
        )

    def clear_downbeat(side: str, name: str) -> None:
        runtime.clear_downbeat(side)
        ui.notify(f"Contador del Deck {name} reiniciado", position="top")

    with ui.row().classes("rhythm-toolbar"):
        ui.button("← INICIO", on_click=lambda: ui.navigate.to("/")).props("flat")
        ui.label("CALIBRACIÓN DE COMPÁS")
        ui.button(
            "PRÓXIMO BEAT = 1 · DECK A",
            on_click=lambda: mark_downbeat("a", "A"),
        ).props("outline color=cyan")
        ui.button(
            "PRÓXIMO BEAT = 1 · DECK B",
            on_click=lambda: mark_downbeat("b", "B"),
        ).props("outline color=pink")
        ui.button(
            "BORRAR A", on_click=lambda: clear_downbeat("a", "A")
        ).props("flat")
        ui.button(
            "BORRAR B", on_click=lambda: clear_downbeat("b", "B")
        ).props("flat")

    dashboard = ui.html(render_dashboard(runtime.snapshot()), sanitize=False).classes(
        "w-full"
    )

    def refresh() -> None:
        dashboard.set_content(render_dashboard(runtime.snapshot()))

    ui.timer(0.1, refresh)


register_product_pages(runtime)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Frontend web de DJ Coach")
    parser.add_argument("--port", type=int, default=8080, help="puerto HTTP local")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="no abre automáticamente el navegador",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app.on_startup(runtime.start)
    app.on_shutdown(runtime.stop)
    ui.run(
        host="127.0.0.1",
        port=args.port,
        title="DJ Coach",
        dark=True,
        language="es",
        show=not args.no_open,
        reload=False,
        favicon="🎧",
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
