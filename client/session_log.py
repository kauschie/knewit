# client/session_log.py
# =============================================================================
# Session log utility
#
# - Writes human-readable, machine-parsable logs to .session_logs/
# - Filenames: YYYYMMDD_HHMMSS.session.log
# - Line format: [event-type] {JSON payload}
#
# Event types (client perspective):
#   [session-start]    : session + client metadata
#   [session-end]      : session termination (graceful or not)
#   [question-received]: quiz question payload from host/server
#   [answer-submitted] : answer sent by this client
#   [answer-received]  : host/server announcement of correct answer
#   [chat-received]    : chat messages from others/host
#   [chat-submitted]   : chat messages sent by this client
#   [histogram-updated]: histogram / stats updates
#
# These logs are used to reconstruct last session state after a dropped
# connection: which questions were seen, what we answered, what was correct,
# and chat / histogram context. On startup, the client can read the latest
# log; if it was NOT terminated gracefully, it can reconstruct state.
# =============================================================================

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOG_DIR_NAME = "session_logs"
LOG_SUFFIX = ".session.log"

_EVENT_LINE_RE = re.compile(r"^\[(?P<event>[^\]]+)\]\s+(?P<payload>{.*})$")


class SessionLogger:
    """Append-only session logger for a single client run."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        # base_dir defaults to current working directory
        self.base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
        self.log_dir = self.base_dir / LOG_DIR_NAME
        self.log_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = self.log_dir / f"{ts}{LOG_SUFFIX}"

    # ---- low-level writer -------------------------------------------------

    def _write(self, event: str, payload: Dict[str, Any]) -> None:
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            **payload,
        }
        line = f"[{event}] {json.dumps(record, ensure_ascii=False)}\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)

    # ---- high-level API: what we actually log -----------------------------

    def log_session_start(
        self,
        session_id: str,
        client_id: str,
        role: str,
        server_url: str,
        username: Optional[str] = None,
    ) -> None:
        """Call once after login succeeds."""
        self._write(
            "session-start",
            {
                "session_id": session_id,
                "client_id": client_id,
                "role": role,
                "server_url": server_url,
                "username": username,
            },
        )

    def log_session_end(
        self,
        reason: Optional[str] = None,
        graceful: bool = True,
    ) -> None:
        """Call on clean shutdown (graceful=True) or explicit error cleanup.

        If the process crashes or is killed and never calls this, the last
        session log will look 'incomplete' and can be used for reconstruction.
        """
        self._write(
            "session-end",
            {
                "reason": reason,
                "graceful": graceful,
            },
        )

    def log_question_received(
        self,
        q_index: int,
        question_id: Optional[str],
        title: str,
        text: str,
        options: List[str],
    ) -> None:
        self._write(
            "question-received",
            {
                "q_index": q_index,
                "question_id": question_id,
                "title": title,
                "text": text,
                "options": options,
            },
        )

    def log_answer_submitted(
        self,
        q_index: int,
        answer_index: int,
        answer_value: Any,
    ) -> None:
        self._write(
            "answer-submitted",
            {
                "q_index": q_index,
                "answer_index": answer_index,
                "answer_value": answer_value,
            },
        )

    def log_answer_received(
        self,
        q_index: int,
        correct_index: int,
        correct_value: Any,
    ) -> None:
        self._write(
            "answer-received",
            {
                "q_index": q_index,
                "correct_index": correct_index,
                "correct_value": correct_value,
            },
        )

    def log_chat_received(
        self,
        from_user: str,
        msg: str,
        is_host: bool = False,
    ) -> None:
        self._write(
            "chat-received",
            {
                "from": from_user,
                "is_host": is_host,
                "msg": msg,
            },
        )

    def log_chat_submitted(
        self,
        msg: str,
    ) -> None:
        self._write(
            "chat-submitted",
            {
                "msg": msg,
            },
        )

    def log_histogram_updated(
        self,
        q_index: int,
        counts: List[int],
    ) -> None:
        self._write(
            "histogram-updated",
            {
                "q_index": q_index,
                "counts": counts,
            },
        )


# =============================================================================
# Reading / reconstructing a session from the latest log
# =============================================================================

@dataclass
class QuestionHistory:
    q_index: int
    question_id: Optional[str] = None
    title: str = ""
    text: str = ""
    options: List[str] = field(default_factory=list)
    answer_submitted_index: Optional[int] = None
    answer_submitted_value: Optional[Any] = None
    correct_index: Optional[int] = None
    correct_value: Optional[Any] = None
    histograms: List[List[int]] = field(default_factory=list)


@dataclass
class SessionHistory:
    session_id: Optional[str] = None
    client_id: Optional[str] = None
    role: Optional[str] = None
    server_url: Optional[str] = None
    username: Optional[str] = None

    # termination info
    terminated: bool = False
    terminated_gracefully: Optional[bool] = None
    termination_reason: Optional[str] = None

    questions: Dict[int, QuestionHistory] = field(default_factory=dict)
    chats: List[Dict[str, Any]] = field(default_factory=list)

    def latest_question_index(self) -> Optional[int]:
        if not self.questions:
            return None
        return max(self.questions.keys())

    def terminated_successfully(self) -> bool:
        """True if we have a session-end event and it was graceful."""
        return bool(self.terminated and self.terminated_gracefully)

    def unanswered_questions(self) -> List[int]:
        """Indices of questions that were seen but have no submitted answer."""
        return [
            idx
            for idx, q in self.questions.items()
            if q.answer_submitted_index is None
        ]

    def answered_without_reveal(self) -> List[int]:
        """Indices with a submitted answer but no correct answer received."""
        return [
            idx
            for idx, q in self.questions.items()
            if q.answer_submitted_index is not None and q.correct_index is None
        ]


def _ensure_question(history: SessionHistory, q_index: int) -> QuestionHistory:
    if q_index not in history.questions:
        history.questions[q_index] = QuestionHistory(q_index=q_index)
    return history.questions[q_index]


def get_latest_log_path(base_dir: Optional[Path] = None) -> Optional[Path]:
    base = Path(base_dir) if base_dir is not None else Path.cwd()
    log_dir = base / LOG_DIR_NAME
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob(f"*{LOG_SUFFIX}"))
    return logs[-1] if logs else None


def load_session_history_from_log(
    path: Optional[Path] = None,
    base_dir: Optional[Path] = None,
) -> Optional[SessionHistory]:
    """Load and reconstruct SessionHistory from a given log file.

    If `path` is None, this uses the latest log in .session_logs/.
    Returns None if nothing is found.
    """
    if path is None:
        path = get_latest_log_path(base_dir=base_dir)
        if path is None:
            return None

    history = SessionHistory()

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            m = _EVENT_LINE_RE.match(line)
            if not m:
                # ignore malformed lines
                continue
            event = m.group("event")
            try:
                payload = json.loads(m.group("payload"))
            except json.JSONDecodeError:
                continue

            # Strip ts for convenience
            payload.pop("ts", None)

            if event == "session-start":
                history.session_id = payload.get("session_id")
                history.client_id = payload.get("client_id")
                history.role = payload.get("role")
                history.server_url = payload.get("server_url")
                history.username = payload.get("username")

            elif event == "session-end":
                history.terminated = True
                history.terminated_gracefully = payload.get("graceful")
                history.termination_reason = payload.get("reason")

            elif event == "question-received":
                q_idx = payload.get("q_index")
                if q_idx is None:
                    continue
                q = _ensure_question(history, q_idx)
                q.question_id = payload.get("question_id")
                q.title = payload.get("title", "")
                q.text = payload.get("text", "")
                q.options = payload.get("options", []) or []

            elif event == "answer-submitted":
                q_idx = payload.get("q_index")
                if q_idx is None:
                    continue
                q = _ensure_question(history, q_idx)
                q.answer_submitted_index = payload.get("answer_index")
                q.answer_submitted_value = payload.get("answer_value")

            elif event == "answer-received":
                q_idx = payload.get("q_index")
                if q_idx is None:
                    continue
                q = _ensure_question(history, q_idx)
                q.correct_index = payload.get("correct_index")
                q.correct_value = payload.get("correct_value")

            elif event == "histogram-updated":
                q_idx = payload.get("q_index")
                if q_idx is None:
                    continue
                q = _ensure_question(history, q_idx)
                counts = payload.get("counts") or []
                q.histograms.append(counts)

            elif event in ("chat-received", "chat-submitted"):
                # Just append chat events as-is for now
                history.chats.append({"event": event, **payload})

            # Other events can be added here later.

    return history


def load_latest_history(
    base_dir: Optional[Path] = None,
) -> Optional[Tuple[SessionHistory, Path]]:
    """Convenience: load the latest session history + its path.

    Returns (history, path) or None if there are no logs.
    """
    path = get_latest_log_path(base_dir=base_dir)
    if path is None:
        return None
    history = load_session_history_from_log(path=path)
    if history is None:
        return None
    return history, path


def load_latest_incomplete_history(
    base_dir: Optional[Path] = None,
) -> Optional[Tuple[SessionHistory, Path]]:
    """Return the latest session history ONLY if it was not terminated successfully.

    Intended usage at client startup:

        result = load_latest_incomplete_history()
        if result is not None:
            history, path = result
            # use `history` to reconstruct quiz state, then reconnect
    """
    result = load_latest_history(base_dir=base_dir)
    if result is None:
        return None
    history, path = result
    if history.terminated_successfully():
        return None
    return history, path
