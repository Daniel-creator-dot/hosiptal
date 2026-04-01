"""Thread-local flags for batched consultation side effects (e.g. multi-drug prescribe)."""
import threading

_state = threading.local()


def set_skip_prescription_encounter_note(skip: bool) -> None:
    _state.skip_prescription_encounter_note = bool(skip)


def skip_prescription_encounter_note() -> bool:
    return bool(getattr(_state, 'skip_prescription_encounter_note', False))
