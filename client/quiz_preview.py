from typing import Any, Dict, List, Optional
import string

from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Static, Rule
from textual.reactive import reactive
from quiz_selector import logger


class QuizPreview(VerticalScroll):
    """Scrollable preview of the selected quiz (title, questions, options)."""

    DEFAULT_CSS = """
    QuizPreview {
        padding: 1 2;
        background: $panel;
        border: solid green;
        height: 1fr;              /* fill available space in the parent */
        content-align: center top;  /* align content to top-left */
        align: center middle;
        text-align: center;
    }

    .qp-title        { padding: 0 0 1 0; text-align: center;}
    .qp-subtitle     { color: $text-muted; padding-bottom: 1; text-align: center; }
    .qp-sep          { height: 1; background: $surface; opacity: 15%; margin: 1 0; }

    .qp-qprompt      { text-style: bold; padding: 1 0 0 0; content-align: center top; align: center middle; text-align: center;}

    .qp-option-row   { padding: 0 0 0 0; align: center middle; content-align: center middle; text-align: center; }
    .qp-letter       { width: 3; text-style: bold; align: center middle; content-align: center middle; text-align: center; color: $accent; }
    .qp-empty        { color: $text-muted; padding: 2 0; }
    .correct-option { background: $success-lighten-2; }
    """

    # Avoid double empty render on startup
    quiz: Optional[Dict[str, Any]] = reactive(None, init=False)

    def set_quiz(self, quiz: Optional[Dict[str, Any]]) -> None:
        """Public API: call this to (re)render the preview."""
        self.quiz = quiz  # triggers watch_quiz

    # ---- reactive hook -----------------------------------------------------

    def watch_quiz(self, quiz: Optional[Dict[str, Any]]) -> None:
        logger.debug("QuizPreview.watch_quiz received quiz=%s", bool(quiz))
        self._render_quiz()

    # ---- lifecycle ---------------------------------------------------------

    def on_mount(self) -> None:
        logger.debug("QuizPreview.on_mount")
        self._render_quiz()

    # ---- render helpers ----------------------------------------------------

    def _render_quiz(self) -> None:
        # If we're not attached yet, schedule after the first layout pass.
        if not self.is_attached:
            self.call_after_refresh(self._render_quiz)
            return

        # Clear existing children
        self.remove_children()

        if not self.quiz:
            self.mount(Static("No quiz selected.", classes="qp-empty"))
            return

        title = self.quiz.get("title", "Untitled Quiz")
        questions: List[Dict[str, Any]] = self.quiz.get("questions", [])
        logger.debug("QuizPreview._render_quiz: %s (%d questions)", title, len(questions))

        # Header
        self.mount(
            Static(f"[b]{title}[/b]", classes="qp-title"),
            Static(f"{len(questions)} question{'s' if len(questions) != 1 else ''}", classes="qp-subtitle"),
            Rule(line_style="double"),
        )

        # Questions + options (append rows directly to the scroll)
        letters_cache = list(string.ascii_uppercase)
        for idx, q in enumerate(questions, 1):
            prompt = q.get("prompt", "(no prompt)")
            options: List[str] = q.get("options", [])
            correct_index: Optional[int] = q.get("correct_idx", None)
            logger.debug("QP: Q%d '%s' (opts=%d)", idx, prompt, len(options))

            # Prompt line
            self.mount(Static(f"{idx}. {prompt}", classes="qp-qprompt"))

            # Option rows (A., B., C., ...)
            if options:
                for i, text in enumerate(options):
                    letter = letters_cache[i] if i < len(letters_cache) else f"{i+1}"
                    c = "qp-option-row"
                    if correct_index is not None and i == correct_index:
                        c += " correct-option"
                    self.mount(
                        Horizontal(
                            Static(f"{letter}.", classes="qp-letter"),
                            Static(text, expand=True),
                            classes=c,
                        )
                    )
            else:
                # Placeholder if no options provided
                self.mount(
                    Horizontal(
                        Static("—", classes="qp-letter"),
                        Static("[dim]No options provided[/dim]", expand=True),
                        classes="qp-option-row",
                    )
                )

            # Separator after each question
            self.mount(Rule(line_style="double"))

        # Nudge layout once
        self.refresh(layout=True)
