from __future__ import annotations
from typing import Any, Dict, List, Optional
import string

from textual.containers import VerticalScroll
from textual.widgets import Markdown
from textual.reactive import reactive
from common import logger


class QuizPreviewMD(VerticalScroll):
    """Markdown-based, scrollable quiz preview with optional highlights."""

    CSS="""
    #quiz-md {
        overflow-x: hidden;
    }
    """



    quiz: Optional[Dict[str, Any]] = reactive(None, init=False)
    current_q: Optional[int] = reactive(None, init=False)  # 0-based
    show_answers: bool = reactive(False, init=False)

    def on_mount(self) -> None:
        self._md = Markdown("", id="quiz-md")
        self.mount(self._md)
        self._update_md()

    # --- public API ---------------------------------------------------------
    def set_quiz(self, quiz: Optional[Dict[str, Any]]) -> None:
        self.quiz = quiz  # triggers watch_quiz

    def set_current_question(self, idx: Optional[int]) -> None:
        self.current_q = idx  # triggers re-render

    def set_show_answers(self, show: bool) -> None:
        self.show_answers = show  # triggers re-render

    # --- reactives ----------------------------------------------------------
    def watch_quiz(self, _: Optional[Dict[str, Any]]) -> None:
        self._update_md()

    def watch_current_q(self, _: Optional[int]) -> None:
        self._update_md()

    def watch_show_answers(self, _: bool) -> None:
        self._update_md()

    # --- rendering helper (DO NOT name this `_render`) ----------------------
    def _update_md(self) -> None:
        if not hasattr(self, "_md"):
            return  # not mounted yet

        if not self.quiz:
            self._md.update("_No quiz selected._")
            self.scroll_home(animate=False)
            return

        title = self.quiz.get("title", "Untitled Quiz")
        qs: List[Dict[str, Any]] = self.quiz.get("questions", [])

        lines: List[str] = [f"# {self._esc(title)}", ""]
        for i, q in enumerate(qs, 1):
            prompt = q.get("prompt", "(no prompt)")
            opts: List[str] = q.get("options", [])
            correct = q.get("correct_idx", None)

            header = f"**Q{i}.** {self._esc(prompt)}"
            if self.current_q is not None and (i - 1) == self.current_q:
                lines.append(f"> {header}")  # emphasize current question
            else:
                lines.append(header)

            letters = list(string.ascii_uppercase[: max(0, len(opts))])
            for j, text in enumerate(opts):
                letter = letters[j] if j < len(letters) else f"{j+1}"
                mark = " ✅" if (self.show_answers and correct is not None and j == correct) else ""
                lines.append(f"- **{letter}.** {self._esc(text)}{mark}")

            lines.append("")

        self._md.update("\n".join(lines))
        # optional: keep newest content in view
        self.call_after_refresh(lambda: self.scroll_end(animate=False))

    @staticmethod
    def _esc(text: str) -> str:
        # Minimal escaping to keep Markdown intact but readable
        return (text.replace("\\", "\\\\")
                    .replace("*", "\\*").replace("_", "\\_")
                    .replace("`", "\\`").replace("[", "\\[")
                    .replace("]", "\\]"))
