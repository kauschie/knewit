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
from typing import List
import secrets
import random
import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))

from dataclasses import dataclass
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Input, TabbedContent, TabPane, DataTable, ListView, ListItem, Button, Log, Label, Digits
from textual.containers import Horizontal, Vertical, Container, VerticalScroll, HorizontalGroup, VerticalGroup, HorizontalScroll
from textual.app import App, ComposeResult
from textual import events, on, work
from rich.text import Text

from client.interface import HostInterface
from client.common import logger
from client.widgets.plot_widgets import AnswerHistogramPlot, PercentCorrectPlot
from client.widgets.quiz_selector import QuizSelector
from client.widgets.quiz_preview_log import QuizPreviewLog
from client.widgets.timedisplay import TimeDisplay
from client.widgets.basic_widgets import BorderedInputRandContainer, BorderedTwoInputContainer, PlayerCard, BorderedInputButtonContainer
from client.utils import _host_validate
from client.widgets.chat import RichLogChat
from client.widgets.quiz_creator import QuizCreator

THEME = "flexoki"
MAX_CHAT_MESSAGES = 200

logger.debug("host_ui.py starting...")

class MainScreen(Screen):
    """Host main screen."""

    CSS = """
    #main-container { 
        height: 100%; 
        width: 100%;
        margin: 0;
        padding: 0;
        # background: $background;
    }
    #left-column { 
        width: 6fr; 
        height: 1fr; 
        padding: 0; 
        margin: 0;
        outline: tall $panel;
        # content-align: center top;
    }

    #quiz-preview { 
        height: 4fr; 
        width: 100%;
        # background: red;
        content-align: center top;
    }
    
    #graphs-area { 
        height: 3fr;
        min-height: 10;
        width: 100%;
        # background: green; 
    }
    
    #graphs-area PlotextPlot {
        width:1fr;
        height: 1fr;
    }
        
    #session-controls-area { 
        height: 7%;  
        layout: grid;
        grid-gutter: 0 2;
        # margin: 0 2 0 2;
        background: $surface;
        min-height: 3;
    }
    
    #load-quiz {
        
    }
    
    .two-grid {
        grid-size: 2;
        grid-columns: 1fr 1fr;
        grid-gutter: 1;
        # margin: 0 3 0 3;
        # grid-gutter: 0 3;
    }
    
    .three-grid {
        grid-size: 3;
        grid-columns: 1fr 1fr 1fr;
        grid-gutter: 1;
        # grid-gutter: 0 2;
        # margin: 0 2 0 2;
    }

    # Buttons in session-controls-area fill equally
    #session-controls-area Button { 
        width: 100%;
        height: 100%;
        content-align: center middle;
        # outline: round $accent;
        min-height: 3;
    }
    
    #create-quiz {
        outline: round $accent;
        # color: $accent;
    }
    
    #load-quiz {
        outline: round $accent;
        # color: $accent;
    }
    
    #start-quiz {
        outline: round $accent;
        color: $success;
    }
    #next-question {
        outline: round $accent;
        color: $primary;
    }
    #end-question {
        outline: round $accent;
        color: $warning;
    }
    #stop-quiz {
        outline: round $accent;
        color: $error;
    }

    #timer-widget {
        height: 2;
        margin: 0;
        padding: 0;
        # content-align: right middle;
        # align: right middle;
    }
    
    #timer-label
    {
        content-align: right middle;
        width: 5fr;
    }
    #timer-display {
        content-align: center middle;
        width: 1fr;
    }
    

    #right-tabs {
        width: 4fr;
        height: 100%;
        # border: tall $panel;
        margin: 0 0;
        padding: 0 0;
        box-sizing: border-box;
        # border: tall red;
    }

    #leaderboard,
    #user-controls,
    #log,
    #chat {
        height: 1fr;
        width: 1fr;
    }

    #chat-list {
        height: 7fr;
        # overflow-x: hidden;
    }
    
    #chat-log { 
        height: 7fr;
        width: 1fr;
        # overflow-x: hidden;
    }
    #chat-panel {
        height: 7fr;
        width: 1fr;
        layout: vertical;
        padding: 1;
    }

    /* input row stays visible and un-clipped */
    #chat-input-row {
        box-sizing: border-box;
        layout: horizontal;
        height: 1fr;
        min-height: 3;
        align: center middle;
    }

    #chat-input {
        width: 1fr;
        height: 1fr;
        box-sizing: border-box;
        # outline: solid yellow;
    }

    #chat-send {
        width: 12;
        height: 1fr;
        margin-left: 1;
        box-sizing: border-box;
    }

    

    /* Let widgets fill their grid cells */
    .uc-name, .uc-kick, .uc-mute { width: 100%; }

    /* Optional cosmetics */
    .uc-name { text-align: center; height:1fr; }
    .uc-kick { outline: ascii $warning; height:1fr;}
    .uc-mute { outline: round $success; height:1fr;}

    .uc-row {
        layout: grid;
        grid-size: 3;                   /* 3 columns */
        grid-columns: 3fr 1fr 1fr;      /* 3/5, 1/5, 1/5 => ~75%, 12.5%, 12.5% */
        height: 3;
        width: 100%;
        align-vertical: middle;         /* center buttons/text vertically */
        # border: tall $accent;
        # padding: 1;
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
    
    #quiz-preview-container {
        width: 100%;
        height: 4fr;
        border: solid $accent;
        padding: 1;
    }
    
    """

    BINDINGS = [
        # ("a", "add_player", "Add player"),
        # ("r", "remove_player", "Remove player"),
        ("n", "next_round", "New round column"),  # demo: add a per-round column
        ("c", "demo_chat", "Append demo chat line"),   # demo: add chat text
        ("enter", "send_chat", "Send chat input"),
        ("e", "end_question", "End question"),  # demo: end question
        ("s", "stop_quiz", "Stop quiz"),  # demo: end quiz
    ]

    def __init__(self) -> None:
        super().__init__()
        # general
        self.players: list[dict] = []       # [{player_id, score, ping}]
        self.round_idx: int = 0             # track dynamic round columns
        
        
        # refs populated on_mount
        # general
        self.host_name: str | None = None
        
        # panel refs
        self.leaderboard: DataTable | None = None
        self.user_controls: ListView | None = None
        self.log_list: Log | None = None
        self.extra_cols: list[str] = []  # track dynamic round columns
        self.timer: TimeDisplay | None = None
        self.hist_plot: AnswerHistogramPlot | None = None
        self.pc_plot: PercentCorrectPlot | None = None
        
        # session controls
        self.session_controls_area: Horizontal | None = None
        self.create_quiz_btn: Button | None = None
        self.load_quiz_btn: Button | None = None
        self.start_btn: Button | None = None
        self.nq_btn: Button | None = None
        self.stop_quiz_btn: Button | None = None
        self.end_question_btn: Button | None = None
        
        # quiz refs
        self.selected_quiz: dict | None = None
        self.quiz_preview: QuizPreviewLog | None = None
        
        # chat refs
        # self.chat_feed: MarkdownChat | None = None
        self.chat_input: Input | None = None
        self.chat_send: Button | None = None
        self.round_active: bool = False
        self.chat_log: RichLogChat | None = None
        

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="<!> KnewIt Host UI Main <!>")
        with Horizontal(id="main-container"):
            with Vertical(id="left-column"):
                with HorizontalGroup(id="timer-widget"):
                    yield Static("Time Remaining", id="timer-label")
                    yield TimeDisplay(id="timer-display")
                with Vertical(id="quiz-preview-container"):
                    yield QuizPreviewLog(id="quiz-preview")
                    
                with Horizontal(id="session-controls-area", classes="two-grid"):
                    # state1: Lobby
                    yield Button("Create Quiz", id="create-quiz")
                    yield Button("Load Quiz", id="load-quiz")
                    
                    # state2: Ready (quiz loaded)
                    yield Button("Start Quiz", id="start-quiz", classes="hidden")
                    
                    # state3: active (quiz running)
                    yield Button("Next Question", id="next-question", classes="hidden")
                    yield Button("End Question", id="end-question", classes="hidden")
                    
                    # both state2 and 3 but want it at the end of the row
                    yield Button("Stop Quiz", id="stop-quiz", classes="hidden ")
                
                with Horizontal(id="graphs-area"):
                    yield AnswerHistogramPlot(id="answers-plot")
                    yield PercentCorrectPlot(id="percent-plot")

            with TabbedContent(initial="chat", id="right-tabs"):
                with TabPane("Leaderboard", id="leaderboard"):
                    # DataTable gives both vertical & horizontal scrolling
                    yield DataTable(id="leaderboard-area")
                with TabPane("User Controls", id="user-controls"):
                    # A scrollable list of rows; each row holds name + buttons
                    yield ListView(id="user-controls-area")
                with TabPane("Log", id="log"):
                    # Log widget trims to max_lines and auto-scrolls
                    yield Log(id="log_area", max_lines=50, highlight=False, auto_scroll=True)
                with TabPane("Chat", id="chat"):
                    # with Vertical(id="chat-panel"):
                    yield RichLogChat(id="chat-log", 
                                    max_lines=MAX_CHAT_MESSAGES, 
                                    markup=True, 
                                    auto_scroll=True, 
                                    highlight=False, 
                                    wrap=True,
                                    min_width=20)
                    with Horizontal(id="chat-input-row"):
                        yield Input(placeholder="Type message here... (Enter to send)", id="chat-input")
                        yield Button("Send", id="chat-send", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        # cache refs
        self.leaderboard = self.query_one("#leaderboard-area", DataTable)
        self.user_controls = self.query_one("#user-controls-area", ListView)
        self.log_list = self.query_one("#log_area", Log)
        self.chat_input = self.query_one("#chat-input", Input)
        self.chat_send = self.query_one("#chat-send", Button)
        self.chat_log   = self.query_one("#chat-log", RichLogChat)
        self.create_quiz_btn = self.query_one("#create-quiz", Button)
        self.load_quiz_btn = self.query_one("#load-quiz", Button)
        self.start_btn = self.query_one("#start-quiz", Button)
        self.nq_btn = self.query_one("#next-question", Button)
        self.end_question_btn = self.query_one("#end-question", Button)
        self.stop_quiz_btn = self.query_one("#stop-quiz", Button)
        self.session_controls_area = self.query_one("#session-controls-area", Horizontal)
        self.hist_plot = self.query_one("#answers-plot", AnswerHistogramPlot)
        self.pc_plot = self.query_one("#percent-plot", expect_type=PercentCorrectPlot)

        self.quiz_preview = self.query_one("#quiz-preview", QuizPreviewLog)
        # self.host_name = self.app.session.get("username", "Host") if self.app.session else "Host"
        self.host_name = self.app.session.username if self.app.session else "HostUnknown"
        self.timer = self.query_one("#timer-display", TimeDisplay)

        # Setup leaderboard columns
        assert self.leaderboard is not None
        self.leaderboard.cursor_type = "row"   # nicer selection
        self.leaderboard.add_columns("Ping", "Name", "Total")
        self.leaderboard.fixed_columns = 3  # keep base columns visible when scrolling
        self.theme = THEME          

        session = self.app.session  # or however you're storing it
        if session and session.pending_events:
            logger.debug(f"Processing {len(session.pending_events)} pending events on mount.")
            # run them in order
            for msg in list(session.pending_events):
                # no await here; schedule the async handler
                asyncio.create_task(session.on_event(msg))
            session.pending_events.clear()
    
    
    def on_show(self) -> None:
        """Focus chat input on screen show."""
        if self.app.session:
            self.title = f"Hosting as {self.app.session.username} | Session: {self.app.session.session_id}"
        if self.chat_input:
            self.set_focus(self.chat_input)
    
    # ---------- Leaderboard helpers ----------

    def _rebuild_leaderboard(self) -> None:
        if not self.leaderboard:
            return

        dt = self.leaderboard
        dt.clear(columns=True)

        # 1) Define columns
        base_labels = ["Ping", "Name", "Total"]
        round_labels = [f"R{i}" for i in range(1, self.round_idx + 1)]

        # 2) Add columns and capture keys (order matches labels)
        keys = dt.add_columns(*base_labels, *round_labels)
        ping_key, name_key, total_key, *round_keys = keys  # <-- keep these

        # 3) Add rows (use ints where appropriate so sort is numeric)
        for p in self.players:
            ping = int(p.get("latency_ms", 0)) if p.get("latency_ms") is not None else "-"
            name = p["player_id"]
            total = int(p.get("score", 0))
            is_muted = p.get("is_muted", False)
            rounds = [int(v) for v in p.get("round_scores", [])]

            row = [ping, name, total, *rounds]
            dt.add_row(*row)

        # 4) Sort by Total (desc). Use the column KEY, not the label string.
        dt.sort(total_key, reverse=True)


    def _rebuild_user_controls(self) -> None:
        try:
            lv = self.query_one("#user-controls-area", ListView)
        except Exception:
            return  # tab not mounted yet

        lv.clear()

        for p in self.players:
            # pid = p["player_id"]
            name = p["player_id"]

            row = Horizontal(
                            Label(name, classes="uc-name"),
                            Button("Kick", id=f"kick-{name}", classes="uc-kick"),
                            Button("Mute", id=f"mute-{name}", classes="uc-mute"),
                            classes="uc-row",
                        )

            lv.append(ListItem(row))


# --------- quiz internals ---------
    async def _initialize_quiz(self) -> None:
        if not self.selected_quiz:
            self.append_chat(user="System", msg="[red]No quiz data provided to initialize.")
            logger.error("No quiz data provided to initialize.")
        # self.selected_quiz = quiz # already set in on_button_pressed
        
        #1 setup preview panel
        if not self.quiz_preview:
            logger.error("Quiz preview panel not available to set quiz.")
            self.append_chat(user="System", msg="[red]Quiz preview panel not set.")
            return
        
        await self.app.session.send_load_quiz(self.selected_quiz)
        
        logger.debug(f"Setting quiz preview: quiz:{self.selected_quiz}")
        self.append_chat(user="System", msg=f"Quiz loaded: [b]{self.selected_quiz.get('title','(untitled)')}[/b]")
        self.quiz_preview.set_quiz(self.selected_quiz)
        self.quiz_preview.set_show_answers(False)
        
        #3 reset plots
        self.query_one("#percent-plot", PercentCorrectPlot).set_series([])
        labels = self._get_labels_for_question(0) or ["A", "B", "C", "D"]

        # self.query_one("#answers-plot", AnswerHistogramPlot).reset_question(labels)
        self.hist_plot.reset_question(labels)

        #4 enable start quiz and next buttons
        # self.toggle_buttons()
        self.set_button_state("READY")

    def update_lobby(self, players: list[dict]) -> None:
        """Update the lobby player list."""
        self.players = players
        self._rebuild_leaderboard()
        self._rebuild_user_controls()

    # ---------- Host Control Actions ----------
    
    def _get_labels_for_question(self, q_idx: int) -> list[str]:
        """Derive answer labels from the selected quiz and question index."""
        if not self.selected_quiz:
            return []
        questions = self.selected_quiz.get("questions", [])

        if not (0 <= q_idx < len(questions)):
            return []

        options = questions[q_idx].get("options", [])
        return [chr(65 + i) for i in range(len(options))]  # A, B, C, ...
    
    def start_quiz(self) -> None:
        """Prepare state for Q0 and show 'waiting for answers'."""
        if not self.selected_quiz:
            return
        self.append_chat(user=self.host_name, msg="Quiz started.")
        self._send_quiz_start()
        
        self.set_button_state("ACTIVE")

    def begin_question(self, q_idx: int, timer_duration: int | None = None) -> None:
        
        """Switch plots/UI to the given question."""
        if not self.selected_quiz:
            logger.debug("[HostUi] No selected quiz to begin question.")
            return
        # self.selected_quiz["questions"][q_idx]["options"]   

        self.round_active = True
        if self.timer:
            self.timer.start(timer_duration or 10)  # demo: 30 second timer
        
        self.round_idx = q_idx + 1  # for leaderboard columns

        if self.quiz_preview:
            self.quiz_preview.set_current_question(q_idx)
            self.quiz_preview.set_show_answers(False)
        
        logger.debug(f"[HostUi] Beginning question {q_idx}.")
        
        # Reset answer histogram
        labels = self._get_labels_for_question(q_idx)
        logger.debug(f"[HostUi] Question {q_idx} labels: {labels}")
        if self.hist_plot:
            self.hist_plot.reset_question(labels)
       
    def next_question(self) -> None:
        """Advance to the next question."""
        
        if not self.selected_quiz:
            return
        
        if self.round_idx >= len(self.selected_quiz.get("questions", [])):
            # no more questions
            self.append_chat(user=self.host_name, msg="No more questions remaining.")
            logger.debug("No more questions remaining.")
            return
            
        if not self.quiz_preview.show_answers:
            # end current question first
            self.end_question()
            self.timer.stop()
        
        self._send_next_question()

    def end_question(self) -> None:
        """Close the question: freeze histogram and append % correct."""
        logger.debug(f"Ending question. self.round_active = {self.round_active}")
        
        if not self.selected_quiz:
            return
        
        # send end question to server
        self._send_end_question()
    
    def show_correct_answer(self, correct_idx, updated_histogram) -> None:
        """ Called when question.results received from server. """
        self.round_active = False
        if self.timer:
            self.timer.stop()
            
        if self.quiz_preview:
            self.quiz_preview.set_show_answers(True)
        
        self.update_answer_histogram(updated_histogram)
        self.update_percent_correct(correct_idx, updated_histogram)
    
    def update_percent_correct(self, correct_idx, updated_histogram) -> None:
        percent_correct = self.calculate_percent_correct(correct_idx, updated_histogram)
        logger.debug(f"[Host] show_correct_answer(). Percent correct: {percent_correct}")
        self.pc_plot.set_series([*self.pc_plot.percents, percent_correct])
    
    def stop_quiz(self) -> None:
        """Stop the quiz prematurely."""
        if not self.selected_quiz:
            return
        msg = "Quiz stopped by host."
        self._send_chat_internal(msg)
        self._send_stop_quiz()
    
    
    def end_quiz(self, leaderboard: list[dict] | None = None) -> None:
        """Wrap up the quiz and show results."""
        msg = "Quiz ended."
        
        if leaderboard:
            top_winner = leaderboard[0]['name'] if leaderboard else "Nobody"
            msg += f" Winner: {top_winner}"
        self.append_chat(user=self.host_name, msg=msg)
        
        # show final results in quiz preview
        if self.quiz_preview:
            printed_tokens = []
            theme_vars = self.app.get_css_variables()
            accent = theme_vars.get("accent", "green")
            printed_tokens.append(Text("Quiz Finished!\n\n", style="bold"))
            
            # Title
            tmp = Text("Final Leaderboard")
            tmp.stylize(f"bold underline {accent}")
            printed_tokens.append(tmp)
            printed_tokens.append(Text(":\n\n"))

            if leaderboard:
                for i, p in enumerate(leaderboard[:5]):  # Show top 5 for host
                    rank_style = "bold yellow" if i == 0 else "bold"
                    printed_tokens.append(Text.from_markup(f"{i+1}. [{rank_style}]{p['name']}[/] - {p['score']} points\n"))
            else:
                printed_tokens.append(Text("No player data available."))

            logger.debug(f"[Host Ui] Final leaderboard printed in quiz preview.") 
            logger.debug(f"[Host Ui] Leaderboard data: {printed_tokens}")   
            final_msg = Text.assemble(*printed_tokens)
            
            self.quiz_preview.set_message(final_msg)
        
        self.selected_quiz = None
        self.set_button_state("LOBBY")

    def action_start_quiz(self) -> None:
        self.start_quiz()

    def action_next_round(self) -> None:      
        self.next_question()
        
    def action_end_question(self) -> None:
        self.end_question()
        
    def action_stop_quiz(self) -> None:
        self.stop_quiz()
        
    def action_send_chat(self) -> None:
        if self.chat_input and self.chat_input.has_focus:
            self._send_chat_from_input()
    
    # update histogram -> should be moved to widget as watcher?
    def update_answer_histogram(self, bins: List[int]) -> None:
        """Update the answer histogram with new bin counts."""
        if self.hist_plot:
            self.hist_plot.counts = tuple(bins)
    
    # calculate percent correct -> move to server eventually to keep clients thin
    def calculate_percent_correct(self, correct_idx, counts) -> float:
        """Demo method to calculate a random percent correct."""
        if not self.selected_quiz:
            return 0.0
        
        sum_responses = sum(counts)
        if sum_responses == 0:
            return 0.0
        
        if 0 <= correct_idx < len(counts):
            correct_count = counts[correct_idx]
            return (correct_count / sum_responses) * 100.0
        
        return 0.0        
    
    
    def append_chat(self, user: str, msg: str, priv: str | None = None) -> None:
        if user == "System":
            priv = "sys"
        elif user == self.host_name:
            priv = "host"
        if self.chat_log:
            self.chat_log.append_chat(user, msg, priv)
        else:
            logger.warning(f"[Host] Chat log not available. Message from {user}: {msg}")
  
    def show_system_message(self, text: str) -> None:
        self.chat_log.append_chat("System", text)
  
    def append_rainbow_chat(self, user: str, msg: str) -> None:
        if self.chat_log:
            self.chat_log.append_rainbow_chat(user, msg)
        else:
            logger.warning(f"[Host] Chat log not available. Message from {user}: {msg}")



    def on_input_submitted(self, e: Input.Submitted) -> None:
        if e.input.id == "chat-input":
            self._send_chat_from_input()
            
    def _send_chat_internal(self, txt: str) -> None:
        """Send chat message to server."""
        if self.app.session:
            asyncio.create_task(self.app.session.send_chat(txt))

    def _send_chat_from_input(self) -> None:
        if self.chat_input and (txt := self.chat_input.value.strip()):
            self.chat_input.value = ""
            # self.append_chat(user=self.host_name, msg=txt)
            asyncio.create_task(self.app.session.send_chat(txt))
            
    def _send_quiz_start(self) -> None:
        """Send quiz start event to server."""
        if self.app.session and self.selected_quiz:
            asyncio.create_task(self.app.session.send_start_quiz())
            
    def _send_next_question(self) -> None:
        """Send next question event to server."""
        if self.app.session and self.selected_quiz:
            asyncio.create_task(self.app.session.send_next_question())
            
    def _send_end_question(self) -> None:
        """Send end question event to server."""
        if self.app.session and self.selected_quiz:
            asyncio.create_task(self.app.session.send_end_question())
    
    def _send_stop_quiz(self) -> None:
        """Send stop quiz event to server."""
        if self.app.session and self.selected_quiz:
            asyncio.create_task(self.app.session.send_stop_quiz())  
    
    # ---------- Placeholder handlers for the user control buttons ----------
    @work
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "")
        if bid.startswith("kick-"):
            self.append_chat(user=self.host_name, msg=f"Kicked {bid.removeprefix('kick-')}")
        elif bid.startswith("mute-"):
            self.append_chat(user=self.host_name, msg=f"Toggled mute for {bid.removeprefix('mute-')}")
        elif bid.startswith("load-quiz"):
            self.selected_quiz = await self.app.push_screen_wait(QuizSelector())  # get data
            if not self.selected_quiz:
                self.append_chat(user="System", msg="Quiz loading cancelled.")
                return
            self.append_chat(user=self.host_name, msg=f"Loaded quiz: {self.selected_quiz['title']}")
            await self._initialize_quiz()
        elif bid == "chat-send":
            self._send_chat_from_input()
        elif bid == "start-quiz":
            self.start_quiz()
        elif bid == "stop-quiz":
            self.stop_quiz()
        elif bid == "next-question":
            if self.round_idx < 1: self.start_quiz()
            # elif self.round_idx < len(self.selected_quiz['questions']): self.next_question()
            # else: 
                # self.append_chat(user=self.host_name, msg="No more questions remaining.")
                # self.end_quiz()
            else:
                self.next_question() # server handles end of quiz
        elif bid == "end-question":
            self.end_question()
        elif bid.startswith("create-quiz"):
            quiz_data = await self.app.push_screen_wait(QuizCreator())
            if not quiz_data:
                self.append_chat(user=self.host_name, msg="Quiz creation cancelled.")
                return
            self.selected_quiz = quiz_data
            self.append_chat(user=self.host_name, msg=f"Created quiz: {self.selected_quiz['title']}")
            self._initialize_quiz()
    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tab.id == "user-controls":
            self._rebuild_user_controls()

    def toggle_buttons(self) -> None:
        """Toggle visibility of quiz control buttons for demo."""
        
        # toggle pre-quiz buttons
        self.create_quiz_btn.toggle_class("hidden")
        self.load_quiz_btn.toggle_class("hidden")
        self.start_btn.toggle_class("hidden")
        
        # toggle game in-progress buttons
        self.nq_btn.toggle_class("hidden")
        self.end_question_btn.toggle_class("hidden")
        self.stop_quiz_btn.toggle_class("hidden")
        
        # adjust grid layout
        self.session_controls_area.toggle_class("two-grid", "three-grid")

    def set_button_state(self, state: str) -> None:
        """
        Update visible buttons based on the current game state.
        States: 'LOBBY', 'READY', 'ACTIVE'
        """
        # 1. Grab all buttons
        btn_create = self.create_quiz_btn
        btn_load   = self.load_quiz_btn
        btn_start  = self.start_btn
        btn_stop   = self.stop_quiz_btn # "End Quiz"
        btn_next   = self.nq_btn
        btn_endq   = self.end_question_btn
        
        container = self.session_controls_area

        # 2. Reset all to hidden first
        for btn in [btn_create, btn_load, btn_start, btn_stop, btn_next, btn_endq]:
            btn.add_class("hidden")
        
        # 3. Apply state logic
        if state == "LOBBY":
            # [Create Quiz] [Load Quiz]
            btn_create.remove_class("hidden")
            btn_load.remove_class("hidden")
            
            container.remove_class("three-grid")
            container.add_class("two-grid")
            
        elif state == "READY":
            # [Start Quiz] [End Quiz]
            btn_start.remove_class("hidden")
            btn_stop.remove_class("hidden")
            
            container.remove_class("three-grid")
            container.add_class("two-grid")
            
        elif state == "ACTIVE":
            # [Next Question] [End Question] [End Quiz]
            btn_next.remove_class("hidden")
            btn_endq.remove_class("hidden")
            btn_stop.remove_class("hidden")
            
            container.remove_class("two-grid")
            container.add_class("three-grid")

class LoginScreen(Screen):
    """Screen for host to enter session details and login."""
    
    CSS = """
    #login-container {
        align: center middle;
        content-align: center middle;
    }
    
    BorderedInputButtonContainer, BorderedTwoInputContainer {
        border: round $accent;
        border_title_align: center;
        max-width: 60;
    }
    
    .hidden {
        display: none;
    }
    
    .error-message {
        color: red;
        text-align: center;
        margin-top: 2;
        max-width: 60;
    }
    
    """
    
    ready_event: asyncio.Event
    
    BINDINGS = [
        ("enter", "attempt_login", "Submit login"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="<!> KnewIt Host UI Login <!>")
        with Vertical(id="login-container"):
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
    async def action_attempt_login(self) -> None:
        # gather input values
        vals = self._host_get_values()
        logger.debug("Attempting login with values:")
        for k,v in vals.items():
            logger.debug(f"Login input: {k} = {v}")
        
        # perform validation
        ok, msg = _host_validate(vals)
        if not ok:
            logger.debug(f"validation failed: {msg}")
            self._show_error(msg)
            return
        
        # try to connect to server
        self.query_one(".error-message").add_class("hidden")
        
        logger.debug("calling _launch_session")
        success, msg = await self._launch_session(vals)
        
        if not success:
            self.title = "Failed to connect to server."
            self._show_error("Failed to connect to server.")
            logger.debug(f"[Host]launch session failed to connect: {msg}")
            return
        if success:
            logger.debug(f"[Host]launch session succeeded: {msg}")
            self.title = "Connected to server."
    
    async def _launch_session(self, vals: dict) -> tuple[bool, str]:
        # connect to server
        self.title = "Connecting to server..."
        if self.app.session is None:
            self.app.session = HostInterface.from_dict(vals.copy())
        else:
            logger.debug("[Host]Reusing existing HostInterface session.")
            # check if session id or username changed
            if (self.app.session.session_id != vals["session_id"] or
                self.app.session.username != vals["host_name"]):
                
                logger.debug("[Host]Session ID or username changed; disconnecting and updating session info.")
                await self.app.session.stop()
                
                self.app.session = HostInterface.from_dict(vals.copy())    
            else:
                logger.debug("[Host] Session ID and username unchanged; reusing existing session info.")
                self.app.session.set_from_dict(vals.copy())
        self.title = "Creating session..."
        try:
            if not await self.app.session.start():
                return False, "Session creation failed."
        except asyncio.TimeoutError:
            logger.error(f"[Host LoginScreen] Session creation timed out.")
            return False, "Session creation timed out."
        
        logger.debug(f"[Host LoginScreen] Session created successfully.")
        await self.app.session.send_create()
        return True, "Connected and session created."


    async def on_button_pressed(self, event: Button.Pressed) -> None:
        
        if event.button.id == "session-inputs-button":   # from BorderedInputButtonContainer(id="session-inputs")
            self.query_one("#session-inputs-input", Input).value = secrets.token_urlsafe(6)
        
        if event.button.id == "pw-inputs-button":   # from BorderedInputButtonContainer(id="pw-inputs")
            self.query_one("#pw-inputs-input", Input).value = secrets.token_urlsafe(8)
        
        if event.button.id == "host-inputs-button":   # from BorderedInputButtonContainer(id="host-inputs")
            await self.action_attempt_login()
            

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.action_attempt_login()

    # --- helpers ---
    def _host_get_values(self) -> dict:
        
        vals = {
            # "session_id": self.query_one("#session-inputs-input", Input).value.strip(),
            # "password":   self.query_one("#pw-inputs-input", Input).value.strip(),
            # "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip(),
            # "server_port": self.query_one("#server-inputs-input2", Input).value.strip(),
            # "host_name":  self.query_one("#host-inputs-input", Input).value.strip(),
            "app": self.app,
            "session_id": self.query_one("#session-inputs-input", Input).value.strip() or "demo",
            "password":   self.query_one("#pw-inputs-input", Input).value.strip(),
            # "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip() or "kauschcarz.ddns.net",
            "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip() or "0.0.0.0",
            "server_port": self.query_one("#server-inputs-input2", Input).value.strip() or "49000",
            "host_name":  self.query_one("#host-inputs-input", Input).value.strip() or "host",
        }
        vals["username"] = vals["host_name"]  # alias

        return vals

    def _show_error(self, msg: str) -> None:
        err = self.query_one(".error-message", Static)
        err.update(f"[b]* {msg} *[/b]")   # simple emphasis
        self.query_one(".error-message").remove_class("hidden")
        # you can also add a CSS class for styling/animation if you like


class HostUIApp(App):


    CSS = """
    Screen {
        # background: $background;
        }
    
    QuizCreator {
        width: 1fr;
        align: center middle;
        # content-align: center middle;
        border: double $accent;
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
        "quiz_selector": QuizSelector,
        "quiz_creator": QuizCreator,
    }
    
    SCREENS = {
        "main": MainScreen,
        "login": LoginScreen,
    }
    
    def __init__(self) -> None:
        super().__init__()
        self.session: HostInterface | None = None

    # Bindings / actions

    def action_toggle_dark(self) -> None:
        self.theme = THEME if self.theme != THEME else "textual-dark"

    def on_mount(self, event: events.Mount) -> None:  # type: ignore[override]
        # sample quiz
        self.theme = THEME
        
        self.push_screen("login")
        # self.switch_mode("main")
        
    # async def on_unmount(self) -> None:
    #     """Called when the UI is closing. Stop WS reconnect loop."""
    #     if self.session:
    #         await self.session.stop()

if __name__ == "__main__":
    HostUIApp().run()
