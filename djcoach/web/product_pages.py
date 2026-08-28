"""Páginas principales del producto, separadas del monitor técnico MIDI."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Callable

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
    build_guidance_moments,
    build_guidance_steps,
    event_matches_step,
    evaluate_preparation,
    extract_take_features,
    compare_initial_state,
    evaluate_guided_attempt,
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
.guided-product-page { width:min(1280px,calc(100vw - 28px)); padding-top:18px; }
.guided-topnav { display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:8px; }.guided-brand { color:#ff83e4; font-size:11px; font-weight:900; letter-spacing:.16em; }
.guided-shell { display:grid; gap:16px; width:100%; padding:18px; border:0; background:linear-gradient(155deg,#101720,#0a0f16); box-shadow:0 20px 70px #0007; }
.coach-context { display:grid; grid-template-columns:minmax(220px,1.7fr) repeat(5,minmax(105px,.62fr)); gap:10px; align-items:stretch; }.context-cell { display:grid; align-content:center; min-height:66px; padding:10px 14px; border-radius:11px; background:#0a1017; }.context-cell span { color:#8291a5; font-size:10px; font-weight:900; letter-spacing:.12em; }.context-cell strong { margin-top:5px; color:#f1f5fa; font-size:16px; }.context-cell.lesson strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.coach-timeline { display:flex; gap:0; overflow-x:auto; padding:5px 2px 12px; scrollbar-width:thin; }.timeline-step { position:relative; display:flex; flex:0 0 auto; align-items:center; gap:9px; min-width:155px; padding-right:34px; color:#748297; }.timeline-step:not(:last-child)::after { content:""; position:absolute; right:8px; width:18px; height:1px; background:#3b4758; }.timeline-step .timeline-icon { display:grid; place-items:center; width:30px; height:30px; border:1px solid #526075; border-radius:50%; font-size:13px; }.timeline-step .timeline-label { max-width:118px; overflow:hidden; font-size:12px; font-weight:850; text-overflow:ellipsis; white-space:nowrap; }.timeline-step.completed { color:#58e5a3; }.timeline-step.completed .timeline-icon { border-color:#58e5a3; background:#10251f; }.timeline-step.current { color:#fff; }.timeline-step.current .timeline-icon { border-color:#ff4fd8; background:#ff4fd8; color:#160b15; box-shadow:0 0 14px #ff4fd877; }.timeline-step.problem { color:#ffbd59; }.timeline-step.problem .timeline-icon { border-color:#ffbd59; background:#2a1e0b; }
.coach-layout { display:grid; grid-template-columns:minmax(0,1.65fr) minmax(300px,.8fr); gap:16px; }.coach-sidebar { display:grid; gap:12px; align-content:start; }
.coach-now { position:relative; min-height:360px; padding:34px 38px 30px; overflow:hidden; border-radius:18px; background:radial-gradient(circle at 100% 0,#ff4fd81c,transparent 42%),#0b1118; box-shadow:inset 4px 0 #ff4fd8; }.coach-eyebrow { color:#ff83e4; font-size:13px; font-weight:900; letter-spacing:.2em; }.coach-now h2 { margin:12px 0 8px; color:#fff; font-size:clamp(34px,3.2vw,52px); font-weight:900; letter-spacing:.02em; }.coach-objective { max-width:760px; margin:0 0 16px; color:#b1bdca; font-size:16px; line-height:1.45; }.coach-time-pill { display:inline-flex; margin-top:5px; padding:8px 12px; border-radius:999px; background:#35163a; color:#ffd0f4; font-size:14px; font-weight:900; }
.coach-focus-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; margin:18px 0 16px; }.coach-focus-action { --focus:#ff4fd8; display:grid; grid-template-columns:58px 1fr; gap:13px; align-items:center; min-height:86px; padding:14px 16px; border-radius:13px; background:#101822; box-shadow:inset 4px 0 var(--focus),0 8px 24px #0005; }.coach-focus-action.deck-a { --focus:#36d7ff; }.coach-focus-action.mixer { --focus:#ffb648; }.coach-focus-action.done { --focus:#58e5a3; }.coach-focus-icon { display:grid; place-items:center; width:52px; height:52px; border:1px solid color-mix(in srgb,var(--focus) 65%,#fff); border-radius:13px; background:color-mix(in srgb,var(--focus) 12%,#121820); color:var(--focus); font-size:28px; font-weight:900; }.coach-focus-copy { min-width:0; }.coach-focus-copy small { display:block; margin-bottom:3px; color:var(--focus); font-size:11px; font-weight:900; letter-spacing:.14em; }.coach-focus-copy strong { display:block; color:#fff; font-size:clamp(18px,1.55vw,24px); line-height:1.2; }.coach-focus-copy em { display:block; margin-top:7px; color:#9fadc0; font-size:12px; font-style:normal; font-weight:700; }.coach-focus-action.done strong { color:#58e5a3; }
.coach-actions { display:grid; gap:10px; }.coach-action { display:grid; grid-template-columns:42px 1fr; gap:12px; align-items:center; padding:13px 0; }.coach-action + .coach-action { border-top:1px solid #222c38; }.coach-action-icon { display:grid; place-items:center; width:40px; height:40px; border-radius:10px; background:#171e27; color:#fff; font-size:20px; }.coach-action-copy small { display:block; margin-bottom:2px; font-size:10px; font-weight:900; letter-spacing:.13em; }.coach-action-copy strong { display:block; color:#f7f9fc; font-size:clamp(20px,2.2vw,30px); line-height:1.15; }.coach-action.deck-a small { color:#36d7ff; }.coach-action.deck-b small { color:#ff4fd8; }.coach-action.mixer small { color:#ffb648; }.coach-action.done strong { color:#58e5a3; text-decoration:line-through; opacity:.8; }.coach-action.problem strong { color:#ffbd59; }
.visual-mixer { display:grid; grid-template-columns:minmax(0,1fr) 150px minmax(0,1fr); gap:18px; margin-top:18px; padding:20px; border-radius:16px; background:linear-gradient(180deg,#0a0f15,#070a0e); box-shadow:inset 0 0 0 1px #273241,inset 0 18px 45px #11192366; }.visual-deck { --deck:#36d7ff; display:grid; gap:16px; min-width:0; padding:18px; border-radius:14px; background:#0d141c; }.visual-deck.deck-b { --deck:#ff4fd8; }.visual-deck-title { display:flex; justify-content:space-between; color:var(--deck); font-size:13px; font-weight:900; letter-spacing:.16em; }.visual-deck-title span:last-child { color:#78869a; font-size:10px; }.visual-knobs { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; }.coach-knob-control { display:grid; justify-items:center; gap:7px; min-width:0; padding:10px 5px; border-radius:10px; opacity:.55; transition:opacity .15s,background .15s,box-shadow .15s; }.coach-knob-control.involved { opacity:1; background:color-mix(in srgb,var(--deck) 10%,transparent); box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--deck) 60%,transparent),0 0 22px color-mix(in srgb,var(--deck) 20%,transparent); }.coach-knob-face { position:relative; width:68px; height:68px; border:3px solid #465365; border-radius:50%; background:radial-gradient(circle at 38% 30%,#46515e,#171d24 60%,#05070a); box-shadow:0 5px 10px #000b,inset 0 0 0 2px #0b0e12; }.coach-knob-control.involved .coach-knob-face { border-color:var(--deck); }.coach-knob-student,.coach-knob-ghost { position:absolute; inset:5px; border-radius:50%; }.coach-knob-student span { position:absolute; top:0; left:calc(50% - 1px); width:3px; height:26px; border-radius:2px; background:var(--deck); box-shadow:0 0 7px var(--deck); }.coach-knob-ghost span { position:absolute; top:-11px; left:calc(50% - 4px); width:8px; height:9px; border-radius:4px 4px 1px 1px; background:#fff; box-shadow:0 0 9px #fff; }.coach-knob-label { color:#d3dbe5; font-size:11px; font-weight:900; }.coach-knob-readout { min-height:20px; color:#8391a4; font-size:10px; font-weight:700; text-align:center; }.coach-knob-control.involved .coach-knob-readout { color:var(--deck); font-size:11px; }.control-direction { font-size:12px; font-weight:900; }
.visual-deck-lower { display:grid; grid-template-columns:92px 1fr; gap:14px; }.coach-fader-wrap { display:grid; justify-items:center; gap:6px; padding:10px 6px; border-radius:10px; opacity:.55; }.coach-fader-wrap.involved { opacity:1; background:color-mix(in srgb,var(--deck) 10%,transparent); box-shadow:inset 0 0 0 2px color-mix(in srgb,var(--deck) 60%,transparent); }.coach-fader { position:relative; width:48px; height:145px; }.coach-fader-rail { position:absolute; top:4px; bottom:4px; left:22px; width:5px; border-radius:3px; background:#020305; box-shadow:inset 0 0 0 1px #455164; }.coach-fader-target { position:absolute; left:3px; width:42px; height:4px; background:#fff; box-shadow:0 0 8px #fff; }.coach-fader-handle { position:absolute; left:1px; width:46px; height:18px; border:1px solid #6b7889; border-radius:4px; background:linear-gradient(#596575,#12161b); box-shadow:0 3px 7px #000; }.coach-button-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:10px; align-content:start; }.coach-mixer-button { position:relative; min-height:58px; padding:11px 6px 7px; border:1px solid #3a4656; border-radius:9px; background:linear-gradient(#28313c,#11151a); color:#8491a3; font-size:11px; font-weight:900; text-align:center; opacity:.62; }.coach-mixer-button.on { color:#eaf6ff; }.coach-mixer-button .button-led { display:block; width:9px; height:9px; margin:0 auto 6px; border-radius:50%; background:#465265; }.coach-mixer-button.on .button-led { background:var(--deck); box-shadow:0 0 10px var(--deck); }.coach-mixer-button.involved { opacity:1; border:2px solid var(--deck); color:#fff; box-shadow:0 0 20px color-mix(in srgb,var(--deck) 28%,transparent); }.coach-mixer-button.involved::after { content:"AHORA"; position:absolute; top:4px; right:5px; color:var(--deck); font-size:7px; letter-spacing:.08em; }
.visual-center { display:grid; align-content:end; min-width:0; padding:10px 5px 16px; }.visual-center-label { margin-bottom:8px; color:#ffb648; font-size:8px; font-weight:900; letter-spacing:.12em; text-align:center; }.coach-crossfader { position:relative; height:42px; padding:0 8px; opacity:.48; }.coach-crossfader.involved { opacity:1; }.coach-cross-rail { position:absolute; top:19px; left:8px; right:8px; height:4px; border-radius:3px; background:#020305; box-shadow:inset 0 0 0 1px #354050; }.coach-cross-target { position:absolute; top:8px; width:3px; height:25px; background:#fff; box-shadow:0 0 7px #fff; }.coach-cross-handle { position:absolute; top:7px; width:15px; height:28px; border:1px solid #657181; border-radius:3px; background:linear-gradient(90deg,#4b5663,#12161b); }.coach-cross-labels { display:flex; justify-content:space-between; color:#758295; font-size:8px; font-weight:900; }.coach-action-strip { display:flex; flex-wrap:wrap; gap:7px; margin-top:14px; }.coach-action-chip { display:flex; align-items:center; gap:6px; padding:6px 9px; border-radius:999px; background:#131b24; color:#aab6c4; font-size:9px; font-weight:800; }.coach-action-chip.deck-a { box-shadow:inset 2px 0 #36d7ff; }.coach-action-chip.deck-b { box-shadow:inset 2px 0 #ff4fd8; }.coach-action-chip.mixer { box-shadow:inset 2px 0 #ffb648; }.coach-action-chip.done { color:#58e5a3; }.mixer-legend { display:flex; justify-content:center; gap:14px; margin-top:7px; color:#566477; font-size:7px; }.mixer-legend i { display:inline-block; width:8px; height:2px; margin-right:4px; vertical-align:middle; }.mixer-legend .student { background:#36d7ff; }.mixer-legend .teacher { background:#fff; }
.coach-side-card { padding:22px 23px; border-radius:14px; background:#0b1118; }.coach-side-title { margin-bottom:14px; color:#91a0b4; font-size:11px; font-weight:900; letter-spacing:.16em; }.coach-next-time { margin:-7px 0 12px; color:#ffc9f1; font-size:15px; font-weight:900; }.coach-next-intent { margin-bottom:10px; color:#f5f7fa; font-size:21px; font-weight:900; }.coach-next-action { display:flex; gap:10px; padding:9px 0; color:#ccd4de; font-size:14px; line-height:1.4; }.coach-empty-note { color:#8b99ab; font-size:14px; line-height:1.5; }
.feedback-list { display:grid; gap:13px; }.feedback-item { display:grid; grid-template-columns:26px 1fr; gap:9px; color:#aeb8c5; font-size:14px; line-height:1.35; }.feedback-item.success { color:#58e5a3; }.feedback-item.warning { color:#ffbd59; }.feedback-item.problem { color:#ff7b76; }.feedback-item.pending { color:#91a0b3; }.feedback-copy { display:grid; gap:3px; }.feedback-verdict { font-size:15px; font-weight:900; letter-spacing:.09em; }.feedback-detail { color:#a0adbd; font-size:12px; }.feedback-combo { margin-top:13px; color:#ffb648; font-size:14px; font-weight:900; letter-spacing:.12em; }
.guided-controls { display:flex; justify-content:space-between; align-items:center; gap:12px; padding-top:2px; }.practice-progress { color:#7e8b9c; font-size:12px; }.guided-actions { display:flex; gap:9px; }
.result-score { color:#ff4fd8; font-size:48px; font-weight:900; }.result-row { display:grid; grid-template-columns:34px 1fr auto; gap:10px; align-items:center; padding:11px 13px; border:1px solid #263140; border-radius:10px; background:#0b1118; }.result-ok { color:#58e5a3; }.result-missed { color:#ffb648; }
.lesson-plan-dialog{position:relative;width:min(980px,calc(100vw - 48px));max-width:980px;max-height:86vh;padding:0!important;overflow:hidden;background:#0d141d!important;color:#edf3fa}.lesson-plan-close{position:absolute!important;top:12px;right:14px;z-index:4;color:#b9c5d3!important}.lesson-plan-header{display:flex;justify-content:space-between;align-items:start;gap:18px;padding:20px 62px 14px 24px;border-bottom:1px solid #273343}.lesson-plan-header h2{margin:3px 0 5px;font-size:26px}.lesson-plan-header p{margin:0;color:#8f9daf}.lesson-plan-count{flex:0 0 auto;padding:7px 11px;border-radius:999px;background:#281329;color:#ff8be6;font-size:11px;font-weight:900}.lesson-plan-list{display:grid;gap:11px;max-height:calc(86vh - 168px);padding:14px 18px;overflow-y:auto}.lesson-plan-moment{padding:9px;border:1px solid #25303e;border-radius:12px;background:#080e15;transition:opacity .15s,border-color .15s}.lesson-plan-moment.current{border-color:#ff4fd8;box-shadow:0 0 18px #ff4fd81c}.lesson-plan-moment.locked{opacity:.42}.lesson-plan-moment-head{display:flex;align-items:center;gap:9px;margin-bottom:8px;padding:0 3px}.lesson-plan-time{color:#ffb648;font-family:monospace;font-size:11px;font-weight:800}.lesson-plan-now,.lesson-plan-simultaneous{padding:4px 7px;border-radius:999px;font-size:8px;font-weight:950;letter-spacing:.1em}.lesson-plan-now{display:none;background:#45133c;color:#ff91e8}.lesson-plan-moment.current .lesson-plan-now{display:inline-flex}.lesson-plan-simultaneous{background:#172738;color:#8cddff}.lesson-plan-actions{display:grid;grid-template-columns:1fr;gap:7px}.lesson-plan-actions.simultaneous{grid-template-columns:repeat(2,minmax(0,1fr))}.lesson-plan-row{display:grid;grid-template-columns:34px 78px 1fr;gap:9px;align-items:center;min-height:50px;padding:8px 10px;border:1px solid #25303e;border-radius:9px;background:#0c141d}.lesson-plan-row.current{border-color:#6d365f;background:#17101a}.lesson-plan-row.completed{border-color:#2f8a63;background:#0d211a;opacity:.78}.lesson-plan-order{display:grid;place-items:center;width:27px;height:27px;border-radius:50%;background:#1b2531;color:#fff;font-size:11px;font-weight:900}.lesson-plan-row.current .lesson-plan-order{background:#ff4fd8;color:#180b15}.lesson-plan-row.completed .lesson-plan-order{background:#58e5a3;color:#06130d}.lesson-plan-section{color:#7bdfff;font-size:10px;font-weight:900;letter-spacing:.08em}.lesson-plan-row.deck-b .lesson-plan-section{color:#ff75df}.lesson-plan-row.mixer .lesson-plan-section{color:#ffb648}.lesson-plan-instruction{color:#e7edf5;font-size:13px;font-weight:750;line-height:1.3}.lesson-plan-row.completed .lesson-plan-instruction{color:#72e9ad;text-decoration:line-through}.lesson-plan-footer{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:11px 18px;border-top:1px solid #273343;background:#0a1017}.lesson-plan-live{color:#58e5a3;font-size:11px;font-weight:850}.lesson-plan-footer-actions{display:flex;gap:8px}
.calibration-summary { color:#ffb4ed; font-weight:700; }.hardware-legend { display:flex; flex-wrap:wrap; gap:16px; margin:10px 0 14px; color:#8fa0b5; font-size:12px; }.legend-current,.legend-target { display:inline-block; width:12px; height:3px; margin-right:5px; vertical-align:middle; }.legend-current { background:#36d7ff; }.legend-target { background:#ff4fd8; }.hardware-mixer { display:grid; grid-template-columns:1fr .72fr 1fr; gap:12px; margin:12px 0 18px; }.hardware-deck,.hardware-center { padding:16px; border:1px solid #303a48; border-radius:16px; background:linear-gradient(160deg,#171d25,#090d12); box-shadow:inset 0 0 24px #0005; }.hardware-deck.deck-a { border-top:2px solid #36d7ff; }.hardware-deck.deck-b { border-top:2px solid #ff4fd8; }.hardware-title { margin-bottom:13px; color:#d9e2ec; font-size:12px; font-weight:900; letter-spacing:.14em; text-align:center; }.knob-bank { display:grid; grid-template-columns:repeat(3,1fr); gap:14px 8px; }.hw-control { display:grid; justify-items:center; gap:6px; min-width:0; }.hw-label { color:#c7d0dc; font-size:10px; font-weight:800; letter-spacing:.05em; text-align:center; }.hw-values { color:#778598; font-size:9px; text-align:center; }.knob-face { position:relative; width:52px; height:52px; border:3px solid #3a4553; border-radius:50%; background:radial-gradient(circle at 40% 32%,#3a414b,#15191f 62%,#07090c); box-shadow:0 5px 8px #0009,inset 0 0 0 2px #0b0e12; }.hw-control.matched .knob-face { border-color:#3a9b70; }.knob-pointer,.knob-target { position:absolute; inset:4px; border-radius:50%; }.knob-pointer span { position:absolute; top:1px; left:calc(50% - 1px); width:2px; height:19px; border-radius:2px; background:#36d7ff; box-shadow:0 0 5px #36d7ff; }.knob-target span { position:absolute; top:-8px; left:calc(50% - 2px); width:4px; height:8px; border-radius:2px; background:#ff4fd8; box-shadow:0 0 5px #ff4fd8; }
.deck-lower { display:grid; grid-template-columns:84px 1fr; gap:12px; margin-top:18px; }.vertical-fader { position:relative; width:48px; height:150px; margin:4px auto; }.vertical-fader .fader-rail { position:absolute; top:5px; bottom:5px; left:22px; width:4px; border-radius:4px; background:#05070a; box-shadow:inset 0 0 0 1px #35404d; }.vertical-fader .target-line { position:absolute; left:6px; width:36px; height:3px; background:#ff4fd8; box-shadow:0 0 5px #ff4fd8; }.vertical-fader .fader-handle { position:absolute; left:3px; width:42px; height:17px; border-radius:4px; background:linear-gradient(#4b5562,#15191e); border:1px solid #667280; box-shadow:0 3px 6px #000; }.fader-name { color:#c7d0dc; font-size:10px; font-weight:800; text-align:center; }.button-bank { display:grid; grid-template-columns:1fr 1fr; align-content:start; gap:8px; }.hw-button { min-height:44px; padding:7px; border:1px solid #3a4553; border-radius:7px; background:linear-gradient(#2c333c,#12161b); color:#aab5c2; font-size:9px; font-weight:800; text-align:center; }.hw-button .led { display:block; width:7px; height:7px; margin:0 auto 5px; border-radius:50%; background:#3b4652; }.hw-button.on .led { background:#36d7ff; box-shadow:0 0 7px #36d7ff; }.hw-button.mismatch { border-color:#ff4fd8; }.hw-button .target-state { display:block; margin-top:3px; color:#ff83e4; font-size:8px; }.track-slider,.crossfader-visual { position:relative; height:38px; margin:9px 4px 15px; }.horizontal-rail { position:absolute; top:17px; left:5px; right:5px; height:4px; border-radius:4px; background:#05070a; box-shadow:inset 0 0 0 1px #35404d; }.horizontal-target { position:absolute; top:7px; width:3px; height:24px; background:#ff4fd8; box-shadow:0 0 5px #ff4fd8; }.horizontal-handle { position:absolute; top:5px; width:17px; height:28px; border-radius:4px; background:linear-gradient(90deg,#4b5562,#15191e); border:1px solid #667280; box-shadow:2px 2px 6px #000; }.center-block { margin-top:18px; padding:11px; border:1px solid #2e3947; border-radius:11px; background:#0b1016; }.clock-display { padding:12px; border:1px solid #2e3947; border-radius:9px; background:#070b10; text-align:center; }.clock-bpm { color:#f4f7fb; font-size:24px; font-weight:900; }.clock-target { color:#ff83e4; font-size:10px; }.hardware-instructions { display:grid; gap:6px; margin:10px 0; }.hardware-instruction { padding:8px 10px; border-left:3px solid #ff4fd8; border-radius:6px; background:#17101a; color:#d7b5d0; font-size:11px; }
.coach-now,.visual-mixer{box-sizing:border-box}.coach-knob-control,.coach-fader-wrap,.coach-mixer-button { position:relative; }.control-move-arrow { position:absolute; z-index:5; display:grid; justify-items:center; right:-9px; top:22px; color:var(--deck,#ffb648); filter:drop-shadow(0 0 8px currentColor); pointer-events:none; }.control-move-arrow span { font-size:34px; font-weight:900; line-height:.8; }.control-move-arrow small { margin-top:4px; font-size:8px; font-weight:950; letter-spacing:.08em; }.control-move-arrow.ready { color:#58e5a3; }.control-move-arrow.tap { right:3px; top:-13px; color:var(--deck,#ffb648); }.control-move-arrow.tap span { font-size:17px; }.coach-fader-wrap>.control-move-arrow { right:-5px; top:62px; }.coach-crossfader>.control-move-arrow { right:0; top:-35px; }.coach-crossfader>.control-move-arrow.down,.coach-crossfader>.control-move-arrow.up { transform:rotate(90deg); }
.prepare-product-page{width:min(1540px,calc(100vw - 28px));padding-top:24px}.prepare-product-page .product-header{margin-bottom:16px}.prepare-shell{display:grid;grid-template-columns:minmax(270px,.68fr) minmax(0,1.65fr);grid-template-areas:"chip controller" "tracks controller" "readiness controller" "title controller" "summary controller" "legend controller" "instructions controller" "note controller" "plan controller" "start controller";column-gap:18px;row-gap:12px;align-items:start;padding:20px}.prepare-shell>.stage-chip{grid-area:chip}.prepare-shell>.prep-grid{grid-area:tracks;grid-template-columns:1fr;margin:0}.prepare-shell>.readiness-list{grid-area:readiness}.prepare-shell>.prepare-title{grid-area:title;margin:4px 0 0}.prepare-title h2{margin:0;color:#f4f7fb;font-size:clamp(23px,2vw,32px);line-height:1.08}.prepare-shell>.calibration-summary{grid-area:summary}.prepare-shell>.prepare-calibration-view{display:contents}.prepare-shell .hardware-legend{grid-area:legend;margin:0}.prepare-shell .hardware-instructions{grid-area:instructions;margin:0;max-height:210px;overflow:auto}.prepare-shell .hardware-mixer{grid-area:controller;align-self:start;margin:0;min-width:0}.prepare-shell>.prepare-note{grid-area:note}.prepare-shell>.prepare-plan-button{grid-area:plan;justify-self:start}.prepare-shell>.prepare-start-button{grid-area:start;justify-self:start}.prepare-shell .track-check-card{padding:13px}.prepare-shell .track-check-card .track-name{min-height:0;margin-bottom:8px;font-size:14px}.prepare-shell .readiness-list{gap:6px;padding:12px}.prepare-shell .readiness-line{font-size:12px}
@media(min-width:1051px){
  .guided-product-page{width:min(1640px,calc(100vw - 24px));height:calc(100dvh - 32px);padding:8px 0 10px;overflow:hidden}
  .guided-topnav{height:30px;margin:0}
  .guided-shell{grid-template-rows:auto auto minmax(0,1fr) auto;height:calc(100dvh - 80px);max-height:908px;padding:12px 14px;gap:10px;overflow:hidden}
  .coach-context{grid-template-columns:minmax(230px,1.7fr) repeat(5,minmax(100px,.62fr));gap:8px}.context-cell{min-height:56px;padding:8px 12px}.context-cell strong{font-size:14px}
  .coach-timeline{padding:2px 2px 7px}.timeline-step{min-width:145px}.timeline-step .timeline-icon{width:26px;height:26px}.timeline-step .timeline-label{font-size:11px}
  .coach-layout{grid-template-columns:minmax(0,1fr) 300px;min-height:0;gap:12px}.coach-sidebar{min-height:0;grid-template-rows:auto minmax(0,1fr)}.coach-side-card{padding:17px 18px;overflow:auto}
  .coach-now{display:grid;grid-template-columns:minmax(230px,.38fr) minmax(0,1fr);gap:18px;min-height:0;height:100%;max-height:100%;padding:20px 22px}.coach-brief{min-width:0;align-self:start}.coach-stage{display:grid;min-width:0;min-height:0;overflow:hidden}.coach-now h2{font-size:clamp(30px,2.5vw,43px)}.coach-objective{font-size:14px}.coach-time-pill{font-size:12px;padding:6px 10px}
  .coach-focus-grid{grid-template-columns:1fr;gap:9px;margin:15px 0 0;max-height:310px;overflow:auto}.coach-focus-action{grid-template-columns:44px 1fr;min-height:68px;padding:10px 11px}.coach-focus-icon{width:40px;height:40px;font-size:22px}.coach-focus-copy strong{font-size:17px}.coach-focus-copy em{font-size:10px;margin-top:4px}
  .visual-mixer{grid-template-columns:minmax(0,1fr) 105px minmax(0,1fr);align-self:stretch;min-height:0;height:100%;max-height:570px;margin:0;padding:13px;gap:10px}.visual-deck{align-self:center;min-height:0;gap:11px;padding:13px}.visual-deck-title{font-size:12px}.visual-knobs{gap:4px}.coach-knob-control{gap:4px;padding:7px 2px}.coach-knob-face{width:64px;height:64px}.coach-knob-student span{height:24px}.coach-knob-label{font-size:10px}.coach-knob-readout{font-size:9px}.visual-deck-lower{grid-template-columns:78px 1fr;gap:9px}.coach-fader{height:130px}.coach-button-grid{gap:6px}.coach-mixer-button{min-height:48px;padding:8px 4px 5px;font-size:10px}.visual-center{padding-bottom:12px}.mixer-legend{font-size:8px}
  .guided-controls{min-height:34px}.practice-progress{font-size:11px}
}
@media(min-width:1051px) and (max-width:1400px){
  .coach-now{grid-template-columns:1fr;grid-template-rows:104px minmax(0,1fr);align-self:start;height:calc(100dvh - 266px);max-height:calc(100dvh - 266px);min-height:0;gap:8px;padding:12px 14px;overflow:hidden}.coach-brief{display:grid;grid-template-columns:minmax(205px,.42fr) minmax(0,1fr);grid-template-rows:auto auto auto auto;column-gap:14px;align-items:start;max-height:104px;overflow:hidden}.coach-eyebrow,.coach-now h2,.coach-objective,.coach-time-pill{grid-column:1}.coach-eyebrow{grid-row:1}.coach-now h2{grid-row:2;margin:3px 0 1px;font-size:24px}.coach-objective{grid-row:3;margin-bottom:3px;font-size:10px}.coach-time-pill{grid-row:4;width:max-content;margin:0}.coach-focus-grid{grid-column:2;grid-row:1/5;align-self:center;grid-template-columns:repeat(2,minmax(0,1fr));margin:0;max-height:100px}.coach-focus-action{min-height:46px}.coach-stage{min-height:0;overflow:hidden}.visual-mixer{min-height:0;max-height:none;overflow:hidden}.coach-layout{grid-template-columns:minmax(0,1fr) 260px;overflow:hidden}.coach-side-card{padding:14px 15px}.coach-next-intent{font-size:17px}.coach-next-action,.feedback-item{font-size:12px}
  .coach-knob-face{width:54px;height:54px}.coach-knob-student span{height:19px}.visual-deck{gap:5px;padding:7px 9px}.visual-deck-lower{grid-template-columns:64px 1fr;gap:5px}.coach-fader{height:84px}.coach-button-grid{gap:4px}.coach-mixer-button{min-height:31px;padding:4px 3px 2px;font-size:8px}.coach-mixer-button .button-led{margin-bottom:3px}
}
@media(max-width:800px){.mode-grid,.lesson-tracks{grid-template-columns:1fr}.product-header h1{font-size:32px}}
@media(max-width:850px){.prep-grid,.review-grid,.moment-lanes,.hardware-mixer{grid-template-columns:1fr}.timeline-row{grid-template-columns:70px 1fr}.timeline-detail{grid-column:1/-1}.hardware-center{order:3}}
@media(max-width:900px){.prepare-product-page{width:min(100%,calc(100vw - 20px))}.prepare-shell{display:flex;flex-direction:column}.prepare-shell>.prepare-calibration-view{display:block;width:100%}.prepare-shell .hardware-mixer{width:100%}.prepare-shell>.prep-grid,.prepare-shell>.readiness-list,.prepare-shell>.prepare-title,.prepare-shell>.calibration-summary,.prepare-shell>.prepare-note{width:100%}}
@media(max-width:1050px){.coach-layout{grid-template-columns:1fr}.coach-sidebar{grid-template-columns:1fr 1fr}.visual-knobs{grid-template-columns:repeat(5,1fr)}.coach-now{padding:30px}.guided-controls{align-items:flex-start;flex-direction:column}.guided-actions{width:100%;flex-wrap:wrap}}
@media(min-width:901px) and (max-width:1050px){
  .guided-product-page{width:calc(100vw - 16px);height:calc(100dvh - 40px);padding:5px 0 7px;overflow:hidden}.guided-topnav{height:27px;margin:0}.guided-shell{grid-template-rows:auto auto minmax(0,1fr) auto;height:calc(100dvh - 79px);padding:9px 11px;gap:7px;overflow:hidden}
  .coach-context{grid-template-columns:1.5fr repeat(2,1fr);gap:6px}.context-cell{min-height:42px;padding:5px 9px}.context-cell span{font-size:8px}.context-cell strong{font-size:12px}.coach-timeline{padding:0 2px 4px}.timeline-step{min-width:125px}.timeline-step .timeline-icon{width:23px;height:23px}.timeline-step .timeline-label{font-size:9px}
  .coach-layout{display:grid;grid-template-rows:minmax(0,1fr) 88px;gap:7px;min-height:0}.coach-now{display:grid;grid-template-columns:190px minmax(0,1fr);gap:9px;min-height:0;height:100%;padding:12px 14px}.coach-brief{min-width:0}.coach-now h2{margin:5px 0;font-size:26px}.coach-objective{margin-bottom:7px;font-size:11px}.coach-time-pill{padding:4px 7px;font-size:10px}.coach-focus-grid{grid-template-columns:1fr;gap:5px;margin:8px 0 0;max-height:155px;overflow:auto}.coach-focus-action{grid-template-columns:32px 1fr;min-height:48px;padding:6px 8px}.coach-focus-icon{width:29px;height:29px;font-size:17px}.coach-focus-copy small{font-size:8px}.coach-focus-copy strong{font-size:13px}.coach-focus-copy em{margin-top:2px;font-size:8px}
  .coach-stage{display:grid;min-width:0;min-height:0}.visual-mixer{grid-template-columns:minmax(0,1fr) 70px minmax(0,1fr);height:100%;margin:0;padding:7px;gap:5px;overflow:hidden}.visual-deck{align-self:center;gap:5px;padding:7px}.visual-deck-title{font-size:10px}.visual-deck-title span:last-child{font-size:8px}.visual-knobs{gap:1px}.coach-knob-control{gap:2px;padding:3px 1px}.coach-knob-face{width:50px;height:50px}.coach-knob-student span{height:18px}.coach-knob-label{font-size:8px}.coach-knob-readout{min-height:12px;font-size:7px}.visual-deck-lower{grid-template-columns:56px 1fr;gap:4px}.coach-fader{height:78px}.coach-fader-wrap{gap:2px;padding:3px}.coach-button-grid{gap:3px}.coach-mixer-button{min-height:30px;padding:4px 2px 2px;font-size:8px}.coach-mixer-button .button-led{width:6px;height:6px;margin-bottom:2px}.visual-center{padding:5px 2px 8px}.mixer-legend{margin-top:3px;font-size:7px}
  .coach-sidebar{grid-template-columns:1fr 1fr;gap:7px}.coach-side-card{padding:9px 11px}.coach-side-title{margin-bottom:5px;font-size:8px}.coach-next-time{margin:0 0 4px;font-size:10px}.coach-next-intent{margin-bottom:3px;font-size:13px}.coach-next-action{padding:2px 0;font-size:9px}.feedback-list{grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}.feedback-item{grid-template-columns:16px 1fr;gap:3px;font-size:8px}.feedback-verdict{font-size:9px}.feedback-detail{font-size:7px}.guided-controls{min-height:30px;align-items:center;flex-direction:row}.guided-actions{width:auto;flex-wrap:nowrap}.practice-progress{font-size:9px}
}
@media(max-width:900px){.coach-context{grid-template-columns:1fr 1fr}.context-cell.lesson{grid-column:1/-1}.coach-sidebar{grid-template-columns:1fr}.visual-mixer{grid-template-columns:1fr;gap:12px}.visual-center{order:3;padding:12px 20px}.visual-knobs{grid-template-columns:repeat(5,1fr)}.coach-now{min-height:0;padding:25px 20px}.coach-focus-grid{grid-template-columns:1fr}}
@media(max-width:620px){.visual-deck{padding:13px}.visual-knobs{grid-template-columns:repeat(3,1fr)}.coach-knob-control{padding:7px 3px}.coach-knob-face{width:58px;height:58px}.coach-knob-student span{height:21px}.visual-deck-lower{grid-template-columns:78px 1fr}.coach-fader{height:125px}.coach-button-grid{gap:7px}.coach-mixer-button{min-height:50px;font-size:10px}}
@media(max-width:520px){.coach-context{grid-template-columns:1fr 1fr}.context-cell{min-width:0;min-height:58px;padding:8px 10px}.context-cell strong{font-size:14px}.coach-now{padding:22px 14px}.guided-shell{padding:11px}.coach-layout{gap:12px}.visual-mixer{padding:10px;margin-left:-4px;margin-right:-4px}.coach-focus-action{grid-template-columns:48px 1fr;padding:12px}.coach-focus-icon{width:44px;height:44px}.coach-focus-copy strong{font-size:17px}}
.rhythm-shell{display:grid!important;grid-template-rows:auto auto minmax(230px,1fr) auto auto!important;gap:10px!important;min-height:0!important;height:auto!important;max-height:none!important;padding:14px!important;overflow:visible!important;background:radial-gradient(circle at 50% 100%,#df31cc18,transparent 34%),linear-gradient(155deg,#0c1420,#080d15)!important}.rhythm-header{display:grid;grid-template-columns:minmax(200px,1.7fr) repeat(3,minmax(92px,.7fr)) auto;gap:10px;align-items:center;padding:10px 14px;border:1px solid #293647;border-radius:13px;background:#0a1018}.rhythm-meta{display:grid;gap:3px;min-width:0}.rhythm-meta span{color:#8494a8;font-size:9px;font-weight:900;letter-spacing:.12em}.rhythm-meta strong{overflow:hidden;color:#f5f8fc;font-size:14px;text-overflow:ellipsis;white-space:nowrap}.rhythm-meta.phase strong{color:#ff75df}.rhythm-exit{justify-self:end;color:#d88cff;font-size:11px;font-weight:800}.rhythm-phases{display:grid;grid-template-columns:repeat(6,1fr);gap:0;padding:0 18px}.rhythm-phase{position:relative;display:grid;justify-items:center;gap:4px;color:#718095;font-size:10px;font-weight:800;text-align:center}.rhythm-phase:not(:last-child)::after{position:absolute;top:12px;left:calc(50% + 16px);right:calc(-50% + 16px);height:2px;background:#344152;content:""}.rhythm-phase-dot{z-index:1;display:grid;place-items:center;width:24px;height:24px;border:1px solid #536176;border-radius:50%;background:#101722;font-size:11px}.rhythm-phase.completed{color:#67eaa8}.rhythm-phase.completed .rhythm-phase-dot{border-color:#57d999;background:#123526}.rhythm-phase.completed:not(:last-child)::after{background:#57d999}.rhythm-phase.current{color:#ff8ae5}.rhythm-phase.current .rhythm-phase-dot{border-color:#ff4fd8;background:#46163f;box-shadow:0 0 18px #ff4fd899}.rhythm-stage{display:grid;grid-template-columns:minmax(0,1fr) 220px;gap:10px;min-height:0}.rhythm-lane{position:relative;min-height:230px;overflow:hidden;border:1px solid #2a384a;border-radius:14px;background:linear-gradient(180deg,#0b121c,#090d14)}.rhythm-lane::before{position:absolute;inset:50% 0 auto;height:1px;background:#334052;content:""}.rhythm-now{position:absolute;z-index:3;top:0;bottom:34px;left:62%;width:2px;background:#ff75df;box-shadow:0 0 14px #ff4fd8}.rhythm-now::before,.rhythm-now::after{position:absolute;left:50%;transform:translateX(-50%);color:#ff83e4;font-size:10px;font-weight:950;letter-spacing:.12em}.rhythm-now::before{top:-4px;content:"AHORA";transform:translate(-50%,-100%)}.rhythm-now::after{bottom:-22px;content:"AHORA"}.rhythm-now i{position:absolute;top:47%;left:-5px;width:10px;height:10px;border-radius:50%;background:#fff;box-shadow:0 0 16px #fff}.rhythm-card{position:absolute;z-index:2;top:29px;display:grid;gap:5px;min-width:92px;max-width:148px;padding:9px 11px;border:1px solid #375069;border-radius:8px;background:#121c28;box-shadow:0 8px 18px #0008;transform:translateX(-50%);transition:left .12s linear}.rhythm-card.current{border-color:#ff4fd8;background:#30152f;box-shadow:0 0 20px #ff4fd855}.rhythm-card.completed{opacity:.45}.rhythm-card.problem{border-color:#ffbd59}.rhythm-card-title{color:#f1f5f9;font-size:11px;font-weight:900;white-space:nowrap}.rhythm-card-actions{display:flex;flex-wrap:wrap;gap:4px}.rhythm-action{color:#a8b7c8;font-size:9px;font-weight:800;white-space:nowrap}.rhythm-card.current .rhythm-action{color:#ffc5f5}.rhythm-scale{position:absolute;right:7%;bottom:9px;left:7%;display:flex;justify-content:space-between;color:#8492a5;font-family:monospace;font-size:10px;font-weight:800}.rhythm-scale strong{color:#ff75df}.rhythm-wait{position:absolute;inset:0;display:grid;place-items:center;color:#acb9c9;font-size:15px;font-weight:800}.rhythm-next{padding:16px;border:1px solid #2b394b;border-radius:14px;background:#0b121c}.rhythm-next small{display:block;margin-bottom:8px;color:#93a3b8;font-size:9px;font-weight:900;letter-spacing:.13em}.rhythm-next-time{margin-bottom:6px;color:#ffbd59;font-size:12px;font-weight:900}.rhythm-next h3{margin:0 0 10px;color:#fff;font-size:17px}.rhythm-next-action{display:block;padding:5px 0;border-top:1px solid #1f2b39;color:#b9c7d6;font-size:11px;font-weight:800}.rhythm-feedback{display:flex;align-items:center;gap:14px;min-height:55px;padding:10px 16px;border:1px solid #293647;border-radius:13px;background:#0b121c}.rhythm-verdict{min-width:120px;color:#8ea0b4;font-size:22px;font-style:italic;font-weight:950;letter-spacing:.05em}.rhythm-verdict.success{color:#69eaa8}.rhythm-verdict.warning{color:#ffbd59}.rhythm-verdict.problem{color:#ff7670}.rhythm-feedback-detail{color:#aebdce;font-size:12px;font-weight:700}.rhythm-combo{margin-left:auto;color:#ff75df;font-size:14px;font-weight:950}.rhythm-controls{display:flex;justify-content:space-between;align-items:center;gap:12px}.rhythm-controls .practice-progress{font-size:11px}@media(max-width:900px){.rhythm-header{grid-template-columns:1fr 1fr}.rhythm-stage{grid-template-columns:1fr}.rhythm-next{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;align-items:center}.rhythm-next small,.rhythm-next-time,.rhythm-next h3{margin:0}.rhythm-phases{padding:0}.rhythm-phase{font-size:8px}.rhythm-card{max-width:118px}.rhythm-feedback{flex-wrap:wrap}}@media(max-width:620px){.rhythm-phases{grid-template-columns:repeat(3,1fr);gap:8px}.rhythm-phase:not(:last-child)::after{display:none}.rhythm-lane{min-height:250px}.rhythm-stage{gap:8px}.rhythm-next{grid-template-columns:1fr}.rhythm-card{min-width:76px;padding:7px}.rhythm-header{padding:10px}.rhythm-now{left:66%}}
.rhythm-card{min-width:64px;max-width:126px;padding:8px 10px}.rhythm-card.far{opacity:.42}.rhythm-card.status-completed{opacity:.3}.rhythm-card.status-problem{border-color:#ff7670}.rhythm-card.status-past{opacity:.22}.rhythm-card.prepare{border-color:#ffbd59;background:#2b2211;box-shadow:0 0 16px #ffbd593d}.rhythm-card.now{border-color:#ff4fd8;background:#381333;box-shadow:0 0 22px #ff4fd877;transition:none}.rhythm-card.deck-a{border-left:3px solid #36d7ff}.rhythm-card.deck-b{border-left:3px solid #ff4fd8}.rhythm-card.mixer{border-left:3px solid #ffb648}.rhythm-card-actions{justify-content:center}.rhythm-action{color:#edf3fa;font-size:11px;letter-spacing:.03em}.rhythm-card.deck-a .rhythm-action{color:#76e8ff}.rhythm-card.deck-b .rhythm-action{color:#ff9eea}.rhythm-card.mixer .rhythm-action{color:#ffd27b}.rhythm-technique{color:#fff;font-size:9px;font-weight:950;letter-spacing:.12em;text-align:center}.rhythm-lane{min-height:216px}.rhythm-stage{display:grid;grid-template-columns:1fr;gap:12px}.rhythm-action-panels{display:grid;grid-template-columns:1.35fr 1fr 1fr .9fr;gap:10px}.rhythm-level,.rhythm-missed{display:grid;align-content:center;min-height:124px;padding:16px;border:1px solid #2b394b;border-radius:13px;background:#0b121c}.rhythm-level small,.rhythm-missed small{color:#96a6bb;font-size:9px;font-weight:950;letter-spacing:.13em}.rhythm-level strong{margin:8px 0;color:#f5f7fb;font-size:17px;line-height:1.12}.rhythm-level em{color:#a7b7ca;font-size:11px;font-style:normal;font-weight:800}.rhythm-level.now{border-color:#ff4fd8;background:radial-gradient(circle at 50% 0,#70225f66,transparent 68%),#170e19;box-shadow:0 0 23px #ff4fd838}.rhythm-level.now small,.rhythm-level.now em{color:#ff9bea}.rhythm-level.now strong{font-size:22px}.rhythm-level.prepare{border-color:#a663d1;background:#171121}.rhythm-level.prepare small{color:#d090ff}.rhythm-level.prepare em{color:#dcb1ff}.rhythm-level.after{opacity:.82}.rhythm-level.deck-a{border-left:3px solid #36d7ff}.rhythm-level.deck-b{border-left:3px solid #ff4fd8}.rhythm-level.mixer{border-left:3px solid #ffb648}.rhythm-level.empty{opacity:.55}.rhythm-action-panels.waiting{grid-template-columns:1fr}.rhythm-action-panels.waiting>div{display:grid;gap:7px;place-items:center;min-height:110px;padding:18px;border:1px dashed #44566d;border-radius:13px;background:#0b121c;text-align:center}.rhythm-action-panels.waiting small{color:#8ca0b7;font-size:10px;font-weight:900;letter-spacing:.12em}.rhythm-action-panels.waiting strong{color:#f2f6fb;font-size:20px}.rhythm-action-panels.waiting em{color:#9daec1;font-size:12px;font-style:normal}.rhythm-missed{align-content:start;border-color:#61333b;background:#150e14}.rhythm-missed ul{display:grid;gap:6px;margin:10px 0 0;padding:0;list-style:none}.rhythm-missed li{display:grid;grid-template-columns:15px 1fr auto;gap:5px;align-items:center;color:#ffb3ad;font-size:10px;font-weight:800}.rhythm-missed li span,.rhythm-missed li em{color:#ff7670;font-style:normal;font-size:9px;font-weight:950}.rhythm-missed li.clear{display:block;color:#8ea1b6}.rhythm-next{display:none}@media(max-width:1000px){.rhythm-action-panels{grid-template-columns:repeat(3,1fr)}.rhythm-missed{grid-column:1/-1;min-height:auto}.rhythm-missed ul{grid-template-columns:repeat(3,1fr)}}@media(max-width:620px){.rhythm-lane{min-height:250px}.rhythm-action-panels{grid-template-columns:1fr}.rhythm-missed{grid-column:auto}.rhythm-missed ul{grid-template-columns:1fr}}
/* Legibilidad de la coreografía móvil: los tokens se leen de reojo. */
.rhythm-lane{min-height:310px}.rhythm-card{min-width:118px;max-width:290px;padding:14px 18px;border-radius:11px}.rhythm-card.duration{transform:translateX(-100%);padding-bottom:11px}.rhythm-card.deck-a{border-left-width:4px}.rhythm-card.deck-b{border-left-width:4px}.rhythm-card.mixer{border-left-width:4px}.rhythm-action{font-size:15px;font-weight:950;letter-spacing:.04em}.rhythm-card-duration{display:flex;align-items:center;gap:7px;margin-top:9px}.rhythm-card-duration i{height:4px;flex:1;border-radius:999px;background:currentColor;box-shadow:0 0 8px currentColor}.rhythm-card-duration em{color:#b8c6d6;font-size:8px;font-style:normal;font-weight:950;letter-spacing:.08em;white-space:nowrap}.rhythm-card.deck-a .rhythm-card-duration{color:#36d7ff}.rhythm-card.deck-b .rhythm-card-duration{color:#ff4fd8}.rhythm-card.mixer .rhythm-card-duration{color:#ffb648}.rhythm-prepare-progress{position:relative;height:19px;margin-top:10px;overflow:hidden;border:1px solid #765294;border-radius:999px;background:#0b0d16}.rhythm-prepare-progress i{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,#8b5cf6,#ffbd59);box-shadow:0 0 12px #c46eff;transition:width .1s linear}.rhythm-prepare-progress span{position:relative;z-index:1;display:grid;height:100%;place-items:center;color:#fff;font-size:9px;font-weight:950;letter-spacing:.08em;text-shadow:0 1px 3px #000}@media(max-width:620px){.rhythm-lane{min-height:310px}.rhythm-card{min-width:88px;max-width:180px;padding:10px}.rhythm-action{font-size:12px}}
.rhythm-card{max-width:420px}
/* Nota sostenida: cabeza fija y cola horizontal proporcional a su duración. */
.rhythm-card.duration{transform:translateX(-50%);overflow:visible}.rhythm-hold{position:absolute;z-index:0;top:calc(50% - 44px);right:50%;width:var(--hold-width);height:88px;overflow:visible;opacity:.9}.rhythm-hold .trajectory-guide{fill:none;stroke:#526074;stroke-width:1;stroke-dasharray:3 4}.rhythm-hold .trajectory-path{fill:none;stroke:currentColor;stroke-width:5;filter:drop-shadow(0 0 5px currentColor)}.rhythm-hold .trajectory-point{fill:#f7fbff;stroke:currentColor;stroke-width:2}.rhythm-card-start{position:absolute;z-index:3;top:-23px;left:50%;display:grid;justify-items:center;gap:2px;transform:translateX(-50%);pointer-events:none}.rhythm-card-start i{width:12px;height:12px;border:2px solid currentColor;border-radius:50%;background:#08111b;box-shadow:0 0 10px currentColor}.rhythm-card-start em{color:#f3f7fb;font-size:8px;font-style:normal;font-weight:950;letter-spacing:.1em;text-shadow:0 1px 3px #000}.rhythm-card.duration .rhythm-card-actions,.rhythm-card.duration .rhythm-card-duration{position:relative;z-index:1}.rhythm-card.deck-a .rhythm-hold,.rhythm-card.deck-a .rhythm-card-start{color:#36d7ff}.rhythm-card.deck-b .rhythm-hold,.rhythm-card.deck-b .rhythm-card-start{color:#ff4fd8}.rhythm-card.mixer .rhythm-hold,.rhythm-card.mixer .rhythm-card-start{color:#ffb648}.result-overview{display:grid;grid-template-columns:200px 1fr;gap:14px;margin:18px 0}.result-primary-score,.result-metrics,.result-recommendations,.result-history{padding:16px;border:1px solid #293647;border-radius:14px;background:#0b121c}.result-primary-score{display:grid;place-items:center;text-align:center}.result-primary-score .result-score{line-height:1}.result-primary-score>div{color:#8fa0b5;font-size:9px;font-weight:900;letter-spacing:.1em}.result-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.result-metrics div{padding:12px;border-radius:10px;background:#101924}.result-metrics span{display:block;color:#8293a9;font-size:9px;font-weight:900;letter-spacing:.11em}.result-metrics strong{display:block;margin-top:6px;color:#f5f8fc;font-size:20px}.result-recommendations{display:grid;gap:8px;margin:12px 0}.result-section-title{color:#8ddfff;font-size:10px;font-weight:950;letter-spacing:.13em}.result-recommendation{padding:10px 12px;border-left:3px solid #ffbd59;border-radius:7px;background:#17130d;color:#dfd1ad;font-size:13px}.result-row{grid-template-columns:34px 1fr auto}.result-row.success{border-color:#276c4e}.result-row.warning{border-color:#715525}.result-row.problem{border-color:#75363a}.result-row-feedback{margin-top:3px;color:#91a1b5;font-size:11px}.result-verdict{font-size:11px;font-weight:950;letter-spacing:.08em}.result-verdict.success{color:#58e5a3}.result-verdict.warning{color:#ffbd59}.result-verdict.problem{color:#ff7670}.result-history{display:grid;gap:7px;margin-top:16px;color:#aebdce;font-size:12px}@media(max-width:700px){.result-overview{grid-template-columns:1fr}.result-metrics{grid-template-columns:1fr}.result-row{grid-template-columns:28px 1fr}.result-verdict{grid-column:2}}
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
    "loop_size": "TAMAÑO DE LOOP",
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


def render_lesson_plan(
    steps: list[dict[str, Any]], completed_step_ids: set[str] | None = None
) -> str:
    """Listado completo que el alumno puede consultar antes de practicar."""
    completed = completed_step_ids or set()
    step_numbers = {
        str(step.get("id", "")): index
        for index, step in enumerate(steps, start=1)
    }
    moments = build_guidance_moments(steps)
    current_moment_index = next(
        (
            index
            for index, moment in enumerate(moments)
            if not all(
                str(action.get("id", "")) in completed
                for action in moment["actions"]
            )
        ),
        len(moments),
    )
    rendered_moments = []
    for moment_index, moment in enumerate(moments):
        actions = moment["actions"]
        simultaneous = len(actions) > 1
        moment_state = (
            "completed"
            if moment_index < current_moment_index
            else "current"
            if moment_index == current_moment_index
            else "locked"
        )
        rows = "".join(
            '<div class="lesson-plan-row '
            f'{escape(str(step.get("section", ""))).replace("_", "-")}'
            f'{" completed" if str(step.get("id", "")) in completed else " current" if moment_state == "current" else " locked"}" '
            f'data-step-id="{escape(str(step.get("id", "")))}" '
            f'data-order="{step_numbers[str(step.get("id", ""))]}">'
            f'<span class="lesson-plan-order">{"✓" if str(step.get("id", "")) in completed else step_numbers[str(step.get("id", ""))]}</span>'
            f'<span class="lesson-plan-section">{escape(section_label(str(step.get("section", ""))).upper())}</span>'
            f'<span class="lesson-plan-instruction">{escape(str(step.get("instruction", "")))}</span>'
            '</div>'
            for step in actions
        )
        rendered_moments.append(
            f'<div class="lesson-plan-moment {moment_state}" data-moment-index="{moment_index}"><div class="lesson-plan-moment-head">'
            f'<span class="lesson-plan-time">{format_seconds(moment.get("reference_seconds"))}</span>'
            '<span class="lesson-plan-now">AHORA</span>'
            f'{"<span class=\"lesson-plan-simultaneous\">SIMULTÁNEAS · HACÉ AMBAS</span>" if simultaneous else ""}'
            '</div><div class="lesson-plan-actions '
            f'{"simultaneous" if simultaneous else ""}">{rows}</div></div>'
        )
    body = "".join(rendered_moments)
    if not body:
        body = '<div class="coach-empty-note">La lección no tiene acciones practicables.</div>'
    return (
        '<section><div class="lesson-plan-header"><div>'
        '<div class="product-kicker">ENSAYO SIN TIEMPO</div>'
        '<h2>Probá toda la secuencia</h2>'
        '<p>Hacé las acciones en Traktor: se marcarán sin límite de tiempo y no afectarán tu puntuación.</p>'
        '</div>'
        f'<span class="lesson-plan-count">{len(completed)} / {len(steps)}</span></div>'
        f'<div class="lesson-plan-list">{body}</div></section>'
    )


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


def _moment_intent(moment: dict[str, Any] | None) -> tuple[str, str]:
    """Resume acciones técnicas como una intención que el alumno reconoce."""
    if not moment or not moment.get("actions"):
        return "LISTO", "Esperá la próxima indicación del coach."
    actions = moment["actions"]
    controls = {str(action.get("control", "")) for action in actions}
    sections = {str(action.get("section", "")) for action in actions}
    deck = next(iter(sections)) if len(sections) == 1 else None
    deck_text = section_label(deck).upper() if deck else ""
    if "low" in controls and {"deck_a", "deck_b"}.issubset(sections):
        return "BASS SWAP", "Intercambiá los graves manteniendo continuidad en la mezcla."
    if controls & {"play", "transport_cue", "cue"}:
        return (
            f"PREPARÁ {deck_text}" if deck_text else "ENTRADA",
            "Prepará la entrada del nuevo track en el momento indicado.",
        )
    if controls & {"loop_active", "loop_size"}:
        return (
            f"LOOP {deck_text}" if deck_text else "LOOP",
            "Definí y activá el loop indicado para sostener la transición.",
        )
    if controls & {"low", "mid", "high", "gain"}:
        return (
            f"AJUSTE DE EQ {deck_text}" if deck_text else "AJUSTE DE EQ",
            "Acomodá la ecualización para dejar espacio entre ambos tracks.",
        )
    if controls & {"fx_adjust", "fx_on"}:
        return "EFECTO", "Aplicá el efecto como parte de la transición."
    if controls & {"volume", "crossfader"}:
        return "MEZCLA", "Equilibrá la salida audible de ambos decks."
    if "sync" in controls:
        return "SINCRONIZACIÓN", "Alineá el tempo antes de continuar."
    return "SIGUIENTE MOVIMIENTO", "Completá las acciones indicadas."


def _moment_short_label(moment: dict[str, Any]) -> str:
    intent, _objective = _moment_intent(moment)
    return intent.replace("PREPARÁ ", "ENTRADA ").title()


def _action_icon(action: dict[str, Any]) -> str:
    control = str(action.get("control", ""))
    instruction = str(action.get("instruction", ""))
    if control == "play":
        return "▶"
    if control in {"cue", "transport_cue"}:
        return "◉"
    if control in {"loop_active", "loop_size"}:
        return "↻"
    if control == "sync":
        return "⟳"
    if control in {"low", "mid", "high", "gain", "volume", "fx_adjust"}:
        return "↓" if instruction.startswith(("Bajá", "Cerrá")) else "↑"
    if control == "crossfader":
        return "↔"
    return "•"


def _action_state(action: dict[str, Any]) -> str:
    outcome = action.get("outcome")
    if not outcome:
        return ""
    return "done" if outcome.get("status") == "completed" else "problem"


def _musical_wait(seconds: float | int | None, bpm: float | None) -> str:
    if seconds is None:
        return ""
    seconds = max(0.0, float(seconds))
    if seconds <= 0.5:
        return "AHORA"
    approximate = f"≈ {seconds:.0f} s"
    if not bpm:
        return f"En {seconds:.0f} segundos"
    beats = max(1, round(seconds * float(bpm) / 60.0))
    if beats >= 4:
        bars = max(1, round(beats / 4))
        word = "compás" if bars == 1 else "compases"
        return f"En {bars} {word} · {approximate}"
    word = "beat" if beats == 1 else "beats"
    return f"En {beats} {word} · {approximate}"


def render_coach_context(lesson_name: str, status: dict[str, Any]) -> str:
    context = status.get("musical_context", {})
    step = status.get("current_moment_number", 0)
    total = status.get("total_moments", 0)
    bar = context.get("bar")
    beat = context.get("beat")
    bpm = context.get("bpm")
    musical = f"Compás {bar} · Beat {beat}" if bar and beat else "Sin calibrar"
    bpm_text = f"{float(bpm):.1f}" if bpm is not None else "---"
    step_text = f"{step} de {total}" if total else "---"
    phase = (
        "INICIO"
        if status.get("state") == "waiting_for_play"
        else _moment_intent(status.get("current"))[0]
        if status.get("current")
        else "---"
    )
    return (
        '<div class="coach-context">'
        f'<div class="context-cell lesson"><span>LECCIÓN</span><strong>{escape(lesson_name)}</strong></div>'
        f'<div class="context-cell"><span>PASO</span><strong>{step_text}</strong></div>'
        f'<div class="context-cell"><span>FASE</span><strong>{escape(phase)}</strong></div>'
        f'<div class="context-cell"><span>TIEMPO MUSICAL</span><strong>{escape(musical)}</strong></div>'
        f'<div class="context-cell"><span>BPM</span><strong>{bpm_text}</strong></div>'
        '<div class="context-cell"><span>MODO</span><strong>Práctica</strong></div>'
        '</div>'
    )


def render_coach_timeline(status: dict[str, Any]) -> str:
    timeline = status.get("timeline", [])
    if not timeline:
        return '<div class="coach-empty-note">La timeline aparecerá al iniciar.</div>'
    phases: list[dict[str, Any]] = []
    for moment in timeline:
        label = _moment_short_label(moment)
        if phases and phases[-1]["label"] == label:
            phases[-1]["states"].append(moment["visual_state"])
        else:
            phases.append({"label": label, "states": [moment["visual_state"]]})
    for phase in phases:
        states = phase["states"]
        if "current" in states:
            phase["visual_state"] = "current"
        elif "problem" in states:
            phase["visual_state"] = "problem"
        elif all(state == "completed" for state in states):
            phase["visual_state"] = "completed"
        else:
            phase["visual_state"] = "pending"
    if len(phases) > 6:
        current_index = next(
            (
                index
                for index, phase in enumerate(phases)
                if phase["visual_state"] == "current"
            ),
            0,
        )
        start = max(0, min(current_index - 2, len(phases) - 6))
        phases = phases[start : start + 6]
    icons = {"completed": "✓", "current": "●", "pending": "○", "problem": "!"}
    steps = "".join(
        f'<div class="timeline-step {escape(str(phase["visual_state"]))}">'
        f'<span class="timeline-icon">{icons.get(phase["visual_state"], "○")}</span>'
        f'<span class="timeline-label">{escape(str(phase["label"]))}</span></div>'
        for phase in phases
    )
    return f'<div class="coach-timeline">{steps}</div>'


def _actions_by_control(
    moment: dict[str, Any] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    actions = {}
    for action in (moment or {}).get("actions", []):
        section = str(action.get("section", ""))
        control = str(action.get("control", ""))
        actions[(section, control)] = action
        if control == "loop_size":
            actions.setdefault((section, "loop_active"), action)
    return actions


def _control_midi(deck: dict[str, Any], control: str) -> int | None:
    value = deck.get(control, {})
    if not isinstance(value, dict) or not value.get("received"):
        return None
    midi = value.get("midi")
    return int(midi) if midi is not None else None


def _boolean_state(deck: dict[str, Any], control: str) -> tuple[bool, bool]:
    return bool(deck.get(control)), bool(deck.get(f"{control}_received"))


def _control_target(action: dict[str, Any] | None) -> int | None:
    if not action or action.get("target_value") is None:
        return None
    return int(action["target_value"])


def _render_control_arrow(current: int | None, target: int | None) -> str:
    """Indicador grande y cercano al control que debe mover el alumno."""
    if current is None or target is None:
        return ""
    if target < current:
        return '<div class="control-move-arrow down"><span>↓</span><small>BAJÁ</small></div>'
    if target > current:
        return '<div class="control-move-arrow up"><span>↑</span><small>SUBÍ</small></div>'
    return '<div class="control-move-arrow ready"><span>✓</span><small>LISTO</small></div>'


def _render_coach_knob(
    deck: dict[str, Any],
    section: str,
    control: str,
    label: str,
    action: dict[str, Any] | None,
) -> str:
    current = _control_midi(deck, control)
    target = _control_target(action)
    involved = action is not None
    current_for_angle = current if current is not None else 63
    student_percentage = round(current_for_angle / 127 * 100)
    ghost = (
        f'<div class="coach-knob-ghost" style="transform:rotate({_knob_angle(target):.1f}deg)"><span></span></div>'
        if target is not None
        else ""
    )
    if current is None:
        readout = "SIN MIDI"
    elif target is None:
        readout = f"{student_percentage}%"
    else:
        target_percentage = round(target / 127 * 100)
        direction = "↓" if target < current else "↑" if target > current else "✓"
        readout = f"{student_percentage}% {direction} {target_percentage}%"
    return (
        f'<div class="coach-knob-control {"involved" if involved else ""}">'
        f'{_render_control_arrow(current, target)}'
        '<div class="coach-knob-face">'
        f'{ghost}<div class="coach-knob-student" style="transform:rotate({_knob_angle(current_for_angle):.1f}deg)"><span></span></div>'
        f'</div><div class="coach-knob-label">{escape(label)}</div>'
        f'<div class="coach-knob-readout">{escape(readout)}</div></div>'
    )


def _render_coach_fader(
    deck: dict[str, Any], action: dict[str, Any] | None
) -> str:
    current = _control_midi(deck, "volume")
    target = _control_target(action)
    current_percentage = (current if current is not None else 0) / 127 * 100
    target_line = (
        f'<div class="coach-fader-target" style="bottom:{target / 127 * 100:.1f}%"></div>'
        if target is not None
        else ""
    )
    value = "---" if current is None else f"{round(current_percentage)}%"
    return (
        f'<div class="coach-fader-wrap {"involved" if action else ""}">'
        f'{_render_control_arrow(current, target)}'
        '<div class="coach-fader"><div class="coach-fader-rail"></div>'
        f'{target_line}<div class="coach-fader-handle" style="bottom:{current_percentage:.1f}%;transform:translateY(50%)"></div>'
        f'</div><div class="coach-knob-label">VOLUME</div>'
        f'<div class="coach-knob-readout">{value}</div></div>'
    )


def _render_coach_button(
    deck: dict[str, Any],
    control: str,
    label: str,
    action: dict[str, Any] | None,
) -> str:
    active, received = _boolean_state(deck, control)
    classes = ["coach-mixer-button"]
    if active and received:
        classes.append("on")
    if action:
        classes.append("involved")
    state = "ON" if active and received else "OFF" if received else "---"
    button_guide = ""
    if action and received:
        target_active = bool(action.get("target_active"))
        button_guide = (
            '<div class="control-move-arrow ready"><span>✓</span><small>LISTO</small></div>'
            if active == target_active
            else '<div class="control-move-arrow tap"><span>●</span><small>PULSÁ</small></div>'
        )
    return (
        f'<div class="{" ".join(classes)}">{button_guide}<span class="button-led"></span>'
        f'{escape(label)}<div class="coach-knob-readout">{state}</div></div>'
    )


def _render_visual_deck(
    mixer_state: dict[str, Any],
    section: str,
    actions: dict[tuple[str, str], dict[str, Any]],
) -> str:
    deck = mixer_state.get(section, {})
    css_class = "deck-a" if section == "deck_a" else "deck-b"
    title = "DECK A" if section == "deck_a" else "DECK B"
    knobs = "".join(
        _render_coach_knob(
            deck, section, control, label, actions.get((section, control))
        )
        for control, label in (
            ("gain", "GAIN"),
            ("high", "HI"),
            ("mid", "MID"),
            ("low", "LOW"),
            ("fx_adjust", "FX"),
        )
    )
    fader = _render_coach_fader(deck, actions.get((section, "volume")))
    buttons = "".join(
        _render_coach_button(
            deck, control, label, actions.get((section, control))
        )
        for control, label in (
            ("play", "PLAY"),
            ("cue", "CUE"),
            ("sync", "SYNC"),
            ("loop_active", "LOOP"),
            ("fx_on", "FX ON"),
        )
    )
    return (
        f'<section class="visual-deck {css_class}"><div class="visual-deck-title">'
        f'<span>{title}</span><span>ALUMNO / GHOST</span></div>'
        f'<div class="visual-knobs">{knobs}</div><div class="visual-deck-lower">'
        f'{fader}<div class="coach-button-grid">{buttons}</div></div></section>'
    )


def _render_coach_crossfader(
    mixer_state: dict[str, Any], action: dict[str, Any] | None
) -> str:
    crossfader = mixer_state.get("crossfader", {})
    current = crossfader.get("midi") if crossfader.get("received") else None
    current_percentage = (int(current) if current is not None else 63) / 127 * 100
    target = _control_target(action)
    target_line = (
        f'<div class="coach-cross-target" style="left:{target / 127 * 100:.1f}%"></div>'
        if target is not None
        else ""
    )
    movement_arrow = _render_control_arrow(
        int(current) if current is not None else None, target
    )
    return (
        '<section class="visual-center"><div class="visual-center-label">CROSSFADER</div>'
        f'<div class="coach-crossfader {"involved" if action else ""}">'
        f'{movement_arrow}<div class="coach-cross-rail"></div>{target_line}'
        f'<div class="coach-cross-handle" style="left:{current_percentage:.1f}%;transform:translateX(-50%)"></div>'
        '</div><div class="coach-cross-labels"><span>A</span><span>B</span></div></section>'
    )


def render_visual_mixer(
    mixer_state: dict[str, Any] | None,
    moment: dict[str, Any] | None,
) -> str:
    state = mixer_state or {}
    actions = _actions_by_control(moment)
    return (
        '<div class="visual-mixer">'
        f'{_render_visual_deck(state, "deck_a", actions)}'
        f'{_render_coach_crossfader(state, actions.get(("mixer", "crossfader")))}'
        f'{_render_visual_deck(state, "deck_b", actions)}'
        '</div><div class="mixer-legend">'
        '<span><i class="student"></i>posición real</span>'
        '<span><i class="teacher"></i>ghost profesor</span></div>'
    )


def _action_live_detail(
    action: dict[str, Any], mixer_state: dict[str, Any] | None
) -> str:
    section = str(action.get("section", ""))
    control = str(action.get("control", ""))
    state = mixer_state or {}
    if section == "mixer" and control == "crossfader":
        value = state.get("crossfader", {})
        current = value.get("midi") if value.get("received") else None
    else:
        deck = state.get(section, {})
        if control in {"play", "transport_cue", "cue", "sync", "loop_active", "fx_on"}:
            received = bool(deck.get(f"{control}_received"))
            current_active = bool(deck.get(control)) if received else None
            target_active = bool(action.get("target_active"))
            if current_active is None:
                return "Estado actual sin recibir · tocá el control"
            return (
                f'Actual {"ON" if current_active else "OFF"} → '
                f'Objetivo {"ON" if target_active else "OFF"}'
            )
        value = deck.get(control, {})
        current = value.get("midi") if value.get("received") else None
    target = action.get("target_value")
    if current is None:
        return "Posición actual sin recibir · mové el control"
    current_percentage = round(int(current) / 127 * 100)
    if target is None:
        return f"Posición actual {current_percentage}%"
    target_percentage = round(int(target) / 127 * 100)
    direction = "BAJÁ ↓" if int(target) < int(current) else "SUBÍ ↑" if int(target) > int(current) else "LISTO ✓"
    return f"Actual {current_percentage}% → objetivo {target_percentage}% · {direction}"


def _render_focus_actions(
    actions: list[dict[str, Any]], mixer_state: dict[str, Any] | None
) -> str:
    if not actions:
        return ""
    rendered = "".join(
        f'<div class="coach-focus-action {escape(str(action.get("section", ""))).replace("_", "-")} {_action_state(action)}">'
        f'<div class="coach-focus-icon">{_action_icon(action)}</div>'
        '<div class="coach-focus-copy">'
        f'<small>{escape(section_label(str(action.get("section", ""))).upper())}</small>'
        f'<strong>{escape(str(action.get("instruction", "")))}</strong>'
        f'<em>{escape(_action_live_detail(action, mixer_state))}</em>'
        '</div></div>'
        for action in actions
    )
    return f'<div class="coach-focus-grid">{rendered}</div>'


def render_coach_now(
    moment: dict[str, Any] | None,
    state: str,
    seconds_until: float | int | None = None,
    bpm: float | None = None,
    mixer_state: dict[str, Any] | None = None,
) -> str:
    if state == "idle":
        intent, objective = "LISTO PARA EMPEZAR", "Iniciá el intento cuando estés frente a Traktor."
        actions = []
    elif state == "waiting_for_play":
        intent, objective = "SINCRONIZÁ LA GUÍA", "Este PLAY marca el inicio del reloj de la lección."
        actions = [
            {"section": "deck_a", "control": "play", "instruction": "Pulsá PLAY en Deck A"}
        ]
    elif state == "guidance_complete":
        return (
            '<section class="coach-now"><div class="coach-eyebrow">COMPLETADO</div>'
            '<h2>SECUENCIA TERMINADA</h2><p class="coach-objective">'
            'Ya recorriste todas las acciones. Detené el intento para ver el resultado.</p>'
            '<div class="feedback-item success"><span>✓</span><strong>Lección completada</strong></div></section>'
        )
    else:
        intent, objective = _moment_intent(moment)
        actions = list((moment or {}).get("actions", []))
    shown_moment = {"actions": actions}
    focus_actions = _render_focus_actions(actions, mixer_state)
    wait = _musical_wait(seconds_until, bpm)
    wait_html = f'<div class="coach-time-pill">{escape(wait)}</div>' if wait else ""
    return (
        '<section class="coach-now"><div class="coach-brief">'
        '<div class="coach-eyebrow">AHORA</div>'
        f'<h2>{escape(intent)}</h2><p class="coach-objective">{escape(objective)}</p>{wait_html}'
        f'{focus_actions}</div>'
        f'<div class="coach-stage">{render_visual_mixer(mixer_state, shown_moment)}</div>'
        '</section>'
    )


def render_coach_next(
    moment: dict[str, Any] | None,
    seconds_until: float | int | None,
    bpm: float | None,
) -> str:
    if not moment:
        return (
            '<section class="coach-side-card"><div class="coach-side-title">DESPUÉS</div>'
            '<div class="coach-empty-note">No hay otra acción pendiente.</div></section>'
        )
    intent, _objective = _moment_intent(moment)
    actions = "".join(
        f'<div class="coach-next-action"><span>{_action_icon(action)}</span>'
        f'<span>{escape(str(action["instruction"]))}</span></div>'
        for action in moment.get("actions", [])
    )
    return (
        '<section class="coach-side-card"><div class="coach-side-title">DESPUÉS</div>'
        f'<div class="coach-next-time">{escape(_musical_wait(seconds_until, bpm))}</div>'
        f'<div class="coach-next-intent">{escape(intent)}</div>{actions}</section>'
    )


def render_coach_feedback(status: dict[str, Any]) -> str:
    feedback = list(status.get("feedback", []))
    if status.get("state") == "waiting_for_play":
        feedback = [{"state": "pending", "verdict": "READY", "message": "Esperando PLAY de Deck A"}]
    elif status.get("state") == "idle":
        feedback = [{"state": "pending", "verdict": "READY", "message": "Esperando que inicies el intento"}]
    if not feedback and status.get("current"):
        pending = [
            action
            for action in status["current"].get("actions", [])
            if not action.get("outcome")
        ]
        feedback = [
            {"state": "pending", "verdict": "NOW", "message": action["instruction"]}
            for action in pending[:3]
        ]
    if not feedback:
        feedback = [{"state": "pending", "verdict": "READY", "message": "Esperando el comienzo de la práctica"}]
    icons = {"success": "✓", "warning": "⚠", "problem": "!", "pending": "○"}
    items = "".join(
        f'<div class="feedback-item {escape(str(item["state"]))}"><span>'
        f'{icons.get(item["state"], "○")}</span><span class="feedback-copy">'
        f'<strong class="feedback-verdict">{escape(str(item.get("verdict", "NOW")))}</strong>'
        f'<span class="feedback-detail">{escape(str(item["message"]))}'
        f'{f" · {abs(float(item["delta_beats"])):g} beats" if item.get("delta_beats") is not None else ""}'
        '</span></span></div>'
        for item in feedback[:4]
    )
    combo = int(status.get("combo", 0))
    combo_html = (
        f'<div class="feedback-combo">🔥 x{combo} COMBO</div>' if combo >= 2 else ""
    )
    return (
        '<section class="coach-side-card"><div class="coach-side-title">FEEDBACK</div>'
        f'<div class="feedback-list">{items}</div>{combo_html}</section>'
    )


def _rhythm_action_label(action: dict[str, Any]) -> str:
    """Etiqueta breve: el alumno mira Traktor, no un segundo mixer."""
    control = str(action.get("control", ""))
    section = str(action.get("section", ""))
    deck = {"deck_a": "A", "deck_b": "B"}.get(section, "")
    label = {
        "low": "LOW",
        "mid": "MID",
        "high": "HIGH",
        "gain": "GAIN",
        "fx_adjust": "FX",
        "volume": "FADER",
        "crossfader": "CROSSFADER",
        "loop_active": "LOOP",
        "loop_size": "LOOP",
        "fx_on": "FX ON",
        "play": "PLAY",
        "sync": "SYNC",
        "cue": "CUE",
    }.get(control, CONTROL_LABELS.get(control, control.upper()))
    instruction = str(action.get("instruction", ""))
    if control in {"low", "mid", "high", "gain", "fx_adjust", "volume"}:
        direction = "↓" if instruction.startswith(("Bajá", "Cerrá")) else "↑"
        return f"{deck} {label} {direction}".strip()
    if control == "crossfader":
        return "X-FADER → B" if "Deck B" in instruction else "X-FADER → A"
    if control == "play":
        return f"{deck} ▶".strip()
    if control == "loop_active":
        return f"{deck} ↻ {'●' if action.get('target_active') else '○'}".strip()
    if control in {"cue", "fx_on", "sync", "transport_cue"}:
        short = {"fx_on": "FX", "transport_cue": "CUE"}.get(control, label)
        return f"{deck} {short} {'●' if action.get('target_active') else '○'}".strip()
    return f"{deck} {label}".strip()


def _rhythm_action_target(action: dict[str, Any]) -> str:
    value = action.get("target_value")
    if value is None:
        return ""
    return f"Objetivo {round(int(value) / 127 * 100)}%"


def _rhythm_card_color(moment: dict[str, Any]) -> str:
    sections = {str(action.get("section", "")) for action in moment.get("actions", [])}
    if sections == {"deck_a"}:
        return "deck-a"
    if sections == {"deck_b"}:
        return "deck-b"
    return "mixer"


def _rhythm_gesture_duration(action: dict[str, Any], bpm: float) -> tuple[float, int]:
    """Duración de una tarjeta: sólo los gestos continuos ocupan tiempo."""
    seconds = max(0.0, float(action.get("duration_seconds", 0.0)))
    beats = seconds * bpm / 60.0
    # 118 px es una acción puntual. Un beat adicional agrega espacio
    # deliberadamente visible: la longitud debe comunicar velocidad de un
    # vistazo, no ser una diferencia de apenas unos píxeles.
    width = min(420, round(112 + beats * 48))
    return beats, width


def _rhythm_hold_trajectory(action: dict[str, Any], width: int) -> str:
    """Nota sostenida: la card es inicio y la cola apunta al objetivo."""
    start = int(action.get("start_value", action.get("target_value", 63)))
    target = int(action.get("target_value", start))
    start_percent = round(max(0, min(127, start)) / 127 * 100)
    target_percent = round(max(0, min(127, target)) / 127 * 100)

    def y_position(percent: int) -> int:
        # 50% se ubica en el centro; 0% cae abajo y 100% sube.
        return round(85 - percent * 0.7)

    start_y = y_position(start_percent)
    target_y = y_position(target_percent)
    return (
        f'<svg class="rhythm-hold trajectory" style="--hold-width:{width}px" '
        'viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
        '<path class="trajectory-guide" d="M0 50 H100" />'
        # El extremo derecho toca la card: es el valor con el que se empieza.
        # Hacia la izquierda avanza la cola hasta el objetivo del profesor.
        f'<path class="trajectory-path" d="M0 {target_y} L100 {start_y}" />'
        f'<circle class="trajectory-point" cx="0" cy="{target_y}" r="4" />'
        f'<circle class="trajectory-point" cx="100" cy="{start_y}" r="4" />'
        '</svg>'
    )


def _rhythm_phase_index(status: dict[str, Any]) -> int:
    if status.get("state") in {"idle", "waiting_for_play"}:
        return 0
    intent, _ = _moment_intent(status.get("current"))
    if intent == "BASS SWAP":
        return 4
    if intent.startswith("PREPARÁ") or intent.startswith("LOOP"):
        return 1
    if "EQ" in intent or intent == "EFECTO":
        return 2
    if intent == "MEZCLA":
        return 3
    if status.get("state") == "guidance_complete":
        return 5
    total = max(1, int(status.get("total_moments", 1)))
    progress = int(status.get("current_moment_number", 1)) / total
    return min(5, max(1, round(progress * 4)))


def render_rhythm_header(lesson_name: str, status: dict[str, Any]) -> str:
    context = status.get("musical_context", {})
    bpm = context.get("bpm")
    phase_names = ("PREPARACIÓN", "ENTRADA B", "EQ PREP", "BLEND", "BASS SWAP", "SALIDA")
    phase = phase_names[_rhythm_phase_index(status)]
    bpm_text = f"{float(bpm):.1f}" if bpm is not None else "---"
    return (
        '<header class="rhythm-header">'
        f'<div class="rhythm-meta lesson"><span>LECCIÓN</span><strong>{escape(lesson_name)}</strong></div>'
        f'<div class="rhythm-meta phase"><span>FASE</span><strong>{phase}</strong></div>'
        f'<div class="rhythm-meta"><span>BPM</span><strong>{bpm_text}</strong></div>'
        '<div class="rhythm-meta"><span>MODO</span><strong>PRÁCTICA</strong></div>'
        '<span class="rhythm-exit">TRAKTOR · MÚSICA / DJ COACH · COREOGRAFÍA</span>'
        '</header>'
    )


def render_rhythm_phases(status: dict[str, Any]) -> str:
    labels = ("Preparación", "Entrada B", "EQ Prep", "Blend", "Bass Swap", "Salida")
    current = _rhythm_phase_index(status)
    phases = "".join(
        f'<div class="rhythm-phase {"completed" if index < current else "current" if index == current else "pending"}">'
        f'<span class="rhythm-phase-dot">{"✓" if index < current else index + 1}</span>'
        f'<span>{label}</span></div>'
        for index, label in enumerate(labels)
    )
    return f'<nav class="rhythm-phases">{phases}</nav>'


def render_rhythm_now_focus(status: dict[str, Any]) -> str:
    """Zona fija: la orden se lee quieta al llegar a su ventana musical."""
    moment = status.get("current")
    if not moment or status.get("state") != "guiding":
        return ""
    bpm = float(status.get("musical_context", {}).get("bpm") or 128.0)
    seconds = status.get("seconds_until_current")
    beats = float(seconds or 0.0) * bpm / 60.0
    if beats > 4.0:
        return ""
    now = beats <= 1.0
    intent, _ = _moment_intent(moment)
    actions = list(moment.get("actions", []))
    tokens = " ".join(_rhythm_action_label(action) for action in actions)
    target = _rhythm_action_target(actions[0]) if len(actions) == 1 else ""
    instruction = intent if intent == "BASS SWAP" else tokens
    return (
        f'<section class="rhythm-now-focus {"now" if now else "prepare"}">'
        f'<span>{"AHORA" if now else "PREPARATE"}</span>'
        f'<strong>{escape(instruction)}</strong>'
        f'<em>{escape(target or _rhythm_countdown(seconds, bpm))}</em></section>'
    )


def render_rhythm_lane(status: dict[str, Any]) -> str:
    state = status.get("state", "idle")
    if state == "idle":
        return '<section class="rhythm-lane"><div class="rhythm-wait">INICIÁ EL INTENTO CUANDO ESTÉS LISTO</div></section>'
    if state == "waiting_for_play":
        return '<section class="rhythm-lane"><div class="rhythm-wait">PULSÁ PLAY EN DECK A PARA INICIAR EL RELOJ</div></section>'
    bpm = float(status.get("musical_context", {}).get("bpm") or 128.0)
    student_seconds = float(status.get("student_seconds", 0.0))
    cards = []
    for moment in status.get("timeline", []):
        delta_beats = (float(moment["reference_seconds"]) - student_seconds) * bpm / 60.0
        visual_state = str(moment.get("visual_state", "pending"))
        if delta_beats < -4.0 and visual_state not in {"current", "problem"}:
            continue
        if delta_beats > 10.0:
            continue
        left = max(7.0, min(95.0, 62.0 - delta_beats * 5.5))
        stage = "now" if abs(delta_beats) <= 1.0 else "prepare" if delta_beats <= 4.0 else "far"
        # Cada fila representa una mano. No comprimimos dos movimientos
        # distintos en una tarjeta porque el alumno debe verlos como dos
        # gestos físicos independientes.
        for lane, action in enumerate(moment.get("actions", [])[:2]):
            # Dos acciones simultáneas se distribuyen en filas separadas;
            # las tarjetas grandes deben conservar aire entre sí.
            top = 30 + lane * 124
            action_color = _rhythm_card_color({"actions": [action]})
            duration_beats, hold_width = _rhythm_gesture_duration(action, bpm)
            duration_html = ""
            duration_class = ""
            if duration_beats >= 0.05:
                duration_class = " duration"
                duration_html = (
                    f'{_rhythm_hold_trajectory(action, hold_width)}'
                    '<span class="rhythm-card-duration"><i></i>'
                    f'<em>{duration_beats:.1f} BEATS · '
                    f'{round(int(action.get("start_value", action.get("target_value", 63))) / 127 * 100)}% '
                    f'→ {round(int(action.get("target_value", 63)) / 127 * 100)}%</em></span>'
                )
            cards.append(
                f'<article class="rhythm-card{duration_class} {action_color} status-{escape(visual_state)} {stage}" '
                f'style="left:{left:.1f}%;top:{top}px">'
                '<span class="rhythm-card-start"><i></i><em>INICIO</em></span>'
                f'<div class="rhythm-card-actions"><span class="rhythm-action">'
                f'{escape(_rhythm_action_label(action))}</span></div>{duration_html}</article>'
            )
    scale = '<span>8 BEATS</span><span>6</span><span>4</span><span>2</span><strong>1</strong>'
    return (
        '<section class="rhythm-lane"><div class="rhythm-now"><i></i></div>'
        f'{"".join(cards)}<div class="rhythm-scale">{scale}</div></section>'
    )


def _rhythm_countdown(seconds: float | int | None, bpm: float | None) -> str:
    if seconds is None:
        return "---"
    beats = max(0, round(max(0.0, float(seconds)) * float(bpm or 128.0) / 60.0))
    return "AHORA" if beats == 0 else f"En {beats} beats"


def render_rhythm_next(status: dict[str, Any]) -> str:
    moment = status.get("next")
    bpm = status.get("musical_context", {}).get("bpm")
    if not moment:
        return '<aside class="rhythm-next"><small>PRÓXIMO</small><h3>--- </h3></aside>'
    intent, _ = _moment_intent(moment)
    actions_list = list(moment.get("actions", []))
    if intent == "BASS SWAP":
        action_text = " · ".join(
            _rhythm_action_label(action) for action in actions_list
        )
        label = "BASS SWAP"
    else:
        action_text = _rhythm_action_label(actions_list[0]) if actions_list else "---"
        label = action_text
    return (
        '<aside class="rhythm-next"><small>PRÓXIMO</small>'
        f'<div class="rhythm-next-time">{escape(_rhythm_countdown(status.get("seconds_until_next"), bpm))}</div>'
        f'<h3>{escape(label)}</h3><span class="rhythm-next-action">{escape(action_text)}</span></aside>'
    )


def _rhythm_seconds_until(status: dict[str, Any], moment: dict[str, Any]) -> float:
    return float(moment.get("reference_seconds", 0.0)) - float(
        status.get("student_seconds", 0.0)
    )


def _rhythm_live_midi(action: dict[str, Any], status: dict[str, Any]) -> int | None:
    """Valor recibido para explicar un gesto sin duplicar el mixer visual."""
    mixer = status.get("mixer_state", {})
    section = str(action.get("section", ""))
    control = str(action.get("control", ""))
    if control == "crossfader":
        value = mixer.get("crossfader", {})
    else:
        value = mixer.get(section, {}).get(control, {})
    if not isinstance(value, dict) or not value.get("received"):
        return None
    midi = value.get("midi")
    return int(midi) if midi is not None else None


def _rhythm_action_guidance(action: dict[str, Any], status: dict[str, Any]) -> str:
    """Objetivo breve y físico: perilla/fader no se explica como botón."""
    if action.get("target_active") is not None:
        verb = "ACTIVÁ" if action.get("target_active") else "DESACTIVÁ"
        return f"BOTÓN · {verb}"
    target = action.get("target_value")
    if target is None:
        return "ACCIÓN PUNTUAL"
    target_midi = int(target)
    target_percent = round(target_midi / 127 * 100)
    current = _rhythm_live_midi(action, status)
    if current is None:
        return f"OBJETIVO {target_percent}%"
    current_percent = round(current / 127 * 100)
    if target_midi > current + 2:
        direction = "SUBÍ ↑"
    elif target_midi < current - 2:
        direction = "BAJÁ ↓"
    else:
        direction = "MANTENÉ ✓"
    return f"{current_percent}% → {target_percent}% · {direction}"


def _rhythm_prepare_progress(seconds: float, bpm: float | int | None) -> tuple[int, str]:
    """Los últimos 16 beats se llenan; antes, la consigna ya es visible."""
    beats = max(0.0, seconds * float(bpm or 128.0) / 60.0)
    progress = round(max(0.0, min(1.0, (16.0 - beats) / 16.0)) * 100)
    return progress, _rhythm_countdown(seconds, bpm)


def _render_rhythm_level(
    label: str,
    moment: dict[str, Any] | None,
    status: dict[str, Any],
    style: str,
) -> str:
    if moment is None:
        return (
            f'<section class="rhythm-level {style} empty"><small>{label}</small>'
            '<strong>--- </strong><em>Sin otra acción</em></section>'
        )
    actions = list(moment.get("actions", []))
    intent, _ = _moment_intent(moment)
    compact = " · ".join(_rhythm_action_label(action) for action in actions)
    action_detail = " + ".join(
        _rhythm_action_guidance(action, status) for action in actions
    )
    seconds_until = _rhythm_seconds_until(status, moment)
    countdown_html = ""
    if style == "now":
        title = intent if intent == "BASS SWAP" else " + ".join(
            str(action.get("instruction", compact)) for action in actions
        )
        detail = action_detail
    else:
        title = compact or intent
        countdown = _rhythm_countdown(
            seconds_until, status.get("musical_context", {}).get("bpm")
        )
        detail = f"{countdown} · {action_detail}"
        if style == "prepare":
            progress, progress_label = _rhythm_prepare_progress(
                seconds_until, status.get("musical_context", {}).get("bpm")
            )
            countdown_html = (
                '<div class="rhythm-prepare-progress" '
                f'aria-label="{escape(progress_label)}"><i style="width:{progress}%"></i>'
                f'<span>{escape(progress_label)}</span></div>'
            )
    color = _rhythm_card_color(moment)
    return (
        f'<section class="rhythm-level {style} {color}"><small>{label}</small>'
        f'<strong>{escape(title)}</strong><em>{escape(detail or "Objetivo listo")}</em>'
        f'{countdown_html}</section>'
    )


def render_rhythm_action_panels(status: dict[str, Any]) -> str:
    """Consignas fijas: el reloj manda; los resultados sólo califican."""
    state = status.get("state")
    if state in {"idle", "waiting_for_play"}:
        waiting = "PULSÁ PLAY EN DECK A" if state == "waiting_for_play" else "INICIÁ EL INTENTO"
        return (
            '<section class="rhythm-action-panels waiting"><div>'
            f'<small>COREOGRAFÍA</small><strong>{waiting}</strong>'
            '<em>El reloj musical comenzará con la música.</em></div></section>'
        )
    current = status.get("current")
    current_due = current is not None and _rhythm_seconds_until(status, current) <= 1.0
    now = current if current_due else None
    prepare = status.get("next") if current_due else current
    after = status.get("after_next") if current_due else status.get("next")
    missed = list(status.get("missed", []))[-3:]
    missed_html = "".join(
        '<li><span>!</span>'
        f'{escape(_rhythm_action_label(action))}<em>MISSED</em></li>'
        for action in reversed(missed)
    ) or '<li class="clear">Sin pendientes</li>'
    return (
        '<section class="rhythm-action-panels">'
        f'{_render_rhythm_level("AHORA", now, status, "now")}'
        f'{_render_rhythm_level("PREPARATE", prepare, status, "prepare")}'
        f'{_render_rhythm_level("DESPUÉS", after, status, "after")}'
        '<aside class="rhythm-missed"><small>PENDIENTES / MISSED</small>'
        f'<ul>{missed_html}</ul></aside></section>'
    )


def render_rhythm_feedback(status: dict[str, Any]) -> str:
    feedback = list(status.get("feedback", []))
    if status.get("state") == "waiting_for_play":
        item = {"state": "pending", "verdict": "READY", "message": "Esperando PLAY de Deck A"}
    elif status.get("state") == "idle":
        item = {"state": "pending", "verdict": "READY", "message": "Listo para empezar"}
    elif feedback:
        item = feedback[0]
    else:
        item = {"state": "pending", "verdict": "PREPARATE", "message": "La acción se acerca a AHORA"}
    delta = item.get("delta_beats")
    delta_text = ""
    if delta is not None:
        sign = "+" if float(delta) > 0 else ""
        delta_text = f' · {sign}{float(delta):g} beat'
    combo = int(status.get("combo", 0))
    combo_html = f'<span class="rhythm-combo">x{combo} COMBO</span>' if combo >= 2 else ""
    return (
        '<section class="rhythm-feedback">'
        f'<strong class="rhythm-verdict {escape(str(item.get("state", "pending")))}">{escape(str(item.get("verdict", "READY")))}</strong>'
        f'<span class="rhythm-feedback-detail">{escape(str(item.get("message", "")))}{delta_text}</span>{combo_html}</section>'
    )


def _midi_percentage(value: int | float | bool | None) -> float:
    if value is None or isinstance(value, bool):
        return 50.0
    return max(0.0, min(100.0, float(value) / 127.0 * 100.0))


def _knob_angle(value: int | float | bool | None) -> float:
    return -135.0 + _midi_percentage(value) / 100.0 * 270.0


def _render_knob(item: Any, label: str) -> str:
    state_class = "matched" if item.matched else "mismatch"
    return (
        f'<div class="hw-control {state_class}">'
        '<div class="knob-face">'
        f'<div class="knob-target" style="transform:rotate({_knob_angle(item.target):.1f}deg)"><span></span></div>'
        f'<div class="knob-pointer" style="transform:rotate({_knob_angle(item.current):.1f}deg)"><span></span></div>'
        '</div>'
        f'<div class="hw-label">{escape(label)}</div>'
        f'<div class="hw-values">actual {escape(item.current_display)}<br>objetivo {escape(item.target_display)}</div>'
        '</div>'
    )


def _render_vertical_fader(item: Any) -> str:
    current = _midi_percentage(item.current)
    target = _midi_percentage(item.target)
    return (
        '<div class="hw-control">'
        '<div class="vertical-fader">'
        '<div class="fader-rail"></div>'
        f'<div class="target-line" style="bottom:{target:.1f}%"></div>'
        f'<div class="fader-handle" style="bottom:{current:.1f}%;transform:translateY(50%)"></div>'
        '</div><div class="fader-name">VOLUME</div>'
        f'<div class="hw-values">actual {escape(item.current_display)}<br>objetivo {escape(item.target_display)}</div>'
        '</div>'
    )


def _render_state_button(item: Any, label: str) -> str:
    on_class = "on" if bool(item.current) else "off"
    mismatch = "" if item.matched else " mismatch"
    return (
        f'<div class="hw-button {on_class}{mismatch}"><span class="led"></span>'
        f'{escape(label)}<span class="target-state">objetivo '
        f'{escape(item.target_display)}</span></div>'
    )


def _render_horizontal_control(item: Any, label: str, css_class: str) -> str:
    current = _midi_percentage(item.current)
    target = _midi_percentage(item.target)
    return (
        f'<div class="hw-label">{escape(label)}</div>'
        f'<div class="{css_class}"><div class="horizontal-rail"></div>'
        f'<div class="horizontal-target" style="left:{target:.1f}%"></div>'
        f'<div class="horizontal-handle" style="left:{current:.1f}%;transform:translateX(-50%)"></div>'
        '</div>'
        f'<div class="hw-values">actual {escape(item.current_display)} · objetivo {escape(item.target_display)}</div>'
    )


def render_mixer_calibration(comparison: Any) -> str:
    items = {
        (item.section, item.control): item for item in comparison.items
    }

    def deck(section: str, title: str, css_class: str) -> str:
        knobs = "".join(
            _render_knob(items[(section, control)], label)
            for control, label in (
                ("gain", "GAIN"),
                ("high", "HIGH"),
                ("mid", "MID"),
                ("low", "LOW"),
                ("fx_adjust", "FILTER / FX"),
            )
        )
        buttons = "".join(
            _render_state_button(items[(section, control)], label)
            for control, label in (
                ("fx_on", "FX ON"),
                ("cue", "CUE"),
                ("play", "PLAY"),
                ("loop_active", "LOOP"),
                ("sync", "SYNC"),
            )
        )
        loop_size = items.get((section, "loop_size"))
        if loop_size is not None:
            mismatch = "" if loop_size.matched else " mismatch"
            buttons += (
                f'<div class="hw-button{mismatch}"><span class="led"></span>'
                f'LOOP SIZE<span class="target-state">actual '
                f'{escape(loop_size.current_display)}<br>objetivo '
                f'{escape(loop_size.target_display)}</span></div>'
            )
        return (
            f'<section class="hardware-deck {css_class}">'
            f'<div class="hardware-title">{escape(title)}</div>'
            f'<div class="knob-bank">{knobs}</div>'
            '<div class="deck-lower">'
            f'{_render_vertical_fader(items[(section, "volume")])}'
            f'<div class="button-bank">{buttons}</div></div>'
            '<div class="center-block">'
            f'{_render_horizontal_control(items[(section, "track_progress")], "POSICIÓN DEL TRACK", "track-slider")}'
            '</div></section>'
        )

    clock = items[("mixer", "master_clock")]
    bpm = items[("mixer", "master_bpm")]
    center = (
        '<section class="hardware-center">'
        '<div class="hardware-title">MIXER / CLOCK</div>'
        f'{_render_state_button(clock, "MASTER CLOCK")}'
        '<div class="clock-display">'
        f'<div class="clock-bpm">{escape(bpm.current_display)}</div>'
        f'<div class="clock-target">objetivo {escape(bpm.target_display)}</div>'
        '</div><div class="center-block">'
        f'{_render_horizontal_control(items[("mixer", "crossfader")], "CROSSFADER", "crossfader-visual")}'
        '</div></section>'
    )
    mismatches = [item for item in comparison.items if not item.matched]
    instructions = "".join(
        f'<div class="hardware-instruction">{escape(item.instruction)}</div>'
        for item in mismatches[:6]
    )
    if len(mismatches) > 6:
        instructions += (
            f'<div class="hardware-instruction">Y {len(mismatches) - 6} ajustes más…</div>'
        )
    return (
        '<div class="hardware-legend">'
        '<span><i class="legend-current"></i>Posición actual</span>'
        '<span><i class="legend-target"></i>Objetivo del profesor</span>'
        '</div>'
        f'<div class="hardware-instructions">{instructions}</div>'
        '<div class="hardware-mixer">'
        f'{deck("deck_a", "DECK A", "deck-a")}{center}'
        f'{deck("deck_b", "DECK B", "deck-b")}</div>'
    )


def product_shell(title: str, subtitle: str) -> None:
    ui.add_css(PRODUCT_CSS)
    with ui.element("header").classes("product-header"):
        ui.label("DJ COACH · LECCIONES GRABADAS").classes("product-kicker")
        ui.html(f"<h1>{title}</h1><p>{subtitle}</p>", sanitize=True)


def create_lesson_plan_rehearsal(
    runtime: Any, lesson_steps: list[dict[str, Any]]
) -> Callable[[], None]:
    """Crea el ensayo MIDI secuencial y devuelve la acciÃ³n para abrirlo."""
    lesson_moments = build_guidance_moments(lesson_steps)
    state: dict[str, Any] = {
        "checkpoint": None,
        "processed": 0,
        "completed": set(),
        "listening": False,
    }

    def sync_marks() -> None:
        completed_ids = sorted(state["completed"])
        current_index = next(
            (
                index
                for index, moment in enumerate(lesson_moments)
                if not all(
                    str(action.get("id", "")) in state["completed"]
                    for action in moment["actions"]
                )
            ),
            len(lesson_moments),
        )
        completed_json = json.dumps(completed_ids)
        ui.run_javascript(
            f"""(() => {{
                const dialog = document.querySelector('.lesson-plan-dialog');
                if (!dialog) return;
                const completed = new Set({completed_json});
                const currentIndex = {current_index};
                dialog.querySelectorAll('.lesson-plan-moment').forEach(moment => {{
                    const index = Number(moment.dataset.momentIndex);
                    moment.classList.toggle('completed', index < currentIndex);
                    moment.classList.toggle('current', index === currentIndex);
                    moment.classList.toggle('locked', index > currentIndex);
                }});
                dialog.querySelectorAll('.lesson-plan-row').forEach(row => {{
                    const done = completed.has(row.dataset.stepId);
                    const moment = row.closest('.lesson-plan-moment');
                    const current = Number(moment.dataset.momentIndex) === currentIndex;
                    row.classList.toggle('completed', done);
                    row.classList.toggle('current', !done && current);
                    row.classList.toggle('locked', !done && !current);
                    const order = row.querySelector('.lesson-plan-order');
                    if (order) order.textContent = done ? 'âœ“' : row.dataset.order;
                }});
                const count = dialog.querySelector('.lesson-plan-count');
                if (count) count.textContent = `${{completed.size}} / {len(lesson_steps)}`;
            }})();"""
        )

    def refresh() -> None:
        if not state["listening"] or state["checkpoint"] is None:
            return
        capture = runtime.peek_take_capture(state["checkpoint"])
        events = capture["events"]
        new_events = events[state["processed"] :]
        changed = False
        for event in new_events:
            current_moment = next(
                (
                    moment
                    for moment in lesson_moments
                    if not all(
                        str(action.get("id", "")) in state["completed"]
                        for action in moment["actions"]
                    )
                ),
                None,
            )
            if current_moment is None:
                break
            matched = next(
                (
                    step
                    for step in current_moment["actions"]
                    if str(step.get("id", "")) not in state["completed"]
                    and event_matches_step(event, step)
                ),
                None,
            )
            if matched is not None:
                state["completed"].add(str(matched.get("id", "")))
                changed = True
        state["processed"] = len(events)
        if changed:
            sync_marks()

    def stop_listener() -> None:
        state["listening"] = False
        state["checkpoint"] = None

    def close() -> None:
        stop_listener()
        dialog.close()

    def reset() -> None:
        state["completed"].clear()
        state["checkpoint"] = runtime.begin_take_capture()
        state["processed"] = 0
        view.set_content(render_lesson_plan(lesson_steps))
        ui.run_javascript(
            "requestAnimationFrame(()=>{const list=document.querySelector("
            "'.lesson-plan-dialog .lesson-plan-list');if(list)list.scrollTop=0;});"
        )

    def open_dialog() -> None:
        state["checkpoint"] = runtime.begin_take_capture()
        state["processed"] = 0
        state["listening"] = True
        view.set_content(render_lesson_plan(lesson_steps, state["completed"]))
        dialog.open()

    with ui.dialog() as dialog:
        with ui.card().classes("lesson-plan-dialog"):
            ui.button("âœ•", on_click=close).props(
                "flat round dense aria-label=Cerrar"
            ).classes("lesson-plan-close")
            view = ui.html(
                render_lesson_plan(lesson_steps), sanitize=False
            ).classes("w-full")
            with ui.element("div").classes("lesson-plan-footer"):
                ui.label("â— ESCUCHANDO MIDI Â· SIN LÃMITE DE TIEMPO").classes(
                    "lesson-plan-live"
                )
                with ui.element("div").classes("lesson-plan-footer-actions"):
                    ui.button("REINICIAR MARCAS", on_click=reset).props(
                        "flat color=blue"
                    )
                    ui.button("CERRAR", on_click=close).props("flat color=pink")
    dialog.on("hide", lambda _event: stop_listener())
    ui.timer(0.1, refresh)
    return open_dialog


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
                            if event.get("loop_size_label"):
                                detail += f' · {event["loop_size_label"]}'
                        elif event_type == "selector_change":
                            target = (
                                f'{section_label(event["section"])} · '
                                "TAMAÑO DE LOOP"
                            )
                            detail = str(event["label"])
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
        with ui.column().classes("product-page prepare-product-page"):
            try:
                lesson = repository.get(lesson_id)
                if lesson.status != "ready_for_practice" or not lesson.reference_take_id:
                    raise FileNotFoundError
                reference_take = take_repository.get(lesson.reference_take_id)
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
            with ui.element("section").classes("lesson-summary prepare-shell"):
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
                with ui.element("div").classes("readiness-list"):
                    midi_line = ui.label().classes("readiness-line")
                    deck_a_line = ui.label().classes("readiness-line")
                    deck_b_line = ui.label().classes("readiness-line")
                    names_line = ui.label().classes("readiness-line")
                ui.html("<h2>Igualá el estado inicial del profesor</h2>").classes(
                    "prepare-title"
                )
                calibration_summary = ui.label().classes("calibration-summary")
                reference_comparison = compare_initial_state(
                    reference_take.initial_state,
                    reference_take.initial_state,
                )
                calibration_dashboard = ui.html(
                    render_mixer_calibration(reference_comparison),
                    sanitize=False,
                ).classes("w-full prepare-calibration-view")
                lesson_steps = build_guidance_steps(reference_take.features)
                open_lesson_plan = create_lesson_plan_rehearsal(
                    runtime, lesson_steps
                )
                ui.label(
                    "Pod\u00e9s ensayar primero todo el plan. Al terminar, volv\u00e9 a "
                    "igualar este mixer con el estado inicial del profesor."
                ).classes("coach-empty-note prepare-note")
                ui.button(
                    f"ENSAYAR PLAN \u00b7 {len(lesson_steps)} ACCIONES",
                    on_click=open_lesson_plan,
                ).props("outline color=blue").classes("prepare-plan-button")
                continue_button = ui.button(
                    "COMENZAR PRÁCTICA GUIADA",
                    on_click=lambda: ui.navigate.to(
                        f"/practice/{lesson.id}/guided"
                    ),
                ).props("unelevated color=pink").classes("prepare-start-button")

                def refresh_student_preparation() -> None:
                    snapshot = runtime.snapshot()
                    status = evaluate_preparation(
                        snapshot, bool(confirm_a.value), bool(confirm_b.value)
                    )
                    calibration = compare_initial_state(
                        reference_take.initial_state, snapshot
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
                    calibration_dashboard.set_content(
                        render_mixer_calibration(calibration)
                    )
                    calibration_summary.set_text(
                        "✓ Mixer listo para comenzar"
                        if calibration.ready
                        else (
                            f"Faltan ajustar {calibration.mismatch_count} "
                            "controles o estados"
                        )
                    )
                    continue_button.set_enabled(
                        status.ready and calibration.ready
                    )

                confirm_a.on_value_change(
                    lambda _event: refresh_student_preparation()
                )
                confirm_b.on_value_change(
                    lambda _event: refresh_student_preparation()
                )
                refresh_student_preparation()
                ui.timer(0.5, refresh_student_preparation)

    @ui.page("/practice/{lesson_id}/guided")
    def guided_practice_page(lesson_id: str) -> None:
        ui.add_css(PRODUCT_CSS)
        with ui.column().classes("product-page guided-product-page"):
            try:
                lesson = repository.get(lesson_id)
                if lesson.status != "ready_for_practice":
                    raise FileNotFoundError
                reference_take = take_repository.get(str(lesson.reference_take_id))
                lesson_steps = build_guidance_steps(reference_take.features)
                lesson_moments = build_guidance_moments(lesson_steps)
            except FileNotFoundError:
                product_shell("Práctica no disponible", "La lección no está aprobada.")
                return
            with ui.element("div").classes("guided-topnav"):
                ui.button(
                    "← VOLVER A PREPARAR",
                    on_click=lambda: ui.navigate.to(
                        f"/practice/{lesson.id}/prepare"
                    ),
                ).props("flat dense")
                ui.label("DJ COACH · PRÁCTICA").classes("guided-brand")

            plan_state: dict[str, Any] = {
                "checkpoint": None,
                "processed": 0,
                "completed": set(),
                "listening": False,
            }

            def sync_lesson_plan_marks() -> None:
                completed_ids = sorted(plan_state["completed"])
                current_index = next(
                    (
                        index
                        for index, moment in enumerate(lesson_moments)
                        if not all(
                            str(action.get("id", ""))
                            in plan_state["completed"]
                            for action in moment["actions"]
                        )
                    ),
                    len(lesson_moments),
                )
                completed_json = json.dumps(completed_ids)
                ui.run_javascript(
                    f"""(() => {{
                        const dialog = document.querySelector('.lesson-plan-dialog');
                        if (!dialog) return;
                        const completed = new Set({completed_json});
                        const currentIndex = {current_index};
                        dialog.querySelectorAll('.lesson-plan-moment').forEach(moment => {{
                            const index = Number(moment.dataset.momentIndex);
                            moment.classList.toggle('completed', index < currentIndex);
                            moment.classList.toggle('current', index === currentIndex);
                            moment.classList.toggle('locked', index > currentIndex);
                        }});
                        dialog.querySelectorAll('.lesson-plan-row').forEach(row => {{
                            const done = completed.has(row.dataset.stepId);
                            const moment = row.closest('.lesson-plan-moment');
                            const current = Number(moment.dataset.momentIndex) === currentIndex;
                            row.classList.toggle('completed', done);
                            row.classList.toggle('current', !done && current);
                            row.classList.toggle('locked', !done && !current);
                            const order = row.querySelector('.lesson-plan-order');
                            if (order) order.textContent = done ? '✓' : row.dataset.order;
                        }});
                        const count = dialog.querySelector('.lesson-plan-count');
                        if (count) count.textContent = `${{completed.size}} / {len(lesson_steps)}`;
                    }})();"""
                )

            def refresh_lesson_plan() -> None:
                if not plan_state["listening"] or plan_state["checkpoint"] is None:
                    return
                capture = runtime.peek_take_capture(plan_state["checkpoint"])
                events = capture["events"]
                new_events = events[plan_state["processed"] :]
                changed = False
                for event in new_events:
                    current_moment = next(
                        (
                            moment
                            for moment in lesson_moments
                            if not all(
                                str(action.get("id", ""))
                                in plan_state["completed"]
                                for action in moment["actions"]
                            )
                        ),
                        None,
                    )
                    if current_moment is None:
                        break
                    matched = next(
                        (
                            step
                            for step in current_moment["actions"]
                            if str(step.get("id", ""))
                            not in plan_state["completed"]
                            and event_matches_step(event, step)
                        ),
                        None,
                    )
                    if matched is not None:
                        plan_state["completed"].add(
                            str(matched.get("id", ""))
                        )
                        changed = True
                plan_state["processed"] = len(events)
                if changed:
                    sync_lesson_plan_marks()

            def open_lesson_plan() -> None:
                plan_state["checkpoint"] = runtime.begin_take_capture()
                plan_state["processed"] = 0
                plan_state["listening"] = True
                lesson_plan_view.set_content(
                    render_lesson_plan(lesson_steps, plan_state["completed"])
                )
                lesson_plan_dialog.open()

            def close_lesson_plan() -> None:
                plan_state["listening"] = False
                plan_state["checkpoint"] = None
                lesson_plan_dialog.close()

            def stop_lesson_plan_listener() -> None:
                plan_state["listening"] = False
                plan_state["checkpoint"] = None

            def reset_lesson_plan() -> None:
                plan_state["completed"].clear()
                plan_state["checkpoint"] = runtime.begin_take_capture()
                plan_state["processed"] = 0
                lesson_plan_view.set_content(render_lesson_plan(lesson_steps))
                ui.run_javascript(
                    "requestAnimationFrame(()=>{const list=document.querySelector("
                    "'.lesson-plan-dialog .lesson-plan-list');if(list)list.scrollTop=0;});"
                )

            with ui.dialog() as lesson_plan_dialog:
                with ui.card().classes("lesson-plan-dialog"):
                    ui.button("✕", on_click=close_lesson_plan).props(
                        "flat round dense aria-label=Cerrar"
                    ).classes("lesson-plan-close")
                    lesson_plan_view = ui.html(
                        render_lesson_plan(lesson_steps), sanitize=False
                    ).classes("w-full")
                    with ui.element("div").classes("lesson-plan-footer"):
                        ui.label("● ESCUCHANDO MIDI · SIN LÍMITE DE TIEMPO").classes(
                            "lesson-plan-live"
                        )
                        with ui.element("div").classes(
                            "lesson-plan-footer-actions"
                        ):
                            ui.button(
                                "REINICIAR MARCAS", on_click=reset_lesson_plan
                            ).props("flat color=blue")
                            ui.button(
                                "CERRAR", on_click=close_lesson_plan
                            ).props("flat color=pink")
            lesson_plan_dialog.on("hide", lambda _event: stop_lesson_plan_listener())

            idle_status = {"state": "idle"}
            with ui.element("section").classes("lesson-summary guided-shell rhythm-shell"):
                context_view = ui.html(
                    render_rhythm_header(lesson.name, idle_status), sanitize=False
                ).classes("w-full")
                timeline_view = ui.html(
                    render_rhythm_phases(idle_status), sanitize=False
                ).classes("w-full")
                with ui.element("div").classes("rhythm-stage"):
                    now_view = ui.html(
                        render_rhythm_lane(idle_status), sanitize=False
                    ).classes("w-full")
                    next_view = ui.html(
                        render_rhythm_action_panels(idle_status), sanitize=False
                    ).classes("w-full")
                feedback_view = ui.html(
                    render_rhythm_feedback(idle_status), sanitize=False
                ).classes("w-full")
                with ui.element("div").classes("rhythm-controls"):
                    practice_progress = ui.label(
                        "Prepará Traktor y comenzá cuando estés listo."
                    ).classes("practice-progress")
                    with ui.element("div").classes("guided-actions"):
                        start_attempt_button = ui.button("INICIAR INTENTO").props(
                            "unelevated color=pink"
                        )
                        stop_attempt_button = ui.button(
                            "DETENER Y VER RESULTADO"
                        ).props("unelevated color=positive")

                def start_attempt() -> None:
                    if plan_state["listening"]:
                        close_lesson_plan()
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
                    context_view.set_content(
                        render_rhythm_header(lesson.name, status)
                    )
                    timeline_view.set_content(render_rhythm_phases(status))
                    now_view.set_content(render_rhythm_lane(status))
                    next_view.set_content(render_rhythm_action_panels(status))
                    feedback_view.set_content(render_rhythm_feedback(status))
                    if state == "idle":
                        practice_progress.set_text(
                            "Prepará Traktor y comenzá cuando estés listo."
                        )
                        return
                    practice_progress.set_text(
                        f'{status["completed_count"]} correctas · '
                        f'{status["missed_count"]} con problema · '
                        f'{status["total_steps"]} acciones'
                    )

                refresh_guidance()
                # 10 FPS mantiene el feedback visual cercano al movimiento MIDI
                # sin obligar al navegador a redibujar en cada mensaje recibido.
                ui.timer(0.1, refresh_guidance)
                ui.timer(0.1, refresh_lesson_plan)

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
            evaluation = features.get("evaluation") or evaluate_guided_attempt(
                features.get("steps", []),
                features.get("outcomes", []),
                attempt.final_state,
            )
            product_shell(
                "Resultado del intento",
                f"Práctica guiada de {lesson.name}",
            )
            with ui.element("section").classes("result-overview"):
                with ui.element("div").classes("result-primary-score"):
                    ui.label(f'{evaluation.get("quality_score", 0)}%').classes("result-score")
                    ui.label("CALIDAD DE EJECUCIÓN")
                with ui.element("div").classes("result-metrics"):
                    ui.html(
                        f'<div><span>ACCIONES</span><strong>{evaluation.get("completed_count", 0)} / {len(features.get("steps", []))}</strong></div>'
                        f'<div><span>MISSED</span><strong>{evaluation.get("missed_count", 0)}</strong></div>'
                        f'<div><span>TIMING</span><strong>{evaluation.get("timing_issue_count", 0)} ajustes</strong></div>',
                        sanitize=False,
                    )
            with ui.element("section").classes("result-recommendations"):
                ui.label("PARA EL PRÓXIMO INTENTO").classes("result-section-title")
                for recommendation in evaluation.get("recommendations", []):
                    ui.label(recommendation).classes("result-recommendation")
            with ui.element("section").classes("review-section"):
                ui.label("DESGLOSE DE LA TÉCNICA").classes("result-section-title")
                for item in evaluation.get("results", []):
                    with ui.element("div").classes(
                        f'result-row {item.get("state", "problem")}'
                    ):
                        ui.label(
                            "✓" if item["state"] == "success" else "!"
                        ).classes(
                            "result-ok" if item["state"] == "success" else "result-missed"
                        )
                        with ui.element("div"):
                            ui.label(item["instruction"])
                            ui.label(item["feedback"]).classes("result-row-feedback")
                        delta = item.get("delta_beats")
                        detail = (
                            f'{item["verdict"]} · {float(delta):+g} beats'
                            if delta is not None
                            else item["verdict"]
                        )
                        ui.label(detail).classes(f'result-verdict {item["state"]}')
            previous_attempts = [
                candidate
                for candidate in attempt_repository.list_for_lesson(lesson.id)
                if candidate.id != attempt.id
            ][:3]
            if previous_attempts:
                with ui.element("section").classes("result-history"):
                    ui.label("INTENTOS ANTERIORES").classes("result-section-title")
                    for previous in previous_attempts:
                        previous_evaluation = previous.features.get("evaluation", {})
                        score = previous_evaluation.get(
                            "quality_score", previous.features.get("score_percentage", 0)
                        )
                        ui.label(
                            f'{previous.started_at[:16].replace("T", " ")} · {score}%'
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
