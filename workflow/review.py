import math
import uuid
from datetime import datetime, timezone

from risk.ratios import score_from_ratios

RATIO_FIELDS = ("debt_to_equity", "current_ratio", "net_margin")
SCORE_FIELDS = RATIO_FIELDS + ("risk_level",)
VALID_LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")

HUMAN_ACTIONS = ("approve", "override", "rerun")

_NOTE_LABEL = {
    "approve": "Note",
    "override": "Reason",
    "rerun": "Hint",
    "rescore": "Hint used",
}


def new_event(action: str, reviewer: str, iteration: int, notes: str = "",
              before: dict | None = None, after: dict | None = None) -> dict:
    """One audit-trail entry. `before` / `after` are score dicts (or None when not relevant)."""
    return {
        "id": str(uuid.uuid4()),
        "at": datetime.now(timezone.utc).isoformat(),
        "iteration": iteration,
        "action": action,
        "reviewer": reviewer,
        "notes": (notes or "").strip(),
        "before": before,
        "after": after,
    }


def apply_override(current: dict, edited: dict | None, risk_level: str | None = None) -> dict:
    """Builds the analyst's corrected score.

    - Ratios the analyst did not type keep their current value.
    - The risk level and the notes are recalculated with the same rules as the automatic score
      (risk.ratios.score_from_ratios), so an override can never contradict the rules by accident.
    - If the analyst explicitly names a risk level, that level wins, and a note says so.
    """
    edited = edited or {}
    ratios = {}
    for field in RATIO_FIELDS:
        value = edited.get(field)
        if value is None:
            value = current.get(field)
        elif isinstance(value, bool) or not math.isfinite(float(value)):
            raise ValueError(f"{field} must be a finite number, got {value!r}")
        else:
            value = float(value)
        ratios[field] = value

    rule_score = score_from_ratios("override", **ratios)
    notes = ["Values were set by the analyst; the level and notes below were recalculated from them."]
    notes.extend(rule_score.notes)

    level = rule_score.risk_level
    if risk_level:
        wanted = risk_level.strip().upper()
        if wanted not in VALID_LEVELS:
            raise ValueError(f"risk_level must be one of {VALID_LEVELS}, got {risk_level!r}")
        if wanted != rule_score.risk_level:
            notes.append(f"Risk level set manually by the analyst to {wanted} "
                         f"(the rules give {rule_score.risk_level}).")
            level = wanted

    return {**ratios, "risk_level": level, "notes": notes}


def score_changes(before: dict | None, after: dict | None) -> list[str]:
    """['debt_to_equity 1.4 -> 1.3', 'risk_level MEDIUM -> LOW']. Empty if nothing changed."""
    if not before or not after:
        return []
    return [f"{f} {before.get(f)} -> {after.get(f)}"
            for f in SCORE_FIELDS if before.get(f) != after.get(f)]


def describe_event(event: dict) -> str:
    """One readable line for the terminal and the PDF. Plain ASCII on purpose."""
    action = event.get("action")
    changes = "; ".join(score_changes(event.get("before"), event.get("after")))

    if action == "approve":
        text = "Approved"
    elif action == "override":
        text = f"Override: {changes or 'no value changed'}"
    elif action == "rerun":
        text = "Asked for a re-run of the scoring"
    elif action == "rescore":
        text = f"System re-scored: {changes or 'same result'}"
    else:
        text = str(action)

    notes = event.get("notes")
    if notes:
        text += f". {_NOTE_LABEL.get(action, 'Note')}: {notes}"
    return text


def joined_human_notes(events: list[dict]) -> str:
    """All notes written by people, oldest first, for the report text and the legacy edit_notes field."""
    return " | ".join(e["notes"] for e in events if e.get("action") in HUMAN_ACTIONS and e.get("notes"))