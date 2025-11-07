# quiz_preview_log.py (or inline with your widgets)

from __future__ import annotations
from typing import Any, Dict, List, Optional
import string
import textwrap

from textual.reactive import reactive
from textual.widgets import RichLog
from rich.text import Text


class QuizPreviewLog(RichLog):
    """Scrollable quiz preview using RichLog (styled, fast, simple)."""

    # external API state
    quiz: Optional[Dict[str, Any]] = reactive(None, init=False)
    current_q: Optional[int] = reactive(None, init=False)   # 0-based index
    show_answers: bool = reactive(False, init=False)

    def __init__(self, *args, **kwargs) -> None:
        # sensible defaults: wrap lines, don't trim, keep auto-scroll off by default
        kwargs.setdefault("wrap", True)
        kwargs.setdefault("auto_scroll", False)
        kwargs.setdefault("highlight", False)
        # Don't set max_lines so preview isn't trimmed (or set a big number if you prefer)
        super().__init__(*args, **kwargs)
        # precomputed layout info (question index -> logical start line)
        self._question_start_line = {}
        self._total_lines = 0
        self._last_width = 0

    # ---- Public API --------------------------------------------------------

    def set_quiz(self, quiz: Optional[Dict[str, Any]]) -> None:
        self.quiz = quiz   # triggers re-render via watch

    def set_current_question(self, idx: Optional[int]) -> None:
        self.current_q = idx

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
        width = max(1, getattr(self.size, "width", 80))
        self._compute_layout(width)
        self._render_all()

    def watch_current_q(self, _: Optional[int]) -> None:
        width = max(1, getattr(self.size, "width", 80))
        self._compute_layout(width)
        self._render_all()

    # ---- Layout helpers --------------------------------------------------

    def _count_wrapped_lines(self, text: str, width: int) -> int:
        """Estimate the number of wrapped terminal lines for `text` at `width`.

        This uses textwrap.wrap as a lightweight approximation; it is fast and
        usually accurate for plain text when `wrap=True` on the log.
        """
        if width <= 0:
            width = 80
        wrapped = textwrap.wrap(text, width=width) or [""]
        return max(1, len(wrapped))

    def _compute_layout(self, width: int) -> None:
        """Compute logical start line for each question and total logical lines.

        This does not write to the widget; it only measures how many wrapped
        lines each piece of text will occupy so we can scroll to a question
        later without re-wrapping during render.
        """
        self._question_start_line = {}
        total = 0

        if not self.quiz:
            self._total_lines = 0
            self._last_width = width
            return

        questions: List[Dict[str, Any]] = self.quiz.get("questions", [])

        # Title area
        title = self.quiz.get("title", "Untitled Quiz")
        total += self._count_wrapped_lines(title, width)
        info = f"{len(questions)} question{'s' if len(questions) != 1 else ''}"
        total += self._count_wrapped_lines(info, width)
        total += 1  # blank line

        # Questions
        for i, q in enumerate(questions):
            # record starting logical line for this question
            self._question_start_line[i] = total

            prompt = q.get("prompt", "(no prompt)")
            prefix = "▶ " if (self.current_q is not None and i == self.current_q) else ""
            header_text = prefix + f"Q{i+1}. " + prompt
            total += self._count_wrapped_lines(header_text, width)

            opts: List[str] = q.get("options", [])
            correct = q.get("correct_idx", None)
            for j, opt in enumerate(opts):
                letter = string.ascii_uppercase[j] if j < 26 else str(j+1)
                line_text = "  " + f"{letter}. " + opt
                if self.show_answers and correct is not None and j == correct and i <= (self.current_q or -1):
                    line_text += "  ✅"
                total += self._count_wrapped_lines(line_text, width)

            total += 1  # blank separator

        self._total_lines = total
        self._last_width = width

    def _scroll_to_current(self) -> None:
        """Scroll so the current question is visible (with one-line context).

        We try a fraction-based scroll helper first, then fall back to coordinate
        based methods. Uses the precomputed `_question_start_line` and
        `_total_lines`.
        """
        if self.current_q is None:
            return
        start_line = self._question_start_line.get(self.current_q)
        if start_line is None:
            return

        target_line = max(0, start_line - 1)
        frac = target_line / max(1, self._total_lines)

        # Prefer a fraction-based API if available
        if hasattr(self, "scroll_to_fraction"):
            try:
                self.scroll_to_fraction(frac)
                return
            except Exception:
                pass

        # Fallback: try scroll_to(y) using virtual/content height if available
        try:
            height = getattr(self, "virtual_size", None)
            if height:
                h = getattr(height, "height", None) or (height[1] if isinstance(height, (tuple, list)) else None)
            else:
                h = getattr(self.size, "height", None) or 0
            if h:
                y = int(frac * max(1, h))
                self.scroll_to(y)
                return
        except Exception:
            pass

        # Last-resort: scroll to end/home as appropriate
        try:
            if hasattr(self, "scroll_to_end"):
                self.scroll_to_end()
            elif hasattr(self, "scroll_end"):
                self.scroll_end()
        except Exception:
            pass

    def watch_show_answers(self, _: bool) -> None:
        width = max(1, getattr(self.size, "width", 80))
        self._compute_layout(width)
        self._render_all()

    def on_resize(self, event) -> None:
        """Recompute layout when the widget is resized."""
        width = max(1, getattr(self.size, "width", 80))
        if width != self._last_width:
            self._compute_layout(width)
            self._render_all()

    # ---- Rendering ---------------------------------------------------------

    def _render_all(self) -> None:
        """Clear and re-render the full preview."""
        self.clear()

        if not self.quiz:
            self.write(Text("No quiz selected.", style="dim"))
            self.scroll_home()
            return

        title = self.quiz.get("title", "Untitled Quiz")
        questions: List[Dict[str, Any]] = self.quiz.get("questions", [])

        # Title
        self.write(Text(title, style="bold underline"))
        self.write(Text(f"{len(questions)} question{'s' if len(questions)!=1 else ''}", style="dim"))
        self.write(Text(""))

        # Questions
        for i, q in enumerate(questions, 1):
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

        # Keep content anchored to top for preview readability
        # self.scroll_home()
        # Ensure we scroll after the next refresh/layout so scroll helpers work
        try:
            self.call_after_refresh(self._scroll_to_current)
        except Exception:
            # If call_after_refresh isn't available on this Textual version,
            # try scheduling with a short timeout via post_message or skip.
            try:
                self._scroll_to_current()
            except Exception:
                pass
