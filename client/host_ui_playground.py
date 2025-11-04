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
from textual.widgets import Header, Footer, Static, Button, Input, TabbedContent, TabPane, DataTable, ListView, ListItem, Button, Log, Label
from textual.containers import Horizontal, Vertical, Container, VerticalScroll, HorizontalGroup, VerticalGroup, HorizontalScroll
from textual.message import Message
from textual.app import App, ComposeResult
from textual.widget import Widget
from textual import events
import secrets


# ---- shared model -----------------------------------------------------------
@dataclass
class SessionModel:
    session_id: str
    host_name: str
    server_ip: str
    server_port: int

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


class QuizPreview(Static):
    def __init__(self) -> None:
        super().__init__(classes="quiz-preview")
        self.title = "No quiz loaded"
        self.questions = []

    def set_quiz(self, title: str, questions: List[str]) -> None:
        self.title = title
        self.questions = questions
        self.refresh()

    def render(self) -> str:
        qcount = len(self.questions)
        first = self.questions[0] if self.questions else ""
        return f"Quiz: {self.title}\nQuestions: {qcount}\n\nPreview:\n{first}".strip()





class MainScreen(Screen):
    """Host main screen."""

    CSS = """
    #main-container { height: 1fr; }
    #left-column { width: 3fr; height: 1fr; padding: 0; border: tall $panel; }
    #right-tabs  { width: 2fr; height: 1fr; padding: 1; border: tall $panel; }

    .quiz-question { height: 4fr; background: red; }
    .controls-area { height: 1fr; background: blue; }
    .graphs-area   { height: 3fr; background: green; }

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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="<!> KnewIt Host UI Main <!>")
        with Horizontal(id="main-container"):
            with Vertical(id="left-column"):
                yield Static("Quiz Question Area", classes="quiz-question")
                yield Static("Controls Area", classes="controls-area")
                yield Static("Graphs Area", classes="graphs-area")

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

        # Setup leaderboard columns
        assert self.leaderboard is not None
        self.leaderboard.cursor_type = "row"   # nicer selection
        self.leaderboard.add_columns("Ping", "Name", "Total")
        self.leaderboard.fixed_columns = 3  # keep base columns visible when scrolling

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
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "")
        if bid.startswith("kick-"):
            self.append_chat(f"* Kicked {bid.removeprefix('kick-')}")
        elif bid.startswith("mute-"):
            self.append_chat(f"* Toggled mute for {bid.removeprefix('mute-')}")

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tab.id == "user-controls":
            self._rebuild_user_controls()

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

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("tab", "focus_next", "Focus next"),
        ("shift+tab", "focus_previous", "Focus previous"),
        ("q", "quit", "Quit"),
    ]

    MODES = {
        "login": LoginScreen,
        "main": MainScreen,
    }
    
    def __init__(self) -> None:
        super().__init__()
        self.players: List[dict] = []
        self.player_list_container: VerticalScroll | None = None
        self.quiz_preview: QuizPreview | None = None


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

    def set_quiz_preview(self, title: str, questions: List[str]) -> None:
        if self.quiz_preview:
            self.quiz_preview.set_quiz(title, questions)

    # Bindings / actions

    def action_toggle_dark(self) -> None:
        self.theme = "textual-dark" if self.theme != "textual-dark" else "textual-light"

    async def on_mount(self, event: events.Mount) -> None:  # type: ignore[override]
        # seed some players for the initial view
        # self.switch_mode("main")
        self.switch_mode("login")
        self.players = [
            {"player_id": "p1001", "name": "mike"},
            {"player_id": "p1002", "name": "amy"},
        ]
        self.update_players(self.players)
        # sample quiz
        self.set_quiz_preview("Demo Quiz", ["What is 2+2?", "What is the capital of France?"])
        self.theme = "textual-dark"

if __name__ == "__main__":
    HostUIPlayground().run()
