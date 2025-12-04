"""Quiz data types and state management."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
import math
import secrets
import json
import uuid
from pathlib import Path
from fastapi import WebSocket
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))
from client.common import logger  # adjust import path if needed


class QuizState(Enum):
    LOBBY = "lobby"
    ACTIVE = "active"
    FINISHED = "finished"

@dataclass
class Question:
    prompt: str
    options: List[str]  # 4 options
    correct_idx: int    # 0-3
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "options": self.options,
            "correct_idx": self.correct_idx
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            prompt=data["prompt"],
            options=data["options"],
            correct_idx=data["correct_idx"]
        )

@dataclass
class StudentQuestion:
    """Question without the correct answer (for student view)."""
    id: str
    prompt: str
    options: List[str]
    index: int
    total: int
    timer: Optional[int] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "options": self.options,
            "index": self.index,
            "total": self.total,
            "timer": self.timer
        }
    
    @classmethod
    def from_question(cls, question: Question, timer: int = 20) -> "StudentQuestion":
        return cls(
            id=question.id,
            prompt=question.prompt,
            options=question.options,
            index=0,  # default index
            total=0,   # default total
            timer=timer
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> "StudentQuestion":
        return cls(
            id=data["id"],
            prompt=data["prompt"],
            options=data["options"],
            index=data.get("index", 0),
            total=data.get("total", 0),
            timer=data.get("timer")
        )

@dataclass
class Player:
    """A player in a quiz session."""
    player_id: str
    score: float = 0.0
    correct_count: int = 0
    answered_current: bool = False
    round_scores: List[float] = field(default_factory=list)  # scores per question
    # Runtime/network metadata (updated by server on pings/pongs)
    last_pong: Optional[float] = None  # server epoch seconds when last pong received
    latency_ms: Optional[float] = None
    last_seen: Optional[float] = None
    is_muted: bool = False
    # responses: List[Dict] = field(default_factory=list)  # List of {question_id, answer_idx, correct, answer_time} // moving to answer_log

    status: str = "active" # This is for timeout and recovery "active" / "stale" / "removed"

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "score": round(self.score, 1),
            "correct_count": self.correct_count,
            "round_scores": [round(s, 1) for s in self.round_scores],
            "latency_ms": None if self.latency_ms is None else round(self.latency_ms, 1),
            "is_muted": self.is_muted,
        }

@dataclass
class Quiz:
    """A saved quiz with multiple questions."""
    title: str
    questions: List[Question]
    quiz_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    default_timer: int = 20
    default_points: float = 10

    
    def to_dict(self) -> dict:
        return {
            "quiz_id": self.quiz_id,
            "title": self.title,
            "questions": [q.to_dict() for q in self.questions],
            "default_timer": self.default_timer,
            "default_points": self.default_points
        }
    
    def save_to_file(self, directory: str = "quizzes"):
        """Save quiz to JSON file."""
        Path(directory).mkdir(exist_ok=True)
        filepath = Path(directory) / f"{self.quiz_id}.json"
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        return str(filepath)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Quiz":
        return cls(
            quiz_id=data.get("quiz_id", str(uuid.uuid4())[:8]),
            title=data["title"],
            questions=[Question.from_dict(q) for q in data["questions"]],
            default_timer=data.get("default_timer", 20),
            default_points=data.get("default_points", 10.0)
        )
    
    @classmethod
    def load_from_file(cls, filepath: str) -> "Quiz":
        """Load quiz from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)


    @classmethod
    def list_saved_quizzes(cls, directory: str = "quizzes") -> List[dict]:
        """List all saved quizzes."""
        quiz_dir = Path(directory)
        if not quiz_dir.exists():
            return []
        
        quizzes = []
        for filepath in quiz_dir.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                quizzes.append({
                    "quiz_id": data["quiz_id"],
                    "title": data["title"],
                    "num_questions": len(data["questions"])
                })
            except Exception:
                continue
        return quizzes


@dataclass
class QuizSession:
    id: str
    host_id: str
    state: QuizState = QuizState.LOBBY

    # Core entities
    players: Dict[str, Player] = field(default_factory=dict)          # player_id -> Player
    kicked_players: Set[str] = field(default_factory=set)   # set of player_ids who have been kicked
    quiz: Optional[Quiz] = None
    password: Optional[str] = None

    # Question/answer runtime state
    current_question_idx: int = -1
    
    # answer_counts maps answer_idx -> count
    answer_counts: Dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0, 2: 0, 3: 0})
    
    # answer_log maps question_idx -> {player_id: answer_idx}
    answer_log: Dict[int, Dict[str, int]] = field(default_factory=dict)
    
    # answer_time_log maps question_idx -> {player_id: elapsed_time}
    answer_time_log: Dict[int, Dict[str, float]] = field(default_factory=dict)
    
    # Live connections
    connections: Dict[str, WebSocket] = field(default_factory=dict)   # player_id -> ws

    # ---------- Player management ----------

    def add_player(self, player_id: str, ws: WebSocket) -> Optional[Player]:
        """Add player to lobby. Returns None if name is taken or user is kicked."""
        
        # check if kicked
        if player_id in self.kicked_players:
            return None
        
        # check if name taken / active
        for player in self.players.values():
            if player.player_id == player_id:
                return None

        player = Player(player_id=player_id)
        self.players[player_id] = player
        self.connections[player_id] = ws
        return player

    def remove_player(self, player_id: str) -> None:
        """Remove a player from the session."""
        self.players.pop(player_id, None)
        self.connections.pop(player_id, None)

    def kick_player(self, player_id: str) -> None:
        """Kick a player from the session."""
        self.kicked_players.add(player_id)
        self.remove_player(player_id)

    # ---------- Quiz lifecycle ----------

    def load_quiz(self, quiz: Quiz) -> None:
        """Load a quiz into the session and reset per-quiz state."""
        self.quiz = quiz
        self.current_question_idx = -1
        self.answer_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.answer_log.clear()
        self.answer_time_log.clear()
        self.state = QuizState.LOBBY

        # Reset player-level quiz state
        for player in self.players.values():
            player.score = 0.0
            player.correct_count = 0
            player.answered_current = False
            player.round_scores = []

    def start_quiz(self) -> bool:
        """Start the quiz. Returns False if no quiz is loaded."""
        logger.debug(f"[QuizSession] Starting quiz in session {self.id}")
        if not self.quiz or len(self.quiz.questions) == 0:
            return False
        self.state = QuizState.ACTIVE
        # We leave current_question_idx at -1; first call to next_question will move to 0.
        return True

    def next_question(self) -> Optional[Question]:
        """Advance to the next question. Returns None if the quiz is over."""
        logger.debug(f"[QuizSession] Advancing to next question in session {self.id}")
        if not self.quiz:
            return None

        self.current_question_idx += 1
        if self.current_question_idx >= len(self.quiz.questions):
            # No more questions; mark session as finished
            self.state = QuizState.FINISHED
            return None

        # Initialize tracking for this question
        self._reset_current_question_state()
        return self.quiz.questions[self.current_question_idx]

    def get_current_question(self) -> Optional[Question]:
        """Return the current question, or None if not in a valid range."""
        if not self.quiz or self.current_question_idx < 0:
            return None
        if self.current_question_idx >= len(self.quiz.questions):
            return None
        return self.quiz.questions[self.current_question_idx]
 
    # ---------- Answer tracking ----------
       
    def _reset_current_question_state(self) -> None:
        """Reset per-question state (answers, flags, counts) for the active question."""
        logger.debug(f"[QuizSession] Resetting state for question {self.current_question_idx} in session {self.id}")
        # Reset counts
        self.answer_counts = {0: 0, 1: 0, 2: 0, 3: 0}

        # Ensure log bucket exists for this question
        if self.current_question_idx >= 0:
            self.answer_log[self.current_question_idx] = {}

        # Reset each player's "answered_current" flag
        for player in self.players.values():
            player.answered_current = False

    def record_answer(self, player_id: str, answer_idx: int, elapsed: float | None) -> bool:
        """
            Record an answer index and time.
            Does NOT update score or correctness counts (deferred to close_question_scoring).
            Returns True/False for immediate client feedback.
        """
        logger.debug(f"[QuizSession] Recording answer for player {player_id} in session {self.id} with answer {answer_idx}")
        player = self.players.get(player_id)
        if not player:
            return False

        question = self.get_current_question()
        if question is None:
            return False

        q_idx = self.current_question_idx
        # Ensure we have a log bucket for this question
        bucket = self.answer_log.setdefault(q_idx, {})
        tbucket = self.answer_time_log.setdefault(q_idx, {})

        # Reject if they already answered (either via flag or log)
        if player.answered_current or player_id in bucket:
            #if you want to allow changing answers, remove count from previous answer here
            # if player_id in bucket:
            #     prev_answer = bucket[player_id]
            #     if prev_answer in self.answer_counts:
            #         self.answer_counts[prev_answer] -= 1
            
            #  will ALSO need to allow the quiz widget button to be clicked more than once TODO
            
            return False


        # Record in answer and time logs
        bucket[player_id] = answer_idx
        if elapsed is not None:
            tbucket[player_id] = elapsed

        # Update quick counts (for host histogram)
        if answer_idx in self.answer_counts:
            self.answer_counts[answer_idx] += 1

        # Mark player as having answered
        player.answered_current = True

        # Score if correct
        is_correct = (0 <= answer_idx < len(question.options)) and (answer_idx == question.correct_idx)
        return is_correct
    
    def close_question_scoring(self) -> None:
        """
        Finalize scoring for the current question.
        Appends points earned in this round to player.round_scores.
        """
        q = self.get_current_question()
        if not q:
            return

        current_idx = self.current_question_idx
        
        # get logs for this question
        answers = self.answer_log.get(current_idx, {})
        times = self.answer_time_log.get(current_idx, {})
        
        # Quiz-level settings - adjust as needed for more complex scoring
        max_points = self.quiz.default_points if self.quiz else 10.0
        total_time = float(self.quiz.default_timer if self.quiz else 20)
        min_points = math.floor(max_points * 0.5)
        
        for pid, player in self.players.items():
            
            # If we already have a score for this question index, skip it.
            # round_scores should have length == current_idx after this update.
            # If it's already > current_idx, we've already scored this round.
            if len(player.round_scores) > current_idx:
                continue
            
            # Ensure round_scores list padds unanswered questions with 0
            while(len(player.round_scores) < current_idx):
                player.round_scores.append(0)
            
            # Determine points earned for this specific question
            points_awarded = 0.0
            if pid in answers:
                ans_idx = answers[pid]
                if ans_idx == q.correct_idx:
                    # correct answer
                    player.correct_count += 1
                    
                    # Time-based scoring (linear decay from max to min points)
                    client_elapsed = times.get(pid, 0.0)
                    remaining_time = max(0.0, total_time - client_elapsed)
                    points_awarded = max(min_points, (remaining_time / total_time) * max_points)
                    
            player.score += points_awarded
            player.round_scores.append(points_awarded)
            # Note: player.score is already updated in record_answer

    def get_answer_counts(self, question_idx: Optional[int] = None) -> List[int]:
        """
        Compute answer counts for the given question index (or current question).
        Returns a list sized to 4 (A–D) for now.
        """
        if question_idx is None:
            question_idx = self.current_question_idx

        if question_idx is None or question_idx < 0:
            return [0, 0, 0, 0]

        bucket = self.answer_log.get(question_idx, {})
        counts = [0, 0, 0, 0]
        for _, ans in bucket.items():
            if 0 <= ans < len(counts):
                counts[ans] += 1
        return counts

    # ---------- Serialization ----------

    def to_dict(self) -> dict:
        """Convert session state to a dict for JSON (for admin/debug)."""
        return {
            "session_id": self.id,
            "host_id": self.host_id,
            "state": self.state.value,
            "password": self.password,
            "players": [p.to_dict() for p in self.players.values()],
            "quiz_title": self.quiz.title if self.quiz else None,
            "current_question": self.current_question_idx + 1 if self.current_question_idx >= 0 else 0,
            "total_questions": len(self.quiz.questions) if self.quiz else 0,
        }

# Global state (in real app, use Redis)
quiz_sessions: Dict[str, QuizSession] = {}

def create_session(host_id: str, session_id: str | None = None, password: str | None = None) -> QuizSession:
    """Create a new quiz session with a unique ID."""
    if session_id is None:
        session_id = secrets.token_urlsafe(6)  # Shorter, easier to share
    elif session_id in quiz_sessions:
        raise ValueError("Session ID already exists.")
    
    session = QuizSession(
        id=session_id,
        host_id=host_id,
        password=password
    )
    quiz_sessions[session_id] = session
    return session

def get_session(session_id: str) -> Optional[QuizSession]:
    """Get a quiz session by ID."""
    return quiz_sessions.get(session_id)

def delete_session(session_id: str):
    """Delete a session."""
    quiz_sessions.pop(session_id, None)





