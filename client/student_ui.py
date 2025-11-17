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
import asyncio
import ipaddress
import re

from typing import List
from dataclasses import dataclass
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Input, TabbedContent, TabPane, DataTable, ListView, ListItem, Button, Log, Label, Digits
from textual.containers import Horizontal, Vertical, Container, VerticalScroll, HorizontalGroup, VerticalGroup, HorizontalScroll
from textual.app import App, ComposeResult
from textual import events, on, work


import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))
from server.quiz_types import Quiz, StudentQuestion, Question


from knewit.client.widgets.basic_widgets import BorderedInputContainer, BorderedTwoInputContainer, PlayerCard, BorderedInputButtonContainer
from utils import _student_validate
from knewit.client.widgets.chat import RichLogChat
from knewit.client.widgets.quiz_question_widget import QuizQuestionWidget
from common import logger, SessionModel
from ws_client import WSClient

THEME = "flexoki"
MAX_CHAT_MESSAGES = 200


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
        width: 5fr; 
        height: 1fr; 
        padding: 0; 
        margin: 1 1 1 1;
        outline: tall $panel;
        align: center middle;
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
    }

    #timer-widget {
        column-span: 4;
        width: 100%;
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        grid-columns: 1fr 1fr;
        # background: $panel;
    }

    #timer-label {
        height: 100%;
        column-span: 1;
        content-align: right top;
        # background: blue;
    }

    #timer-display {
        height: 100%;
        column-span: 1;
        content-align: left top;
        # background: red;
    }

    #quiz-question-grid Button.selected-option {
        background: $primary 30%;
        color: $text;
    }
    
    #question-log.incorrect {
        background: $error 30%;
    }

    #question-log.correct {
        background: $success 30%;
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
    
    """

    BINDINGS = [
        ("a", "add_player", "Add player"),
        ("r", "remove_player", "Remove player"),
        ("c", "demo_chat", "Append demo chat line"),   # demo: add chat text
        ("enter", "send_chat", "Send chat input"),
        ("1", "start_quiz", "Start quiz"),  # demo: start quiz
        ("2", "end_question", "End question"),  # demo: end question
        ("3", "next_question", "Next Question"),  # demo: next round
        ("4", "end_quiz", "End quiz"),  # demo: end quiz
    ]

    def __init__(self) -> None:
        super().__init__()
        # general
        self.players: list[dict] = []       # [{player_id, name, score, ping}]
        self.round_idx: int = -1             # track dynamic round columns
        
        # refs populated on_mount
        # general
        self.username: str | None = None
        
        # panel refs
        self.leaderboard: DataTable | None = None
        self.log_list: Log | None = None
        self.extra_cols: list[str] = []  # track dynamic round columns
        
        self.quiz_question_widget: QuizQuestionWidget | None = None
        
        # chat refs
        # self.chat_feed: MarkdownChat | None = None
        self.chat_input: Input | None = None
        self.chat_send: Button | None = None
        self.chat_log: RichLogChat | None = None
        

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="<!> KnewIt Host UI Main <!>")
        with Horizontal(id="main-container"):
            with Vertical(id="left-column"):
                yield QuizQuestionWidget(id="quiz-question-widget")

            with TabbedContent(initial="chat", id="right-tabs"):
                with TabPane("Leaderboard", id="leaderboard"):
                    # DataTable gives both vertical & horizontal scrolling
                    yield DataTable(id="leaderboard-area")
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
        self.log_list = self.query_one("#log_area", Log)
        self.chat_input = self.query_one("#chat-input", Input)
        self.chat_send = self.query_one("#chat-send", Button)
        self.chat_log   = self.query_one("#chat-log", RichLogChat)
        self.quiz_question_widget = self.query_one("#quiz-question-widget", QuizQuestionWidget)
        self.username = self.app.login_info.get("username", "Host") if self.app.login_info else "Host"

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
        # self.chat_feed.append("System", "Ready. Press a to add a round column; e to append chat.", )
        self.append_chat("System", "Ready. Press a to add a round column; e to append chat.", "sys")
    
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
            ping = int(p.get("ping", 0)) if str(p.get("ping", "")).isdigit() else p.get("ping", "-")
            name = p["name"]
            total = int(p.get("score", 0))
            rounds = [int(v) for v in p.get("rounds", [])]

            row = [ping, name, total, *rounds]
            dt.add_row(*row)

        # 4) Sort by Total (desc). Use the column KEY, not the label string.
        dt.sort(total_key, reverse=True)

    ## Public API to update the quiz question widget

    def set_quiz_question(self, question: StudentQuestion) -> None:
        if self.quiz_question_widget:
            self.quiz_question_widget.show_question(question, start_timer=True, duration=5)

    def student_load_quiz(self) -> None:
        # check if quiz question is already going
        if self.quiz_question_widget and self.quiz_question_widget.timer.is_running():
            logger.debug("Quiz question is already running, stopping now.")
            self.quiz_question_widget.end_question()

        self.round_idx = 0
        if self.app.quiz is not None:
            self.quiz_question_widget._render_start_screen()

    def next_question(self) -> None:
        """Demo: advance to next question."""
        logger.debug("Advancing to next question from MainScreen.")
        if self.app.quiz is not None and self.quiz_question_widget:
            self.quiz_question_widget.clear_question()
            quiz_questions = self.app.quiz.questions
            if self.round_idx + 1 < len(quiz_questions):
                self.round_idx += 1
                sq = StudentQuestion.from_question(quiz_questions[self.round_idx])
                sq.index = self.round_idx
                sq.total = len(quiz_questions)
                self.set_quiz_question(sq)
                return

    def end_question(self) -> None:
        # logger.debug("Ending question from MainScreen.")
        if self.quiz_question_widget and self.app.quiz is not None:
            self.quiz_question_widget.end_question()
            user_answer_time = self.quiz_question_widget.answered_time
            # logger.debug(f"User answered in: {user_answer_time} seconds.")
            # logger.debug("Question ended.")
            # logger.debug(f"User answer was: " + str(self.quiz_question_widget.answered_option))
            # logger.debug(f"Time taken to answer: " + str(user_answer_time) + " seconds.")
            correct_option = self.app.quiz.questions[self.round_idx].correct_idx
            self.quiz_question_widget.show_correct(correct_option)
    
    def end_quiz(self) -> None:
        logger.debug("Ending quiz from MainScreen.")
        if self.quiz_question_widget:
            self.quiz_question_widget.clear_question()
            self.round_idx = 0
            logger.debug("Quiz ended.")
    # ---------- Actions ----------
    def action_add_player(self) -> None:
        pid = f"p{random.randint(1000, 9999)}"
        name = random.choice(["alice","bob","carol","dave","eve"]) + str(random.randint(1,9))
        self.players.append({"player_id": pid, "name": name, "ping": random.randint(20, 90), "score": 0, "rounds": []})
        self._rebuild_leaderboard()

    def action_remove_player(self) -> None:
        if self.players:
            self.players.pop()
            self._rebuild_leaderboard()

    def action_start_quiz(self) -> None:
        self.student_load_quiz()

    def action_next_question(self) -> None:
        self.next_question()

    def action_end_question(self) -> None:
        self.end_question()
    
    def action_end_quiz(self) -> None:
        self.end_quiz()

    def append_chat(self, user: str, msg: str, priv: str | None = None) -> None:
        if user == "System":
            priv = "sys"
        elif user == self.username:
            priv = "host"
        if self.chat_log:
            self.chat_log.append_chat(user, msg, priv)
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
        
        player_name_list = [p["name"] for p in self.players]
        player_name_list.append(self.username if self.username else "Host")
        name = random.choice(player_name_list) if player_name_list else "Player1"
        line = random.choice(list_of_random_msgs)
        self.append_chat(user=name, msg=line)

    def on_input_submitted(self, e: Input.Submitted) -> None:
        if e.input.id == "chat-input":
            self._send_chat_from_input()

    def _send_chat_from_input(self) -> None:
        if self.chat_input and (txt := self.chat_input.value.strip()):
            self.chat_input.value = ""
            self.append_chat(user=self.username, msg=txt)
    
    # ---------- Placeholder handlers for the user control buttons ----------
    @work
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "")
    
        if bid == "chat-send":
            self._send_chat_from_input()



class LoginScreen(Screen):
    """Screen for host to enter session details and login."""
    
    CSS = """
    #login-container {
        align: center middle;
        content-align: center middle;
    }
    
    
    BorderedInputContainer, BorderedTwoInputContainer, BorderedInputButtonContainer {
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
    
    BINDINGS = [
        ("enter", "attempt_login", "Submit login"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="<!> KnewIt Host UI Login <!>")
        with Vertical(id="login-container"):
            # yield Static("* Server Error Message Placeholder *", classes=[])
            yield BorderedInputContainer(border_title="Session ID",
                                            input_placeholder="demo",
                                            id="session-id")
            yield BorderedInputContainer(border_title="Session Password",
                                         input_placeholder="Leave blank for no password",
                                         id="pw-input")
            yield BorderedTwoInputContainer(border_title="Server IP",
                                            input1_placeholder="0.0.0.0",
                                            input2_placeholder="8000",
                                            id="server-inputs")
            yield BorderedInputButtonContainer(input_title="Username",
                                            input_placeholder="johndoe123",
                                            button_title="Launch",
                                            id="username-inputs") 
  
            yield Static("* Server Error Message Placeholder *", classes="error-message hidden")
        yield Footer()
        
        # --- unify both triggers on one action ---
    def action_attempt_login(self) -> None:
        vals = self._student_get_values()
        logger.debug("Attempting login with values:")
        for k,v in vals.items():
            logger.debug(f"Login input: {k} = {v}")
        
        ok, msg = _student_validate(vals)
        if not ok:
            self._show_error(msg)
            return
        self.app.login_info = vals.copy()  # store for later use in MainScreen
        self.query_one(".error-message").add_class("hidden")
        if not self._connect_to_server(vals):
            self._show_error("Failed to connect to server.")
            return
        # success -> switch modes (or emit a custom Message if you prefer)
        self.app.switch_mode("main")
        
    def _connect_to_server(self, vals: dict) -> bool:
        """Attempt to connect to server with given vals.
        setup connection stuff here
          - the logic needs to be moved over from host_tui_old.py and extended
                (including player information)

        Return True on success, False on failure.
        """
        url = f"https://{vals["server_ip"]}:{vals["server_port"]}/ws?player_id={vals["username"]}&is_host=false&session_id={vals["session_id"]}&password={vals["password"]}"
        
        # self.connection = WSClient(url, on_event=)
        return True  # placeholder for real connection logic

    def on_button_pressed(self, event: Button.Pressed) -> None:
        
        if event.button.id == "username-inputs-button":
            self.action_attempt_login()
            

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_attempt_login()

    # --- helpers ---
    def _student_get_values(self) -> dict:
        
        vals = {
            "session_id": self.query_one("#session-id-input", Input).value.strip() or "demo",
            "password":   self.query_one("#pw-input-input", Input).value.strip(),
            "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip() or "0.0.0.0",
            "server_port": self.query_one("#server-inputs-input2", Input).value.strip() or "8000",
            "username":  self.query_one("#username-inputs-input", Input).value.strip() or "johndoe123",
        }
        
        return vals


    def _show_error(self, msg: str) -> None:
        logger.debug("Showing login error: " + msg)
        err = self.query_one(".error-message", Static)
        err.update(f"[b]* {msg} *[/b]")   # simple emphasis
        self.query_one(".error-message").remove_class("hidden")
        # you can also add a CSS class for styling/animation if you like


class StudentUIPlayground(App):


    CSS = """
    Screen {
        # background: $background;
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
        self.login_info: dict = {}
        
        self.quiz: Quiz | None = None


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
        self.theme = THEME if self.theme != THEME else "textual-dark"

    async def on_mount(self, event: events.Mount) -> None:  # type: ignore[override]
        # seed some players for the initial view
        self.players = [
            {"player_id": "p1001", "name": "mike"},
            {"player_id": "p1002", "name": "amy"},
        ]
        self.update_players(self.players)
        # sample quiz
        
        self.theme = THEME
        
        self.quiz = Quiz.load_from_file("quizzes/abcd1234.json")
        
        logger.debug(f"Loaded sample quiz: {self.quiz}")
        self.switch_mode("login")
        
        # self.switch_mode("main")

if __name__ == "__main__":
    StudentUIPlayground().run()
