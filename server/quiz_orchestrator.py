"""Quiz orchestration logic (timing, scoring, and flow control).

This module is intentionally *server-side only* and does not perform
any WebSocket I/O. `app.py` remains responsible for sending messages
to clients; the orchestrator only manipulates `QuizSession` state and
returns data structures that the server can broadcast.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import time

from quiz_types import QuizSession, QuizState, Question  # adjust import path if needed


# Optional timing defaults (not yet wired into app.py)
READ_TIME = 5     # seconds to read question before answers appear
ANSWER_TIME = 10  # seconds to answer each question
REVIEW_TIME = 3   # seconds to show results before next question


@dataclass
class QuizOrchestrator:
    """
    Orchestrates a single QuizSession.

    Responsibilities:
    - Coordinate quiz start / next-question / finish flow.
    - Optionally enforce timings (read/answer/review) if enabled.
    - Centralize any scoring or per-question bookkeeping that goes
      beyond `QuizSession.record_answer`.
    - Provide helper methods that app.py can call to build payloads
      for host / student UIs.
    """
    session: QuizSession

    # high-level behavior flags
    auto_advance: bool = False   # if True, can later drive a background tick loop
    read_time: float = READ_TIME
    answer_time: float = ANSWER_TIME
    review_time: float = REVIEW_TIME

    # simple phase tracking; you can expand this later to a richer Enum
    phase: str = "idle"          # "idle", "question", "review", "finished"
    phase_started_at: float = field(default_factory=time.time)

    # ---------- Lifecycle hooks ----------

    def on_quiz_loaded(self) -> None:
        """
        Called after a new quiz is loaded into the session.

        At this point, `session.load_quiz(...)` has already reset
        per-quiz state (current_question_idx, scores, answer_log, etc.).
        """
        self.phase = "idle"
        self.phase_started_at = time.time()

    async def start_quiz(self) -> bool:
        """
        Called when the host presses 'Start Quiz'.

        Returns True if the quiz was successfully started and a first
        question is now active; False if there was no quiz loaded.
        """
        if not self.session.start_quiz():
            return False

        question = self.session.next_question()
        if not question:
            # No questions in quiz or some other anomaly
            self.session.state = QuizState.FINISHED
            self.phase = "finished"
            return False

        self.phase = "question"
        self.phase_started_at = time.time()
        # app.py will now broadcast the question to clients based on
        # `self.session.get_current_question()`.
        return True

    async def advance_to_next_question(self) -> Optional[Question]:
        """
        Host-initiated 'next question' action.

        Returns the new Question if one exists; otherwise None, in which
        case the quiz should be considered finished.
        """
        question = self.session.next_question()
        if question is None:
            # Quiz is over.
            self.phase = "finished"
            self.phase_started_at = time.time()
            return None

        self.phase = "question"
        self.phase_started_at = time.time()
        return question

    async def submit_answer(self, player_id: str, answer_idx: int, elapsed: float) -> bool:
        """
        Wrapper around `session.record_answer` in case we want to add
        per-question or per-player rules later (e.g., streaks, speed bonuses based on time).
        """
        return self.session.record_answer(player_id, answer_idx, elapsed)

    async def end_question(self) -> None:
        """
        Hook for 'end question' actions (host pressing a button).

        You can later:
        - freeze submission for this question,
        - compute per-question stats,
        - snapshot histogram for the host,
        - transition to a 'review' phase.
        """
        self.phase = "review"
        self.phase_started_at = time.time()
        # Note: actual messaging to host/students is still done in app.py

    async def finish_quiz(self) -> List[Dict[str, int]]:
        """
        Finalize the quiz and produce a leaderboard suitable for broadcasting.

        Returns:
            A list of { "name": ..., "score": ... } sorted by score desc.
        """
        self.session.state = QuizState.FINISHED
        self.phase = "finished"
        self.phase_started_at = time.time()
        return self.get_leaderboard()

    # ---------- Derived data helpers ----------

    def get_current_histogram(self) -> List[int]:
        """
        Compute the current question's answer histogram.

        This uses `session.answer_log`, so it works even if players
        disconnect/reconnect mid-quiz.
        """
        return self.session.get_answer_counts()

    def get_leaderboard(self) -> List[Dict[str, int]]:
        """
        Return a sorted leaderboard for the session.

        Structure matches what app.py already broadcasts at the end of
        a quiz:
            [{"name": player_id, "score": score}, ...]
        """
        players_sorted = sorted(
            self.session.players.values(),
            key=lambda p: p.score,
            reverse=True,
        )
        return [
            {"name": p.player_id, "score": p.score}
            for p in players_sorted
        ]
