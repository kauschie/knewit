"""
Student TUI for KnewIt.
Handles the main game flow, logging, and UI rendering for the participant.
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
import logging

# Add parent folders to path if running directly
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))

from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Input, DataTable, Button
from textual.message import Message
from textual.containers import Horizontal, Vertical, Container
from textual.app import App, ComposeResult
from textual import events, work
from rich.text import Text

from server.quiz_types import StudentQuestion, Quiz
from client.widgets.basic_widgets import BorderedInputContainer, BorderedTwoInputContainer, BorderedInputButtonContainer
from client.utils import _student_validate
from client.widgets.chat import RichLogChat
from client.widgets.quiz_question_widget import QuizQuestionWidget
from client.interface import StudentInterface
from client.common import logger
from client.session_log import SessionLogger, load_latest_incomplete_history

THEME = "flexoki"
MAX_CHAT_MESSAGES = 200
LABELS = ["A", "B", "C", "D"]


class TitleUpdate(Message):
    def __init__(self, new_title: str) -> None:
        self.new_title = new_title
        super().__init__()


class MainScreen(Screen):
    """Student main screen."""

    # --- RESTORED ORIGINAL CSS ---
    CSS = """
    #main-container { 
        layout: grid;
        grid-size: 2 2;
        grid-rows: 7fr 3fr;
        grid-columns: 6fr 4fr;
        grid-gutter: 0 0;
        height: 100%; 
        width: 100%;
        margin: 0;
        padding: 0;
        # background: $background;
    }
    # #left-column { 
    #     background: $background;
    #     width: 100%; 
    #     height: 100%; 
    #     padding: 0; 
    #     # margin: 1 1 1 1;
    #     outline: round green;
    #     align: center middle;
    # }

    #quiz-question-grid {
        padding: 1;
        layout: grid;
        grid-size: 4;
        grid-columns: 1fr 1fr 1fr 1fr;
        grid-rows: auto 8fr 3;
        text-align: center;
        align: center middle;
        # border: solid red;
        height: 100%;
        width: 100%;
        grid-gutter: 0 1;
        background: $background;
        margin: 0;
        padding: 0;
    }

    #quiz-question-widget {
        
        height: 100%;
        width: 100%;
        border: round $accent;
        background: $background;
    }

    #question-log {
        text-align: left;
        column-span: 4;
        height: 100%;
        width: 1fr;
        min-height: 4;
        padding-left: 2;
        padding-top: 1;
        background: $background;
        border: round $accent;
        overflow: hidden;
    }

    #quiz-question-grid Button {
        width: 100%;
        # height: 100%;
        background: $background;
        align: center bottom;
        outline: round $accent;
        height: 10;
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
        # margin: 1;
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
        background: $error 30%;
    }

    #question-log.correct {
        background: $success 30%;
    }

    #right-tabs {
        width: 4fr;
        height: 100%;
        # border: tall $panel;
        # margin: 0 0;
        padding: 1 1;
        box-sizing: border-box;
        outline: round $accent;
    }

    #leaderboard {
        height: 1fr;
        width: 1fr;
        padding: 2;
        border: round $accent;
        border-title-align: center;
        background: $background;
    }

    #chat-list {
        height: 7fr;
        # overflow-x: hidden;
    }
    
    #chat-log { 
        background: $background;
        height: 7fr;
        width: 100%;
        # overflow-x: hidden;
    }
    #chat {
        background: $background;
        # height: 7fr;
        column-span: 2;
        width: 100%;
        layout: vertical;
        padding: 0;
        margin: 0;
        border: round $accent;
        border-title-align: center;
    }

    /* input row stays visible and un-clipped */
    #chat-input-row {
        background: $background;
        box-sizing: border-box;
        layout: grid;
        grid-size: 2;
        grid-columns: 8fr 1fr;
        height: 3;
        min-height: 3;
        align: center middle;
    }

    #chat-input {
        # width: 1fr;
        height: 100%;
        padding: 0;
        margin: 0;
        padding-left: 2;
        background: $background;
        box-sizing: border-box;
        outline: round $primary;
    }

    #chat-send {
        # width: 8;
        height: 100%;
        # margin-left: 1;
        box-sizing: border-box;
        border: double $primary;
        background: $background;
        outline: round $primary;
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
        background: $background;
    }
    
    .hidden {
        display: none;
    }
    
    """

    TITLE = "KnewIt Student UI"
    SUB_TITLE = "Demo Session"

    BINDINGS = [
        ("enter", "send_chat", "Send chat input"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.players: list[dict] = []
        self.round_idx: int = -1
        
        self.leaderboard: DataTable | None = None
        # self.log_list: Log | None = None
        self.chat_input: Input | None = None
        self.chat_send: Button | None = None
        self.chat_log: RichLogChat | None = None
        self.quiz_question_widget: QuizQuestionWidget | None = None
        
        self.username: str = "Unknown"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="<!> KnewIt Student UI Main <!>")
        with Container(id="main-container"):
            # with Vertical(id="left-column"):
            yield QuizQuestionWidget(id="quiz-question-widget")

            # with TabbedContent(initial="chat", id="right-tabs"):
            with Container(id="leaderboard"):
                yield DataTable(id="leaderboard-area")
                # with TabPane("Log", id="log"):
                #     yield Log(id="log_area", max_lines=50, highlight=False, auto_scroll=True)
            with Container(id="chat"):
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
        # self.log_list = self.query_one("#log_area", Log)
        self.chat_input = self.query_one("#chat-input", Input)
        self.chat_send = self.query_one("#chat-send", Button)
        self.chat_log   = self.query_one("#chat-log", RichLogChat)
        self.quiz_question_widget = self.query_one("#quiz-question-widget", QuizQuestionWidget)
        
        if self.app.session:
            self.username = self.app.session.username

        # Setup leaderboard columns
        assert self.leaderboard is not None
        self.leaderboard.cursor_type = "row"   # nicer selection
        self.leaderboard.add_columns("Ping", "Name", "Total")
        self.leaderboard.fixed_columns = 3  # keep base columns visible when scrolling
        self.theme = THEME     
        
        self.chat_container = self.query_one("#chat", Container)
        self.chat_container.border_title = "Chat"
        self.leaderboard_container = self.query_one("#leaderboard", Container)
        self.leaderboard_container.border_title = "Leaderboard"

        session = self.app.session
        if session and session.pending_events:
            # run them in order
            for msg in list(session.pending_events):
                asyncio.create_task(session.on_event(msg))
            session.pending_events.clear()
    
    # ---------- Logic Hooks (with Logging) ----------

    def update_lobby(self, players: list[dict]) -> None:
        """Update the lobby player list."""
        self.players = players
        self._rebuild_leaderboard()

    def student_load_quiz(self, quiz_title, num_questions) -> None:
        # check if quiz question is already going
        if self.quiz_question_widget and self.quiz_question_widget.timer.is_running():
            logger.debug("[Student UI] Quiz question is already running, stopping now.")
            self.quiz_question_widget.end_question()

        self.round_idx = 0
        if self.quiz_question_widget:
            self.quiz_question_widget._render_start_screen(
                f"Waiting for {num_questions} Question Quiz '{quiz_title}' to start...")
        else:
            logger.warning("[Student UI] Quiz question widget not available to load quiz.")

    def next_question(self, sq: StudentQuestion) -> None:
        """Called when new question received."""
        logger.debug("[Student UI] next_question called.")
        if self.quiz_question_widget:
            self.quiz_question_widget.clear_question()
            self.round_idx = sq.index + 1
            self.set_quiz_question(sq)
            
            # [LOGGING] Question Received
            if hasattr(self.app, "session_logger") and self.app.session_logger:
                self.app.session_logger.log_question_received(
                    q_index=sq.index,
                    question_id=sq.id,
                    title="Quiz Question",
                    text=sq.prompt,
                    options=sq.options
                )
        else:
            logger.warning("[Student UI] Quiz widget missing for next_question")

    def set_quiz_question(self, question: StudentQuestion) -> None:
        if self.quiz_question_widget:
            self.quiz_question_widget.show_question(question, start_timer=True)

    def end_question(self, correct_option: int) -> None:
        """Reveal correct answer."""
        if self.quiz_question_widget:
            self.quiz_question_widget.end_question()
            self.quiz_question_widget.show_correct(correct_option)
            
            # [LOGGING] Answer Received
            if hasattr(self.app, "session_logger") and self.app.session_logger:
                val = LABELS[correct_option] if 0 <= correct_option < len(LABELS) else "?"
                self.app.session_logger.log_answer_received(
                    q_index=self.round_idx - 1, # 0-based
                    correct_index=correct_option,
                    correct_value=val
                )
        else:
            logger.warning("[Student UI] Quiz question widget not available to end question.")
    
    def end_quiz(self, leaderboard: list[dict]) -> None:
        logger.debug("[Student UI] end_quiz called.")
        
        if self.quiz_question_widget:
            self.quiz_question_widget.clear_question()
            if leaderboard:
                my_score = next((p['score'] for p in leaderboard if p['name'] == self.username), 0)
                rank = next((i+1 for i, p in enumerate(leaderboard) if p['name'] == self.username), len(leaderboard))
                
                printed_tokens = []
                theme_vars = self.app.get_css_variables()
                accent = theme_vars.get("accent", "green")
                
                printed_tokens.append(Text("Quiz Finished!\n\n "))
                
                tmp = Text("Your Score")
                tmp.stylize(f"bold underline {accent}")
                printed_tokens.append(tmp)
                printed_tokens.append(Text.from_markup(f": [b]{my_score}[/b]\n "))
                
                tmp = Text("Your Rank")
                tmp.stylize(f"bold underline {accent}")
                printed_tokens.append(tmp)
                printed_tokens.append(Text.from_markup(f": [b]{rank}[/b] out of [b]{len(leaderboard)}[/b]\n\n "))
                
                tmp = Text("Top Players")
                tmp.stylize(f"bold underline {accent}")
                printed_tokens.append(tmp)
                printed_tokens.append(Text(":\n"))
                
                for i, p in enumerate(leaderboard[:3]):
                    printed_tokens.append(Text.from_markup(f"{i+1}. [b]{p['name']}[/b] - {p['score']} points\n"))
                
                msg = Text.assemble(*printed_tokens)
                self.quiz_question_widget._render_start_screen(msg)
            else:
                self.quiz_question_widget._render_start_screen("Quiz Finished! No leaderboard data available.")
        else:
            logger.warning("[Student UI] Quiz question widget not available to end quiz.")
            
        self.round_idx = 0

    # ---------- Chat & Leaderboard Internals ----------

    def _rebuild_leaderboard(self) -> None:
        if not self.leaderboard:
            return

        dt = self.leaderboard
        dt.clear(columns=True)

        # 1) Define columns
        base_labels = ["Ping", "Username", "Total", "Muted"]
        current_rounds_count = max(0, self.round_idx)
        round_labels = [f"R{i}" for i in range(1, current_rounds_count + 1)]

        # 2) Add columns and capture keys (order matches labels)
        keys = dt.add_columns(*base_labels, *round_labels)
        ping_key, name_key, total_key, muted_key, *round_keys = keys

        # 3) Add rows
        for p in self.players:
            ping = int(p.get("latency_ms", 0)) if str(p.get("latency_ms", "")).isdigit() else p.get("latency_ms", "-")
            name = p["player_id"]
            total = int(p.get("score", 0))
            is_muted = "🔇" if p.get("is_muted", False) else "🔊"
            
            raw_rounds = p.get("round_scores", [])
            rounds = [int(v) for v in raw_rounds[:current_rounds_count]]
            
            while (len(rounds) < current_rounds_count):
                rounds.append(0)

            row = [ping, name, total, is_muted, *rounds]
            dt.add_row(*row)

        # 4) Sort by Total (desc)
        if len(dt.columns) > 2:
            dt.sort(total_key, reverse=True)

    def append_chat(self, user: str, msg: str, priv: str | None = None) -> None:
        if user == "System":
            priv = "sys"
        elif user == self.app.session.host_id:
            priv = "host"
            
        
        
        # [LOGGING] Chat Received/Sent
        if hasattr(self.app, "session_logger") and self.app.session_logger:
            if user == self.username:
                self.app.session_logger.log_chat_submitted(msg)
            else:
                is_host = (priv == "host" or priv == "sys")
                self.app.session_logger.log_chat_received(user, msg, is_host)

        if self.chat_log:
            self.chat_log.append_chat(user, msg, priv)
        else:
            logger.warning(f"[Student UI] Chat log not available. Message from {user}: {msg}")
    
    def append_rainbow_chat(self, user: str, msg: str) -> None:
        if self.chat_log:
            self.chat_log.append_rainbow_chat(user, msg)
        else:
            logger.warning(f"[Student UI] Chat log not available. Message from {user}: {msg}")
            
    def action_send_chat(self) -> None:
        if self.chat_input and self.chat_input.has_focus:
            self._send_chat_from_input()

    def on_input_submitted(self, e: Input.Submitted) -> None:
        if e.input.id == "chat-input":
            self._send_chat_from_input()
    
    def _send_chat_from_input(self) -> None:
        if self.chat_input and (txt := self.chat_input.value.strip()):
            self.chat_input.value = ""
            asyncio.create_task(self.app.session.send_chat(txt))

    @work
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "")
        if bid == "chat-send":
            self._send_chat_from_input()
            
        elif bid.startswith("option-"):
            if self.quiz_question_widget is None:
                return
            
            # [LOGGING] Answer Submitted
            if hasattr(self.app, "session_logger") and self.app.session_logger:
                # Map button ID to index
                idx_map = {"option-a": 0, "option-b": 1, "option-c": 2, "option-d": 3}
                idx = idx_map.get(bid)
                if idx is not None:
                    val = LABELS[idx] if idx < len(LABELS) else "?"
                    self.app.session_logger.log_answer_submitted(
                        q_index=self.round_idx - 1, # 0-based
                        answer_index=idx,
                        answer_value=val
                    )

            await self.app.session.send_answer(self.quiz_question_widget)


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
        yield Header(show_clock=True)
        with Vertical(id="login-container"):
            yield BorderedInputContainer(border_title="Session ID", 
                                            input_placeholder="demo", 
                                            id="session-id")
            yield BorderedInputContainer(border_title="Session Password", 
                                         input_placeholder="Leave blank for no password", 
                                         id="pw-input")
            yield BorderedTwoInputContainer(border_title="Server IP",
                                            input1_placeholder="0.0.0.0 or kauschcarz.ddns.net",
                                            input2_placeholder="49000",
                                            id="server-inputs")
            yield BorderedInputButtonContainer(input_title="Username",
                                            input_placeholder="johndoe123",
                                            button_title="Launch",
                                            id="username-inputs") 
  
            yield Static("* Server Error Message Placeholder *", classes="error-message hidden")
        yield Footer()
        
    async def action_attempt_login(self) -> None:
        vals = self._student_get_values()
        logger.debug("[Student Login UI] Attempting login with values:")
        for k,v in vals.items():
            logger.debug(f"[Student Login UI] Login input: {k} = {v}")
        
        # perform validation
        ok, msg = _student_validate(vals)
        if not ok:
            self._show_error(msg)
            return
        
        # [LOGGING] Initialize Session Logger
        try:
            base_dir = Path.cwd()
            logger_obj = SessionLogger(base_dir=base_dir)
            logger_obj.log_session_start(
                session_id=vals["session_id"],
                client_id=vals["username"],
                role="student",
                server_url=f"{vals['server_ip']}:{vals['server_port']}",
                username=vals["username"],
            )
            self.app.session_logger = logger_obj
            logger.info(f"Session logger initialized at {logger_obj.path}")
            
        except Exception as e:
            logger.error(f"Failed to init session logger: {e}")

        self.query_one(".error-message").add_class("hidden")
        success, msg = await self._connect_to_server(vals)
        if not success:
            self.title = "Failed to connect to server."
            self._show_error(msg)
            logger.debug(f"Login failed, staying on login screen: {msg}")
            return
        if success:
            logger.debug("join request sent, waiting for joined message...")
            self.title = "Connected, waiting to join session..."

    async def _connect_to_server(self, vals: dict) -> tuple[bool, str]:
        """Establish WSClient connection and start session."""
        self.title = "Connecting to server..."
        
        # establish connection if not already connected
        if self.app.session is None:
            self.app.session = StudentInterface.from_dict(vals.copy())
        else:
            logger.debug("[Student Login UI] Reusing existing session connection.")
            # check if session id or username changed
            if (self.app.session.session_id != vals["session_id"] or
                self.app.session.username != vals["username"]):
                
                logger.debug("[Student Login UI] Session ID or username changed, disconnecting and updating session info.")
                await self.app.session.stop()
                
                self.app.session = StudentInterface.from_dict(vals.copy())
            else:
                logger.debug("[Student Login UI] Session ID and username unchanged, reusing existing session.")
                self.app.session.set_from_dict(vals.copy())
        
        try:
            if not await self.app.session.start():
                return False, "Failed to establish connection with server."
        except TimeoutError as e:
            logger.error(f"Timeout while connecting to server: {e}")
            return False, "Connection timed out."

        logger.debug("[Student Login UI] Connection established, sending join message...")
        await self.app.session.send_join()
        return True, ""
        
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "username-inputs-button":
            await self.action_attempt_login()        

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.action_attempt_login()

    def _student_get_values(self) -> dict:
        
        vals = {
            "app": self.app,
            "session_id": self.query_one("#session-id-input", Input).value.strip() or "demo",
            "password":   self.query_one("#pw-input-input", Input).value.strip(),
            "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip() or "kauschcarz.ddns.net",
            # "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip() or "0.0.0.0",
            "server_port": int(self.query_one("#server-inputs-input2", Input).value.strip() or "49000"),
            "username":  self.query_one("#username-inputs-input", Input).value.strip() or "johndoe123",
        }
        
        return vals


    def _show_error(self, msg: str) -> None:
        logger.debug("Showing login error: " + msg)
        err = self.query_one(".error-message", Static)
        err.update(f"[b]* {msg} *[/b]")
        self.query_one(".error-message").remove_class("hidden")


class StudentUIApp(App):

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
        ("ctrl+z", "suspend_process", "Suspend" ),
        
    ]

    MODES = {
        "login": LoginScreen,
        "main": MainScreen,
    }
    
    SCREENS = {
        "main": MainScreen,
        "login": LoginScreen,
    }
    
    def __init__(self) -> None:
        super().__init__()
        self.session: StudentInterface | None = None
        self.session_logger: SessionLogger | None = None
        self.quiz: Quiz | None = None

    def action_toggle_dark(self) -> None:
        self.theme = THEME if self.theme != THEME else "textual-dark"

    async def on_mount(self, event: events.Mount) -> None:
        self.theme = THEME
        
        # [RECOVERY] Check for crashed sessions
        try:
            result = load_latest_incomplete_history(base_dir=Path.cwd())
            if result:
                history, path = result
                logger.info(f"Found incomplete session log: {path}")
        except Exception as e:
            logger.error(f"Error checking logs: {e}")

        self.push_screen("login")
        # self.push_screen("main")
        
    async def on_mode_changed(self, event: App.ModeChanged) -> None:
        logger.debug(f"Switched to mode: {event.mode}")

    async def on_shutdown(self, event: events.Shutdown) -> None:
        # [LOGGING] Close log
        if self.session_logger:
            self.session_logger.log_session_end(reason="normal-exit", graceful=True)

if __name__ == "__main__":
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        filename=log_dir / 'student.log', 
        level=logging.INFO, 
        format='%(asctime)s %(levelname)s [STUDENT] %(message)s',
        filemode='w',
        force=True
    )
    logging.getLogger("knewit").setLevel(logging.DEBUG)
    logging.info("Student UI starting up...")
    
    StudentUIApp().run()