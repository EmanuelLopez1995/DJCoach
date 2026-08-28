"""Servicios y persistencia de lecciones."""

from .repository import LessonRepository
from .preparation import PreparationStatus, evaluate_preparation
from .recording import ReferenceTakeRecorder
from .take_repository import TakeRepository
from .features import FEATURE_SCHEMA_VERSION, extract_take_features
from .review import (
    PHASES,
    delete_event,
    merge_with_next,
    prepare_review_timeline,
    publish_validation_errors,
    set_event_phase,
    split_gesture,
    summarize_phases,
)
from .attempt_repository import AttemptRepository
from .guidance import (
    build_guidance_moments,
    build_guidance_steps,
    event_matches_step,
)
from .practice import GuidedPracticeRecorder
from .evaluation import evaluate_guided_attempt
from .initial_state import (
    InitialStateComparison,
    InitialStateItem,
    compare_initial_state,
)

__all__ = [
    "LessonRepository",
    "PreparationStatus",
    "ReferenceTakeRecorder",
    "TakeRepository",
    "FEATURE_SCHEMA_VERSION",
    "AttemptRepository",
    "GuidedPracticeRecorder",
    "evaluate_guided_attempt",
    "InitialStateComparison",
    "InitialStateItem",
    "build_guidance_steps",
    "build_guidance_moments",
    "event_matches_step",
    "compare_initial_state",
    "evaluate_preparation",
    "extract_take_features",
    "PHASES",
    "prepare_review_timeline",
    "delete_event",
    "set_event_phase",
    "split_gesture",
    "merge_with_next",
    "summarize_phases",
    "publish_validation_errors",
]
