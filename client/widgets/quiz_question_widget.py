from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

from textual.widgets import Button, Static, Header, Footer, RichLog
from rich.text import Text
from textual.containers import Container, Horizontal
from textual.app import ComposeResult, App
from textual.reactive import reactive
from textual.widget import Widget


sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))
from client.common import logger
from server.quiz_types import Quiz, Question, StudentQuestion

from knewit.client.widgets.timedisplay import TimeDisplay


class QuizQuestionWidget(Widget):
    """Widget to display the current quiz question and answer options.

    Public API (for wiring to the server events):

        widget.show_question(
            question=question_dict,   # prompt/options from server
            index=3,                  # optional: 1-based question number
            total=10,                 # optional: total questions
            start_timer=True,         # start local timer on receipt
        )

        widget.clear_question()      # blank out between questions (if desired)
    """

    current_question: Optional[Dict[str, Any]] = reactive(None)
    current_index: Optional[int] = reactive(None)
    total_questions: Optional[int] = reactive(None)
    answered_option: Optional[int] = reactive(None)
    answered_time: Optional[float] = reactive(None)
    has_started: bool = reactive(False)

    def compose(self) -> ComposeResult:
        with Container(id="quiz-question-grid"):
            # Top row: timer
            with Horizontal(id="timer-widget"):
                yield Static("Time Remaining", id="timer-label")
                yield TimeDisplay(id="timer-display")

            # Middle: question text (RichLog)
            log = RichLog(
                id="question-log",
                wrap=True,
                markup=True,
                highlight=False,
                min_width=1,
            )
            # log.virtual_size = lambda: (log.size.width, len(log.lines) + 5)
            yield log

            # Bottom row: answer buttons
            yield Button("Option A", id="option-a")
            yield Button("Option B", id="option-b")
            yield Button("Option C", id="option-c")
            yield Button("Option D", id="option-d")

    # --- Convenience accessors ---

    @property
    def timer(self) -> TimeDisplay:
        return self.query_one("#timer-display", TimeDisplay)

    @property
    def log(self) -> RichLog:
        return self.query_one("#question-log", RichLog)
    
    def on_resize(self, event) -> None:
        if not self.has_started:
            self._render_start_screen()
        else:
            self._render_question_and_options()

        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle answer button presses."""
        
        if self.answered_option is not None:
            return  # already answered
        
        btn = event.button
        buttons = self._option_buttons()
        if btn not in buttons:
            return  # not one of our buttons
        
        # check if time has already passed
        if self.timer.remaining <= 0:
            log = self.log
            log.write(f"[bold red]Time's up![/bold red]")
            
            self.answered_option = -1  # mark as no answer
            self.answered_time = self.timer.duration
            logger.debug("Time has expired, cannot answer.")
            return
        
        
        
        answer_idx = buttons.index(btn)
        self.answered_option = answer_idx
        self.answered_time = self._stop_local_timer()
        logger.debug(f"User selected answer index: {answer_idx}")
        logger.debug(f"Time taken to answer: {self.answered_time:.2f} seconds.")
        # Highlight selected button
        for i, b in enumerate(buttons):
            if i == answer_idx:
                b.add_class("selected-option")
                # logger.debug(f"Button {b.id} marked as selected-option.")
            else:
                b.remove_class("selected-option")
                # logger.debug(f"select-option removed from Button {b.id}.")
        
    
    def show_correct(self, correct_idx: int) -> None:
        log = self.log
        if self.current_question is None or self.answered_option is None:
            return
        
        if self.answered_option == correct_idx:
            log.write(f"[bold green]Correct![/bold green]")
            log.add_class("correct")
            # logger.debug("User answered correctly, added correct class.")
        else:
            if self.answered_option == -1:
                log.write(f"[bold red]The answer was {chr(ord('A') + correct_idx)}[/bold red]")
            else:
                log.write(f"[bold red]Incorrect! The answer was {chr(ord('A') + correct_idx)}[/bold red]")
            log.add_class("incorrect")
            # logger.debug("User answered incorrectly, added incorrect class.")



    def _option_buttons(self) -> List[Button]:
        return [
            self.query_one("#option-a", Button),
            self.query_one("#option-b", Button),
            self.query_one("#option-c", Button),
            self.query_one("#option-d", Button),
        ]

    # --- Public API for host wiring ---


    # def show_question(
    #     self,
    #     question: Dict[str, Any],
    #     *,
    #     index: Optional[int] = None,
    #     total: Optional[int] = None,
    #     start_timer: bool = False,
    # ) -> None:

    def show_question(
        self,
        question: StudentQuestion,
        start_timer: bool = False,
    ) -> None:
       
        """
        Called by server when a new question is administered.

        `question` is expected to have at least:
            - "prompt": str
            - "options": list[str]
        """
        self.current_question = {"prompt": question.prompt, "options": question.options}
        self.current_index = question.index
        self.total_questions = question.total
        self.duration = question.timer

        self._render_question_and_options()

        if self.duration is not None:
            self._set_local_timer(self.duration)

        if start_timer:
            self._start_local_timer()
        self.has_started = True

    def end_question(self) -> None:
        """Handle end-of-question logic."""
        user_answer_time = self.answered_time
        logger.debug(f"Ending question. User answered in: {user_answer_time} seconds.")
        if not self.answered_option:
            logger.debug("User did not answer the question.")
            self.answered_time = self._stop_local_timer()
            self.answered_option = -1
    

    def clear_question(self) -> None:
        """Clear the question UI (e.g., between rounds)."""
        self.current_question = None
        self.current_index = None
        self.total_questions = None
        self.answered_option = None
        self.answered_time = None
        self.has_started = False

        self.log.clear()

        # remove background style
        if self.log.has_class("incorrect"):
            self.log.remove_class("incorrect")
        if self.log.has_class("correct"):
            self.log.remove_class("correct")

        # Disable & clear buttons
        for btn in self._option_buttons():
            btn.disabled = True
            btn.label = ""
            if btn.has_class("selected-option"):
                btn.remove_class("selected-option")

    # --- Reactive hook (if you ever set current_question directly) ---

    def watch_current_question(self, _new: Optional[Dict[str, Any]]) -> None:
        self._render_question_and_options()

    # --- Internal helpers ---
    


    def _render_start_screen(self, msg: str = "Waiting for Quiz to start...") -> None:
        """Render a start screen (before any question is shown)."""
        log = self.log
        log.clear()
        t_msg = Text(msg, justify="left", overflow="fold", no_wrap=False)
        theme_vars = self.app.get_css_variables()
        accent_color = theme_vars.get("accent", "pink")
        t_msg.stylize(f"bold underline {accent_color}")
        log.write(t_msg)
        

    def _render_question_and_options(self) -> None:
        """Render the current question into the RichLog and update buttons."""
        log = self.log
        log.clear()
        
        if not self.current_question:
            # If there's no question, blank buttons as well.
            for i, btn in enumerate(self._option_buttons()):
                btn.disabled = True
                btn.label = chr(ord("A") + i)
            return

        prompt: str = self.current_question.get("prompt", "")
        options: List[str] = list(self.current_question.get("options", []))

        # Header: Question 3/10, etc.
        if self.current_index is not None and self.total_questions is not None:
            header = f"Question {self.current_index}/{self.total_questions}"
        elif self.current_index is not None:
            header = f"Question {self.current_index}"
        else:
            header = "Question"

        rich_text = Text(f"{header}\n", justify="left", overflow="fold", no_wrap=False)
        theme_vars = self.app.get_css_variables()
        accent_color = theme_vars.get("accent", "pink")
        rich_text.stylize(f"bold underline {accent_color}")
        log.write(rich_text)
        log.write("")
        
        primary_color = theme_vars.get("primary", "cyan")
        rich_prompt = Text(f"{prompt}\n\n", justify="left", overflow="fold", no_wrap=False)
        rich_prompt.stylize(f"bold {primary_color}")
        log.write(rich_prompt)

        for i, opt in enumerate(options):
            label = chr(ord("A") + i)
            log.write(f"[b]{label}.[/b] {opt}")
        log.write("")  # extra blank line for breathing room

        # Update button labels & enable/disable
        buttons = self._option_buttons()
        for i, btn in enumerate(buttons):
            if i < len(options):
                label = chr(ord("A") + i)
                btn.label = f"{label}"
                btn.disabled = False
            else:
                btn.label = ""
                btn.disabled = True
        

    def _start_local_timer(self, duration: Optional[float] = None) -> None:
        """
        Local-only timer start.

        We assume TimeDisplay encapsulates all its own logic.
        We just tell it to start when the client receives the new question.
        Later, if you go server-authoritative, you can:
          - stop calling this, and/or
          - add a `set_remaining()` path driven by server ticks.
        """
        t = self.timer
        if hasattr(t, "start"):
            t.start(seconds = duration)
            
    def _set_local_timer(self, seconds: float) -> None:
        """
        Local-only timer set.

        Similar to _start_local_timer, this is a local-only convenience.
        """
        t = self.timer
        if hasattr(t, "reset"):
            t.reset(seconds)
            
    def _stop_local_timer(self) -> float:
        """
        Local-only timer stop.

        Similar to _start_local_timer, this is a local-only convenience.
        """
        t = self.timer
        if hasattr(t, "stop"):
            t.stop()
            return t.get_elapsed()
        return 0.0


class QuizQuestionApp(App):
    """A simple app to demonstrate the QuizQuestionWidget."""

    CSS = """
    Screen {
        height: 100%;
        width: 100%;
    }

    #quiz-question-grid {
        padding: 1;
        layout: grid;
        grid-size: 4;
        grid-columns: 1fr 1fr 1fr 1fr;
        grid-rows: 1fr 8fr 1fr;
        text-align: center;
        # border: solid red;
        height: 100%;
        width: 100%;
        grid-gutter: 1;
        background: $background;
    }

    #question-log {
        text-align: left;
        column-span: 4;
        height: 100%;
        width: 1fr;
        min-height: 4;
        padding-left: 5;
        padding-top: 3;
        background: $background;
        border: solid $accent;
        overflow: hidden;
    }

    #quiz-question-grid Button {
        width: 100%;
        height: 100%;
        background: $background;
        align: center bottom;
        outline: round $accent;
        min-width: 5;
    }

    #timer-widget {
        column-span: 4;
        width: 100%;
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        # grid-columns: 1fr 1fr;
        grid-columns: auto auto;
        align: center middle;
        # background: $panel;
    }

    #timer-label {
        height: 100%;
        column-span: 1;
        content-align: right middle;
        # background: blue;
    }

    #timer-display {
        height: 100%;
        column-span: 1;
        content-align: left middle;
        # background: red;
    }

    #quiz-question-grid Button.selected-option {
        background: $primary 30%;
        color: $text;
    }
    
    #question-log.incorrect {
        background: red 50%;
    }

    #question-log.correct {
        background: green 50%;
    }
    """

    BINDINGS = [("q", "quit", "Quit"),
                ("s", "start_timer", "Start Timer"),
                ("t", "stop_timer", "Stop Timer"),
                ("r", "reset_timer", "Reset Timer"),
                ("e", "resume_timer", "Resume Timer"),
                ("c", "check_answer", "Check Answer"),
                ("x", "start_screen", "Start Screen"),
               ]

    def compose(self) -> ComposeResult:
        yield Header()
        self.widget = QuizQuestionWidget()
        yield self.widget
        yield Footer()

    def on_mount(self) -> None:
        # Simple sample question for local testing
        sample_question = StudentQuestion.from_dict({
            "id": "b65d8791",
            "prompt": "What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?What is 2 + 2?",
            "options": ["3", "4", "5", "6"],
            "index": 1,
            "total": 2})
        self.widget.timer.reset(30.0)
        self.widget.show_question(sample_question, start_timer=False)

    def action_start_timer(self) -> None:
        self.widget._start_local_timer()
    
    def action_stop_timer(self) -> None:
        elapsed = self.widget._stop_local_timer()
        logger.debug(f"Timer stopped, elapsed time: {elapsed:.2f} seconds.")

    def action_reset_timer(self) -> None:
        self.widget._set_local_timer(30.0)
        logger.debug("Timer reset to 30.0 seconds.")
        self.refresh(repaint=True)
    
    def action_resume_timer(self) -> None:
        self.widget.timer.resume()
        logger.debug("Timer resumed.")
        
    def action_start_screen(self) -> None:
        quiz_name = "Sample Quiz"
        num_qs = 5
        self.widget._render_start_screen(
                f"Waiting for {num_qs} Question Quiz '{quiz_name}' to start... Waiting for {num_qs} Question Quiz '{quiz_name}' to start... Waiting for {num_qs} Question Quiz '{quiz_name}' to start... Waiting for {num_qs} Question Quiz '{quiz_name}' to start...")

    def action_check_answer(self) -> None:
        self.widget.show_correct(correct_idx=1)  # assume correct answer is index 1 for testing

if __name__ == "__main__":
    logger.debug("QuizQuestionWidget module loaded, testing widget.")
    QuizQuestionApp().run()
