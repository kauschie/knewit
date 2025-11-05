"""
Standalone Textual playground for redesigning the host UI.

Run this locally while iterating on layout and styling. It uses sample data
and simple keyboard-driven interactions so you can refine the UI before
connecting event handlers to the real WebSocket logic in `host_tui.py`.

Usage:
    python knewit/client/host_ui_playground.py

Controls:
  - a : add a sample player
  - r : remove selected player
  - TAB / Shift+TAB : move focus between columns
  - q : quit

This file intentionally keeps networking out of the loop. It exposes small
methods (update_players, set_quiz_preview) you can later call from
`host_tui.py` or tests to drive the UI.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import List
from dataclasses import dataclass
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Input, TabbedContent, TabPane, DataTable, ListView, ListItem, Button, Log, Label, Digits
from textual.containers import Horizontal, Vertical, Container, VerticalScroll, HorizontalGroup, VerticalGroup, HorizontalScroll
from textual.message import Message
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.reactive import reactive
from textual import events, on, work
from textual_plotext import PlotextPlot
import secrets
import logging
from quiz_selector import QuizSelector, logger
from quiz_preview import QuizPreview
from rich.table import Table

THEME = "flexoki"

# logging.basicConfig(filename='logs/host_ui_playground.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
# logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.debug("Host UI Playground module loaded.")

# ---- shared model -----------------------------------------------------------
@dataclass
class SessionModel:
    session_id: str
    host_name: str
    server_ip: str
    server_port: int
    
    
class _BasePlot(PlotextPlot):
    _pending: bool = False
    
    def replot(self) -> None:
        if self._pending:
            return
        self._pending = True
        
        def _do():
            self._pending = False
            self._draw()
            self.refresh()
            
        # run after the *next* refresh/layout
        self.call_after_refresh(_do)
    
    # redraw on resize
    def on_resize(self) -> None:
        self.replot()
        
class AnswerHistogramPlot(_BasePlot):
    """Plot showing answer distribution histogram."""
    labels = reactive(tuple(), init=False) # e.g., ("A", "B", "C", "D", "E")
    counts = reactive(tuple(), init=False) # e.g., (5, 10, 3, 0, 2), same length as labels
    
    def on_mount(self) -> None:
        self.labels = tuple()
        self.counts = tuple()
        self.replot()
        
    def reset_question(self, labels: list[str]) -> None:
        self.labels = tuple(labels)
        self.counts = tuple(0 for _ in labels)
        
    def bump(self, idx: int) -> None:
        if 0 <= idx < len(self.counts):
            counts = list(self.counts)
            counts[idx] += 1
            self.counts = tuple(counts)

    def watch_labels(self, _old: tuple, new: tuple) -> None:
        self.replot()

    def watch_counts(self, _old: tuple, new: tuple) -> None:
        self.replot()

    def _draw(self) -> None:
        plt = self.plt
        plt.clear_data()
        plt.title("Current Question - Answers")
        plt.xlabel("Choice")
        plt.ylabel("Count")
        if not self.labels or not self.counts:
            return
        plt.bar(list(self.labels), list(self.counts))
        plt.ylim(0, max(self.counts) + 1)

class PercentCorrectPlot(_BasePlot):
    percents = reactive(tuple(), init=False) # e.g., (50.0, 75.0, 100.0), one per question

    def on_mount(self) -> None:
        self.percents = tuple()
        self.replot()
    
    # public API
    def append_result(self, percent_correct: float) -> None:
        p = max(0.0, min(100.0, percent_correct))
        self.percents = (*self.percents, p) # should trigger watch method
        
    def set_series(self, percents: list[float]) -> None:
        self.percents = tuple(max(0.0, min(100.0, float(p))) for p in percents)

    # watcher
    def watch_percents(self, _old, _new) -> None:
        self.replot()
    
    def _draw(self) -> None:
        plt = self.plt
        plt.clear_data()
        n = len(self.percents)
        xs = list(range(1, n + 1))
        if xs:
            plt.plot(xs, list(self.percents), marker="hd")
        plt.title("% Correct by Question")
        plt.xlabel("Question #")
        plt.ylabel("% Correct")
        plt.ylim(0, 100)

class BorderedInputButtonContainer(HorizontalGroup):
    """A Container with a border + border title."""

    def __init__(self, *, 
                 input_title: str,
                 input_placeholder: str | None = None,
                 button_title: str,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.input_title = input_title
        self.input_placeholder = input_placeholder
        self.button_title = button_title

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self.input_placeholder, id=f"{self.id}-input")
        yield Button(self.button_title, id=f"{self.id}-button", variant="primary")


    def on_mount(self) -> None:
        self.border_title = f"{self.input_title}"
        self.border_title_align = "center"
        self.border_title_style = "bold"
        in_container = self.query_one(f"#{self.id}-input", Input)
        btn = self.query_one(f"#{self.id}-button", Button)
        in_container.styles.width = "4fr"
        btn.styles.width = "1fr"
        # btn.styles.border = ("double", "blue") # this $accent var doesn't work unless it's in css?
    
class BorderedInputRandContainer(BorderedInputButtonContainer):
    def __init__(self, *, 
                 input_title: str,
                 input_placeholder: str | None = None,
                 **kwargs) -> None:
        super().__init__(input_title=input_title, 
                         input_placeholder=input_placeholder,
                         button_title="Random", 
                         **kwargs)

class BorderedTwoInputContainer(HorizontalGroup):
    """A Container with a border + border title."""
    
    def __init__(self, *, 
                 border_title: str,
                 input1_placeholder: str | None = None,
                 input2_placeholder: str | None = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = border_title
        self.input1_placeholder = input1_placeholder
        self.input2_placeholder = input2_placeholder


    def compose(self) -> ComposeResult:
        yield Input(placeholder=self.input1_placeholder, id=f"{self.id}-input1")
        yield Input(placeholder=self.input2_placeholder, id=f"{self.id}-input2")

    def on_mount(self) -> None:
        self.border_title = f"{self.border_title}"
        in1 = self.query_one(f"#{self.id}-input1", Input)
        in2 = self.query_one(f"#{self.id}-input2", Input)
        in1.styles.width = "4fr"
        in2.styles.width = "1fr"
        
class PlayerCard(Static):
    """Simple card displaying a player's name and status."""

    def __init__(self, player_id: str, name: str, *, classes: str | None = None) -> None:
        super().__init__(classes=(classes or "player-card"))
        self.player_id = player_id
        # Avoid clashing with Widget.name property; store as player_name
        self.player_name = name

    def render(self) -> str:
        return f"{self.player_name} ({self.player_id})"

class TimeDisplay(Digits):
    """A widget to display time remaining."""


import string
from typing import Any, Dict, List, Optional


# class QuizPreview(VerticalScroll):
#     """Scrollable preview of the selected quiz (title, questions, options)."""

#     # You can tweak spacing/fonts here without touching your screen CSS
#     DEFAULT_CSS = """
#     QuizPreview {
#         padding: 1 2;
#         background: $panel;
#         border: tall $background 80%;
#         height: 1fr;
#         content-align: left middle;
#     }

#     .qp-title {
#         padding: 0 0 1 0;
#     }

#     .qp-subtitle {
#         color: $text-muted;
#         padding-bottom: 1;
#     }

#     .qp-qblock {
#         padding: 1 0;
#         border-bottom: solid $surface 10%;
#     }

#     .qp-qprompt {
#         text-style: bold;
#         padding-bottom: 1;
#     }

#     .qp-option-row {
#         padding: 0;
#     }

#     .qp-letter {
#         width: 3;
#         text-style: bold;
#     }

#     .qp-empty {
#         color: $text-muted;
#         padding: 2 0;
#     }
#     """

#     quiz: Optional[Dict[str, Any]] = reactive(None)

#     def set_quiz(self, quiz: Optional[Dict[str, Any]]) -> None:
#         """Public API: call this to (re)render the preview."""
#         self.quiz = quiz  # triggers watch_quiz

#     # ---- reactive hook -----------------------------------------------------

#     def watch_quiz(self, quiz: Optional[Dict[str, Any]]) -> None:
#         self._render_quiz()

#     # ---- lifecycle ---------------------------------------------------------

#     def on_mount(self) -> None:
#         # Initial placeholder render
#         self._render_quiz()

#     # ---- render helpers ----------------------------------------------------

#     def _render_quiz(self) -> None:
#         self.remove_children()

#         if not self.quiz:
#             self.mount
#             self.mount(Static("No quiz selected.", classes="qp-empty"))
#             return

#         title = self.quiz.get("title", "Untitled Quiz")
#         questions: List[Dict[str, Any]] = self.quiz.get("questions", [])

#         # Header
#         self.mount(Static(f"[b]{title}[/b]", classes="qp-title"))
#         self.mount(
#             Static(
#                 f"{len(questions)} question{'s' if len(questions)!=1 else ''}",
#                 classes="qp-subtitle",
#             )
#         )

#         # Questions
#         for i, q in enumerate(questions, 1):
#             self._mount_question_block(i, q)

#         # Ensure layout updates once after mounting everything
#         self.refresh(layout=True)

#     def _mount_question_block(self, index: int, q: Dict[str, Any]) -> None:
#         """Create a single question block with its options."""

#         prompt = q.get("prompt", "(no prompt)")
#         options: List[str] = q.get("options", [])
#         letters = self._letters(len(options))

#         q_block = Vertical(classes="qp-qblock")

#         # Prompt
#         q_block.mount(
#             Static(f"{index}. {prompt}", classes="qp-qprompt")
#         )

#         # Options
#         for letter, text in zip(letters, options):
#             row = Horizontal(classes="qp-option-row")
#             row.mount(Static(f"{letter}.", classes="qp-letter"))
#             row.mount(Static(text, expand=True))
#             q_block.mount(row)

#         self.mount(q_block)

#     @staticmethod
#     def _letters(n: int) -> List[str]:
#         return list(string.ascii_uppercase[: max(0, n)])


class MainScreen(Screen):
    """Host main screen."""

    CSS = """
    #main-container { 
        height: 100%; 
        width: 100%;
        margin: 0;
        padding: 0;
        background: $background;
    }
    #left-column { 
        width: 3fr; 
        height: 1fr; 
        padding: 0; 
        margin: 0;
        border: tall $panel;
    }

    #quiz-preview { 
        height: 4fr; 
        # background: red;
        content-align: center middle;
    }
    
    #graphs-area { 
        height: 3fr;
        width: 100%;
        background: green; 
    }
    
    #graphs-area PlotextPlot {
        width:1fr;
        height: 1fr;
    }
        
    #session-controls-area { 
        height: 1fr;  
        layout: grid;
        grid-gutter: 0 2;
        margin: 0 2 0 2;
        background: $background;
    }
    
    #load-quiz {
        
    }
    
    .two-grid {
        grid-size: 2;
        grid-columns: 1fr 1fr;
        # margin: 0 3 0 3;
        # grid-gutter: 0 3;
    }
    
    .three-grid {
        grid-size: 3;
        grid-columns: 1fr 1fr 1fr;
        # grid-gutter: 0 2;
        # margin: 0 2 0 2;
    }

    # Buttons in session-controls-area fill equally
    #session-controls-area Button { 
        width: 100%;
        height: 100%;
        content-align: center middle;
        border: round $accent;
    }

    TimeDisplay {
        width: 100%;
        height: 100%;
        content-align: center middle;
        border: round $accent;
        text-align: center;
        # text-style: bold;
        background: $boost;
        }

    #right-tabs  { 
        width: 2fr; 
        height: 1fr; 
        padding: 1; 
        border: tall $panel; 
    }
    #leaderboard-area, #user-controls-area, #chat-area { height: 1fr; }

    /* Let widgets fill their grid cells */
    .uc-name, .uc-kick, .uc-mute { width: 100%; }

    /* Optional cosmetics */
    .uc-name { text-align: center; height:1fr;}
    .uc-kick { background: darkred;  color: white; }
    .uc-mute { background: goldenrod; color: black; }

    .uc-row {
        layout: grid;
        grid-size: 3;                   /* 3 columns */
        grid-columns: 3fr 1fr 1fr;      /* 3/5, 1/5, 1/5 => ~75%, 12.5%, 12.5% */
        height: 3;
        width: 100%;
        align-vertical: middle;         /* center buttons/text vertically */
    }
    
    Label {
        height: 1fr;
        content-align: center middle;
    }

    Button {
        content-align: center middle;
        width: 100%;
        height: 1fr;
    }
    
    .hidden {
        display: none;
    }
    
    """

    BINDINGS = [
        ("a", "add_player", "Add player"),
        ("r", "remove_player", "Remove player"),
        ("n", "next_round", "New round column"),  # demo: add a per-round column
        ("c", "demo_chat", "Append chat line"),   # demo: add chat text
    ]

    def __init__(self) -> None:
        super().__init__()
        self.players: list[dict] = []       # [{player_id, name, score, ping}]
        self.round_idx: int = 0             # track dynamic round columns

        # refs populated on_mount
        self.leaderboard: DataTable | None = None
        self.user_controls: ListView | None = None
        self.chat_log: Log | None = None
        self.extra_cols: list[str] = []  # track dynamic round columns
        self.create_quiz_btn: Button | None = None
        self.load_quiz_btn: Button | None = None
        self.start_btn: Button | None = None
        self.nq_btn: Button | None = None
        self.end_quiz_btn: Button | None = None
        self.selected_quiz: dict | None = None
        self.session_controls_area: Horizontal | None = None
        self.quiz_preview: QuizPreview | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="<!> KnewIt Host UI Main <!>")
        with Horizontal(id="main-container"):
            with Vertical(id="left-column"):
                yield QuizPreview(id="quiz-preview")
                with Horizontal(id="session-controls-area", classes="two-grid"):
                    yield Button("Create Quiz", id="create-quiz")
                    yield Button("Load Quiz", id="load-quiz")
                    yield Button("Start Quiz", id="start-quiz", classes="hidden")
                    yield Button("Next Question", id="next-question", classes="hidden")
                    yield Button("End Quiz", id="end-quiz", classes="hidden")
                with Horizontal(id="graphs-area"):
                    yield AnswerHistogramPlot(id="answers-plot")
                    yield PercentCorrectPlot(id="percent-plot")

            with TabbedContent(initial="leaderboard", id="right-tabs"):
                with TabPane("Leaderboard", id="leaderboard"):
                    # DataTable gives both vertical & horizontal scrolling
                    yield DataTable(id="leaderboard-area")
                with TabPane("User Controls", id="user-controls"):
                    # A scrollable list of rows; each row holds name + buttons
                    yield ListView(id="user-controls-area")
                with TabPane("Chat", id="chat"):
                    # Log widget trims to max_lines and auto-scrolls
                    yield Log(id="chat-area", max_lines=50, highlight=False, auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        # cache refs
        self.leaderboard = self.query_one("#leaderboard-area", DataTable)
        self.user_controls = self.query_one("#user-controls-area", ListView)
        self.chat_log = self.query_one("#chat-area", Log)
        self.create_quiz_btn = self.query_one("#create-quiz", Button)
        self.load_quiz_btn = self.query_one("#load-quiz", Button)
        self.start_btn = self.query_one("#start-quiz", Button)
        self.nq_btn = self.query_one("#next-question", Button)
        self.end_quiz_btn = self.query_one("#end-quiz", Button)
        self.session_controls_area = self.query_one("#session-controls-area", Horizontal)
        self.quiz_preview = self.query_one(QuizPreview)

        # Setup leaderboard columns
        assert self.leaderboard is not None
        self.leaderboard.cursor_type = "row"   # nicer selection
        self.leaderboard.add_columns("Ping", "Name", "Total")
        self.leaderboard.fixed_columns = 3  # keep base columns visible when scrolling
        self.theme = THEME          

        # Seed a few players for demo
        for _ in range(3):
            self.action_add_player()

        # Seed chat
        self.append_chat("System ready. Press [n] to add a round column; [c] to append chat.")

    # ---------- Leaderboard helpers ----------

    def _rebuild_leaderboard(self) -> None:
        if not self.leaderboard:
            return
        dt = self.leaderboard
        dt.clear(columns=True)
        
        # 1) Ensure base columns exist exactly once
        base_cols = ["Ping", "Name", "Total"]
        round_cols = [f"R{i}" for i in range(1, self.round_idx + 1)]
        dt.add_columns(*base_cols, *round_cols)


        # 4) Re-add rows from the model
        for p in self.players:
            row = [str(p.get("ping", "-")), p["name"], str(p.get("score", 0))]
            row.extend(str(v) for v in p.get("rounds", []))
            dt.add_row(*row)



    def _rebuild_user_controls(self) -> None:
        try:
            lv = self.query_one("#user-controls-area", ListView)
        except Exception:
            return  # tab not mounted yet

        lv.clear()

        for p in self.players:
            pid = p["player_id"]

            row = Container(
                            Label(p["name"], classes="uc-name"),
                            Button("Kick", id=f"kick-{pid}", classes="uc-kick"),
                            Button("Mute", id=f"mute-{pid}", classes="uc-mute"),
                            classes="uc-row",
                        )

            lv.append(ListItem(row))


# --------- quiz internals ---------
    def _initialize_quiz(self, quiz: dict) -> None:
        if not quiz:
            self.append_chat("[red]No quiz data provided to initialize.")
            logger.error("No quiz data provided to initialize.")
        self.selected_quiz = quiz
        
        #1 setup preview panel
        if self.quiz_preview:
            logger.debug(f"Setting quiz preview: quiz:{quiz}")
            self.quiz_preview.set_quiz(quiz)
        
        #2 reset round state + leaderboard columns
        self.round_idx = 0
        for p in self.players:
            p["score"] = 0
            p["rounds"] = []
        self._rebuild_leaderboard()
        
        #3 reset plots
        self.query_one("#percent-plot", PercentCorrectPlot).set_series([])
        default_labels = ["A", "B", "C", "D"] # change as needed to be the first values?
        self.query_one("#answers-plot", AnswerHistogramPlot).reset_question(default_labels)

        #4 enable start quiz and next buttons
        self.toggle_buttons()


    # ---------- Host Control Actions ----------
    
    def start_quiz(self) -> None:
        """Prepare state for Q0 and show 'waiting for answers'."""
        if not self.selected_quiz:
            return
        # If your quiz has options per question, set labels from question 0.
        labels = ["A", "B", "C", "D"]  # TODO: derive from self.selected_quiz
        self.query_one("#answers-plot", expect_type=AnswerHistogramPlot).reset_question(labels)
        # Optional: update a label like "Q 1 / N" here

    def begin_question(self, q_idx: int) -> None:
        """Switch plots/UI to the given question."""
        labels = ["A", "B", "C", "D"]  # TODO: derive from quiz[q_idx]
        self.query_one("#answers-plot", expect_type=AnswerHistogramPlot).reset_question(labels)
        # Also clear any per-question timers, badges, etc.

    def tally_answer(self, choice_index: int) -> None:
        """Increment histogram as answers arrive in real time."""
        answers_plot = self.query_one("#answers-plot", expect_type=AnswerHistogramPlot)
        if 0 <= choice_index < len(answers_plot.counts):
            new_counts = list(answers_plot.counts)
            new_counts[choice_index] += 1
            answers_plot.set_counts(new_counts)

    def end_question(self, q_idx: int, correct: bool, percent_correct: float) -> None:
        """Close the question: freeze histogram and append % correct."""
        pc_plot = self.query_one("#percent-plot", expect_type=PercentCorrectPlot)
        pc_plot.set_series([*pc_plot.percents, percent_correct])
        # Update leaderboard totals if you score per question here.
        self._rebuild_leaderboard()
    
    def end_quiz(self) -> None:
        """Wrap up the quiz."""
        self.append_chat("* Quiz ended.")
        self.toggle_buttons()




    # ---------- Actions ----------
    def action_add_player(self) -> None:
        pid = f"p{random.randint(1000, 9999)}"
        name = random.choice(["alice","bob","carol","dave","eve"]) + str(random.randint(1,9))
        self.players.append({"player_id": pid, "name": name, "ping": random.randint(20, 90), "score": 0, "rounds": []})
        self._rebuild_leaderboard()
        self._rebuild_user_controls()

    def action_remove_player(self) -> None:
        if self.players:
            self.players.pop()
            self._rebuild_leaderboard()
            self._rebuild_user_controls()


    def action_next_round(self) -> None:
        self.round_idx += 1
        for p in self.players:
            delta = random.randint(0, 10)
            p["score"] = p.get("score", 0) + delta
            p.setdefault("rounds", []).append(delta)
        self._rebuild_leaderboard()

    def action_demo_chat(self) -> None:
        self.append_chat(f"[{datetime.now().strftime('%H:%M:%S')}] Host: demo line")

    # ---------- Chat helper ----------
    def append_chat(self, text: str) -> None:
        if self.chat_log:
            self.chat_log.write('\n' + text)

    # ---------- Placeholder handlers for the user control buttons ----------
    @work
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "")
        if bid.startswith("kick-"):
            self.append_chat(f"* Kicked {bid.removeprefix('kick-')}")
        elif bid.startswith("mute-"):
            self.append_chat(f"* Toggled mute for {bid.removeprefix('mute-')}")
        elif bid.startswith("load-quiz"):
            self.selected_quiz = await self.app.push_screen_wait(QuizSelector())  # get data
            self.append_chat(f"* Loaded quiz: {self.selected_quiz['title']}")
            self._initialize_quiz(self.selected_quiz)
            # self.toggle_buttons()
        elif bid == "start-quiz":
            self.start_quiz()
        elif bid == "next-question":
            self.round_idx += 1
            self.begin_question(self.round_idx - 1)
        elif bid == "end-quiz":
            self.end_question
        elif bid.startswith("create-quiz"):
            self.append_chat("* Created new quiz selected (not implemented)")

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tab.id == "user-controls":
            self._rebuild_user_controls()

    def toggle_buttons(self) -> None:
        """Toggle visibility of quiz control buttons for demo."""
        
        # self.create_quiz_btn.toggle_class("hidden", "three-grid", "two-grid")
        # self.load_quiz_btn.toggle_class("hidden", "three-grid", "two-grid")
        # self.start_btn.toggle_class("hidden", "two-grid", "three-grid")
        # self.nq_btn.toggle_class("hidden", "two-grid", "three-grid")
        # self.end_quiz_btn.toggle_class("hidden", "two-grid", "three-grid")
        self.create_quiz_btn.toggle_class("hidden")
        self.load_quiz_btn.toggle_class("hidden")
        self.start_btn.toggle_class("hidden")
        self.nq_btn.toggle_class("hidden")
        self.end_quiz_btn.toggle_class("hidden")
        self.session_controls_area.toggle_class("two-grid", "three-grid")

class LoginScreen(Screen):
    """Screen for host to enter session details and login."""
    
    CSS = """
    BorderedInputButtonContainer {
        border: round $accent;
        border_title_align: center;
    }
    
    BorderedTwoInputContainer {
        border: round $accent;
        border_title_align: center;
    }

    # Left column: controls
    .controls {
      width: 28;
      padding: 1 1;
      border: tall $panel;
    }

    # Center column: player list
    .players-column {
      min-width: 40;
      padding: 1 1;
      border: tall $panel;
    }

    .player-card {
      padding: 0 1;
      height: 3;
      background: $boost;
      margin: 0 0 1 0;
    }

    /* Right column: quiz preview */
    .quiz-preview {
      width: 40;
      padding: 1 1;
      border: tall $panel;
    }
    
    .hidden {
        display: none;
    }
    
    .error-message {
        color: red;
        text-align: center;
        margin-top: 2;
    }
    
    """
    
    BINDINGS = [
        ("enter", "attempt_login", "Submit login"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="<!> KnewIt Host UI Login <!>")
        with Vertical():
            # yield Static("* Server Error Message Placeholder *", classes=[])
            yield BorderedInputRandContainer(input_title="Session ID", 
                                             input_placeholder="demo", 
                                             id="session-inputs")
            yield BorderedInputRandContainer(input_title="Session Password", 
                                             input_placeholder="Leave blank for no password", 
                                             id="pw-inputs")
            yield BorderedTwoInputContainer(border_title="Server IP",
                                            input1_placeholder="0.0.0.0",
                                            input2_placeholder="8000",
                                            id="server-inputs")
            yield BorderedInputButtonContainer(input_title="Login Details",
                                            input_placeholder="Host",
                                            button_title="Launch",
                                            id="host-inputs")    
            yield Static("* Server Error Message Placeholder *", classes="error-message hidden")
        yield Footer()
        
        # --- unify both triggers on one action ---
    def action_attempt_login(self) -> None:
        vals = self._get_values()
        ok, msg = self._validate(vals)
        if not ok:
            self._show_error(msg)
            return
        # success -> switch modes (or emit a custom Message if you prefer)
        self.query_one(".error-message").add_class("hidden")
        self.app.switch_mode("main")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        
        if event.button.id == "session-inputs-button":   # from BorderedInputButtonContainer(id="session-inputs")
            self.query_one("#session-inputs-input", Input).value = secrets.token_urlsafe(6)
        
        if event.button.id == "pw-inputs-button":   # from BorderedInputButtonContainer(id="pw-inputs")
            self.query_one("#pw-inputs-input", Input).value = secrets.token_urlsafe(8)
        
        if event.button.id == "host-inputs-button":   # from BorderedInputButtonContainer(id="host-inputs")
            self.action_attempt_login()
            

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Hitting Enter in any Input triggers attempt (you can gate by id if you want)
        self.action_attempt_login()

    # --- helpers ---
    def _get_values(self) -> dict:
        # Match how your containers assign child IDs:
        # BorderedInputButtonContainer => #{id}-input
        # BorderedTwoInputContainer   => #{id}-input1 / #{id}-input2
        return {
            "session_id": self.query_one("#session-inputs-input", Input).value.strip() or "demo",
            "password":   self.query_one("#pw-inputs-input", Input).value.strip(),
            "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip() or "0.0.0.0",
            "server_port": self.query_one("#server-inputs-input2", Input).value.strip() or "8000",
            "host_name":  self.query_one("#host-inputs-input", Input).value.strip() or "host",
        }

    def _validate(self, v: dict) -> tuple[bool, str]:
        missing = [k.replace("_", " ").title() for k in ("session_id","server_ip","server_port","host_name") if not v[k]]
        if missing:
            return False, f"Please fill: {', '.join(missing)}."
        # basic port check
        if not v["server_port"].isdigit() or not (0 < int(v["server_port"]) < 65536):
            return False, "Port must be an integer between 1 and 65535."
        # (optional) quick IP sanity check
        parts = v["server_ip"].split(".")
        if len(parts) != 4 or any(not p.isdigit() or not (0 <= int(p) <= 255) for p in parts):
            return False, "Server IP must look like A.B.C.D (0–255)."
        return True, ""

    def _show_error(self, msg: str) -> None:
        err = self.query_one(".error-message", Static)
        err.update(f"[b]* {msg} *[/b]")   # simple emphasis
        self.query_one(".error-message").remove_class("hidden")
        # you can also add a CSS class for styling/animation if you like


class HostUIPlayground(App):


    CSS = """
    Screen {
        background: $background;
        }
    """

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("tab", "focus_next", "Focus next"),
        ("shift+tab", "focus_previous", "Focus previous"),
        ("q", "quit", "Quit"),
    ]

    MODES = {
        "login": LoginScreen,
        "main": MainScreen,
        # "quiz_selector": QuizSelector
    }
    
    def __init__(self) -> None:
        super().__init__()
        self.players: List[dict] = []
        self.player_list_container: VerticalScroll | None = None


    # Small API points to be used later when wiring event handlers
    def update_players(self, players: List[dict]) -> None:
        """Replace the rendered player list with `players`.

        players: list of dicts with keys `player_id` and `name`.
        """
        # clear existing
        if not self.player_list_container:
            return
        self.player_list_container.remove_children()

        for p in players:
            card = PlayerCard(p["player_id"], p.get("name", "unnamed"))
            # mount directly into the scroll container
            self.player_list_container.mount(card)

    # Bindings / actions

    def action_toggle_dark(self) -> None:
        self.theme = THEME if self.theme != THEME else "nord-light"

    async def on_mount(self, event: events.Mount) -> None:  # type: ignore[override]
        # seed some players for the initial view
        self.players = [
            {"player_id": "p1001", "name": "mike"},
            {"player_id": "p1002", "name": "amy"},
        ]
        self.update_players(self.players)
        # sample quiz
        self.theme = THEME
        self.switch_mode("login")
        # self.switch_mode("main")

if __name__ == "__main__":
    HostUIPlayground().run()
