# quiz_preview_log.py (or inline with your widgets)

from __future__ import annotations
from typing import Any, Dict, List, Optional
import string

from textual.reactive import reactive
from textual.widgets import RichLog
from rich.text import Text
from common import logger


class QuizPreviewLog(RichLog):
    """Scrollable quiz preview using RichLog (styled, fast, simple)."""

    # external API state
    quiz: Optional[Dict[str, Any]] = reactive(None, init=False)
    current_q: Optional[int] = reactive(None, init=False)   # 0-based index
    show_answers: bool = reactive(False, init=False)
    message: Optional[str] = reactive(None)

    def __init__(self, *args, **kwargs) -> None:
        # sensible defaults: wrap lines, don't trim, keep auto-scroll off by default
        kwargs.setdefault("wrap", True)
        kwargs.setdefault("auto_scroll", False)
        kwargs.setdefault("highlight", False)
        super().__init__(*args, **kwargs)
        self.already_scrolled = True


    # ---- Public API --------------------------------------------------------

    def set_quiz(self, quiz: Optional[Dict[str, Any]]) -> None:
        self.message = None
        self.set_current_question(0)
        self.quiz = quiz   # triggers re-render via watch

    def set_message(self, msg: str | Text) -> None:
        """ Display a specific message (e.g. results) clearing the quiz preview."""
        self.quiz = None
        if isinstance(msg, str):
            self.message = Text.from_markup(msg)
        else:
            self.message = msg
        self._render_all()
            
    def set_current_question(self, idx: Optional[int]) -> None:
        self.current_q = idx
        if self.already_scrolled is True:
            # logger.debug("Current question changed; resetting already_scrolled to False")
            self.already_scrolled = False

    def set_show_answers(self, show: bool) -> None:
        self.show_answers = show
        
    def get_correct_answer_index(self) -> Optional[int]:
        if not self.quiz or self.current_q is None:
            return None
        questions = self.quiz.get("questions", [])
        if 0 <= self.current_q < len(questions):
            return questions[self.current_q].get("correct_idx")
        return None

    # ---- Reactives ---------------------------------------------------------

    def watch_quiz(self, _: Optional[Dict[str, Any]]) -> None:
        self._render_all()

    def watch_current_q(self, _: Optional[int]) -> None:
        self._render_all()

    def watch_show_answers(self, _: bool) -> None:
        self._render_all()

    def on_resize(self, event) -> None:
        self._render_all()

    # ---- Rendering ---------------------------------------------------------

    def _render_all(self) -> None:
        """Clear and re-render the full preview."""
        self.clear()
        if self.message:
            self.write(self.message)
            return

        if not self.quiz:
            self.write(Text("No quiz selected.", style="dim"))
            return

        title = self.quiz.get("title", "Untitled Quiz")
        questions: List[Dict[str, Any]] = self.quiz.get("questions", [])

        # Title
        self.write(Text(title, style="bold underline"))
        self.write(Text(f"{len(questions)} question{'s' if len(questions)!=1 else ''}", style="dim"))
        self.write(Text(""))

        # Questions
        for i, q in enumerate(questions, 1):
            if self.current_q is None or i > self.current_q+1:
                break
            
            prompt = q.get("prompt", "(no prompt)")
            opts: List[str] = q.get("options", [])
            correct = q.get("correct_idx", None)

            # Header line (highlight current question)
            header = Text()
            prefix = "▶ " if (self.current_q is not None and (i - 1) == self.current_q) else ""
            header.append(prefix, style="yellow" if prefix else "")
            header.append(f"Q{i}. ", style="bold")
            header.append(prompt)
            if prefix:
                header.stylize("bold yellow")
            self.write(header)

            # Options (A., B., C., …) with optional ✅ on the correct one
            letters = list(string.ascii_uppercase[: max(0, len(opts))]) or []
            for j, text in enumerate(opts):
                line = Text("  ")  # indent
                # Letter
                letter = letters[j] if j < len(letters) else f"{j+1}"
                line.append(f"{letter}. ", style="bold")

                # Body
                line.append(text)

                # Correct mark
                if self.show_answers and correct is not None and j == correct and (i-1) <= self.current_q:
                    line.append("  ✅", style="green")
                elif self.current_q is not None and (i - 1) < self.current_q and correct is not None and j == correct:
                    line.append("  ✅", style="green")
                self.write(line)

            self.write(Text(""))  # blank line between questions

        # scroll to the bottom after layout so animation has real geometry
        if not self.already_scrolled:
            try:
                # do it real slowly
                
                # self.call_after_refresh(lambda: self.scroll_end(animate=True, duration=5, easing="out_cubic"))
                self.call_after_refresh(lambda: self.scroll_end(animate=True, speed=5, easing="out_cubic"))
                # logger.debug("Scheduled scroll to end after refresh.")
                
            except Exception:
                # fallback if call_after_refresh isn't available in this Textual
                # version — call directly (may be instantaneous)
                # logger.debug("call_after_refresh not available; scrolling directly")
                self.scroll_end(animate=True, duration=5, easing="out_cubic")
            finally:
                # logger.debug("Setting already_scrolled to True after scrolling.")
                self.already_scrolled = True