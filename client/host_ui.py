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
        outline: round $accent;
        min-height: 3;
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
        border: solid pink;
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
        ("s", "end_quiz", "End quiz"),  # demo: end quiz
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
        
        # session controls
        self.session_controls_area: Horizontal | None = None
        self.create_quiz_btn: Button | None = None
        self.load_quiz_btn: Button | None = None
        self.start_btn: Button | None = None
        self.nq_btn: Button | None = None
        self.end_quiz_btn: Button | None = None
        
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
                    yield Button("Create Quiz", id="create-quiz")
                    yield Button("Load Quiz", id="load-quiz")
                    yield Button("Start Quiz", id="start-quiz", classes="hidden")
                    yield Button("Next Question", id="next-question", classes="hidden")
                    yield Button("End Question", id="end-question", classes="hidden")
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
        self.end_quiz_btn = self.query_one("#end-question", Button)
        self.session_controls_area = self.query_one("#session-controls-area", Horizontal)
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
            ping = int(p.get("latency_ms", 0)) if str(p.get("latency_ms", "")).isdigit() else p.get("latency_ms", "-")
            name = p["player_id"]
            total = int(p.get("score", 0))
            is_muted = p.get("is_muted", False)
            rounds = [int(v) for v in p.get("rounds", [])]

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
    def _initialize_quiz(self) -> None:
        if not self.selected_quiz:
            self.append_chat(user=self.host_name, msg="[red]No quiz data provided to initialize.")
            logger.error("No quiz data provided to initialize.")
        # self.selected_quiz = quiz # already set in on_button_pressed
        
        #1 setup preview panel
        if self.quiz_preview:
            logger.debug(f"Setting quiz preview: quiz:{self.selected_quiz}")
            self.append_chat(user="Server", msg=f"Quiz loaded: [b]{self.selected_quiz.get('title','(untitled)')}[/b]")
            self.quiz_preview.set_quiz(self.selected_quiz)
            self.quiz_preview.set_show_answers(False)
            
        
        #2 reset round state + leaderboard columns
        self.round_idx = 0
        for p in self.players:
            p["score"] = 0
            p["rounds"] = []
        self._rebuild_leaderboard()
        
        #3 reset plots
        self.query_one("#percent-plot", PercentCorrectPlot).set_series([])
        labels = self._get_labels_for_question(0) or ["A", "B", "C", "D"]

        self.query_one("#answers-plot", AnswerHistogramPlot).reset_question(labels)

        #4 enable start quiz and next buttons
        self.toggle_buttons()


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
        self.round_idx = 1  # first question is index 0
        
        # If your quiz has options per question, set labels from question 0.
        labels = self._get_labels_for_question(self.round_idx - 1)
        # labels = ["A", "B", "C", "D"]  # TODO: derive from self.selected_quiz
        self.query_one("#answers-plot", expect_type=AnswerHistogramPlot).reset_question(labels)
        # Optional: update a label like "Q 1 / N" here
        # self.quiz_preview.set_question_label(f"Q {self.round_idx} / {len(self.selected_quiz.get('questions', []))}")
        self.begin_question(0)
        

    def begin_question(self, q_idx: int) -> None:
        """Switch plots/UI to the given question."""
        if not self.selected_quiz:
            return
        # self.selected_quiz["questions"][q_idx]["options"]   

        self.round_active = True
        if self.timer:
            self.timer.start(30)  # demo: 30 second timer
        
        self.quiz_preview.set_current_question(q_idx)
        self.quiz_preview.set_show_answers(False)
        logger.debug(f"Beginning question {q_idx}.")
        # logger.debug(f"Question options: {self.selected_quiz['questions'][q_idx]['options']}")

        
        # labels = ["A", "B", "C", "D"]  # TODO: derive from quiz[q_idx]
        labels = self._get_labels_for_question(q_idx)
        logger.debug(f"Question {q_idx} labels: {labels}")
        self.query_one("#answers-plot", expect_type=AnswerHistogramPlot).reset_question(labels)
        # Also clear any per-question timers, badges, etc.
        
        self.simulate_responses()
       
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
        
        self.round_idx += 1
        self.begin_question(self.round_idx - 1) 
        
    def simulate_responses(self) -> None:
        """Demo method to simulate random answers arriving over time."""
        async def _sim():
            for _ in range(len(self.players)):
                await asyncio.sleep(random.uniform(0.1, 0.5))
                choice = random.randint(0, 3)
                self.tally_answer(choice)
        asyncio.create_task(_sim())     
        

    def tally_answer(self, choice_index: int) -> None:
        """Increment histogram as answers arrive in real time."""
        answers_plot = self.query_one("#answers-plot", expect_type=AnswerHistogramPlot)
        if 0 <= choice_index < len(answers_plot.counts):
            answers_plot.bump(choice_index)

    def end_question(self) -> None:
        """Close the question: freeze histogram and append % correct."""
        logger.debug(f"Ending question. self.round_active = {self.round_active}")
        
        if not self.selected_quiz:
            return
        if self.round_idx < 1:
            return  # no question in progress
        if not self.round_active:
            return  # question already ended
        self.timer.stop()
        self.round_active = False
        # update leaderboard
        for p in self.players:
            delta = random.randint(0, 10)
            p["score"] = p.get("score", 0) + delta
            p.setdefault("rounds", []).append(delta)
        self._rebuild_leaderboard()
        
        # update percent correct plot
        percent_correct = self.calculate_percent_correct()
        # highlight correct answer in preview
        logger.debug(f"Ending question. Percent correct: {percent_correct}")
        self.quiz_preview.set_show_answers(True)
        
        pc_plot = self.query_one("#percent-plot", expect_type=PercentCorrectPlot)
        pc_plot.set_series([*pc_plot.percents, percent_correct])
        # Update leaderboard totals if you score per question here.
    
    def end_quiz(self) -> None:
        """Wrap up the quiz."""
        self.append_chat(user=self.host_name, msg="Quiz ended.")
        self.selected_quiz = None
        self.quiz_preview.set_quiz(None)
        self.toggle_buttons()

    # ---------- Actions ----------
    # def action_add_player(self) -> None:
        # needs to be a function to create a player
        # see if they already existed and were disconnected
            # if so -> reinstate
            # if not -> create new player
        
        # pid = f"p{random.randint(1000, 9999)}"
        # name = random.choice(["alice","bob","carol","dave","eve"]) + str(random.randint(1,9))
        # self.players.append({"player_id": name, "ping": random.randint(20, 90), "score": 0, "rounds": []})
        # self._rebuild_leaderboard()
        # self._rebuild_user_controls()

    # def action_remove_player(self) -> None:
    #     if self.players:
    #         self.players.pop()
    #         self._rebuild_leaderboard()
    #         self._rebuild_user_controls()

    def action_start_quiz(self) -> None:
        self.start_quiz()

    def action_next_round(self) -> None:      
        self.next_question()
        
    def action_end_question(self) -> None:
        self.end_question()
        
    def calculate_percent_correct(self) -> float:
        """Demo method to calculate a random percent correct."""
        if not self.selected_quiz:
            return 0.0
        
        correct_index = self.quiz_preview.get_correct_answer_index()
        if correct_index is None:
            return 0.0
        responses = self.query_one("#answers-plot", expect_type=AnswerHistogramPlot).counts
        sum_responses = sum(responses)
        if sum_responses == 0:
            return 0.0
        num_correct = responses[correct_index]
        percent_correct = (num_correct / sum_responses) * 100.0
        return percent_correct        
    
    def action_end_quiz(self) -> None:
        self.end_quiz()

    def append_chat(self, user: str, msg: str, priv: str | None = None) -> None:
        if user == "System":
            priv = "sys"
        elif user == self.host_name:
            priv = "host"
        if self.chat_log:
            self.chat_log.append_chat(user, msg, priv)
        else:
            logger.warning(f"[Host] Chat log not available. Message from {user}: {msg}")
            # self.chat_log.refresh()
            # self.chat_log.write(msg)
            
        # if self.chat_feed:
        #     self.chat_feed.append(user, msg)

    def action_send_chat(self) -> None:
        if self.chat_input and self.chat_input.has_focus:
            self._send_chat_from_input()

    def action_demo_chat(self) -> None:
        list_of_random_msgs = [
            "Hello everyone!",
            "How's it going?",
            "This quiz is fun!",
            "I think I know the answer.",
            "Can we have a break?",
            "What's the next question?",
            "Good luck to all!",
            "I'm ready for the challenge.",
            "That was a tough one.",
            "Can't wait for the results!"
        ]
        
        player_name_list = [p["player_id"] for p in self.players]
        player_name_list.append(self.host_name if self.host_name else "Host")
        name = random.choice(player_name_list) if player_name_list else "Player1"
        line = random.choice(list_of_random_msgs)
        self.append_chat(user=name, msg=line)

    def on_input_submitted(self, e: Input.Submitted) -> None:
        if e.input.id == "chat-input":
            self._send_chat_from_input()

    def _send_chat_from_input(self) -> None:
        if self.chat_input and (txt := self.chat_input.value.strip()):
            self.chat_input.value = ""
            # self.append_chat(user=self.host_name, msg=txt)
            asyncio.create_task(self.app.session.send_chat(txt))
    
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
                self.append_chat(user=self.host_name, msg="Quiz loading cancelled.")
                return
            self.append_chat(user=self.host_name, msg=f"Loaded quiz: {self.selected_quiz['title']}")
            self._initialize_quiz()
        elif bid == "chat-send":
            self._send_chat_from_input()
        elif bid == "start-quiz":
            self.start_quiz()
        elif bid == "next-question":
            if self.round_idx < 1: self.start_quiz()
            elif self.round_idx < len(self.selected_quiz['questions']): self.next_question()
            else: 
                self.append_chat(user=self.host_name, msg="No more questions remaining.")
                self.end_quiz()
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
        
        self.create_quiz_btn.toggle_class("hidden")
        self.load_quiz_btn.toggle_class("hidden")
        self.start_btn.toggle_class("hidden")
        self.nq_btn.toggle_class("hidden")
        self.end_quiz_btn.toggle_class("hidden")
        self.session_controls_area.toggle_class("two-grid", "three-grid")

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
            "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip() or "kauschcarz.ddns.net",
            # "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip() or "0.0.0.0",
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
