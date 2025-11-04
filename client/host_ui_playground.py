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
from typing import List
from dataclasses import dataclass
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Input
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.app import App, ComposeResult
from textual.containers import Container, HorizontalGroup, VerticalScroll, Vertical
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
    """Screen for host to enter session details and login."""
    
    BINDINGS = [
        ("a", "add_player", "Add player"),
        ("r", "remove_player", "Remove player"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Host Login Screen - under construction")

        # Bindings / actions
    def action_add_player(self) -> None:
        pid = f"p{random.randint(1000,9999)}"
        name = random.choice(["alice", "bob", "carol", "dave", "eve"]) + str(random.randint(1,9))
        self.players.append({"player_id": pid, "name": name})
        self.update_players(self.players)

    def action_remove_player(self) -> None:
        if self.players:
            self.players.pop()
            self.update_players(self.players)



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
            "session_id": self.query_one("#session-inputs-input", Input).value.strip(),
            "password":   self.query_one("#pw-inputs-input", Input).value.strip(),
            "server_ip":  self.query_one("#server-inputs-input1", Input).value.strip(),
            "server_port": self.query_one("#server-inputs-input2", Input).value.strip(),
            "host_name":  self.query_one("#host-inputs-input", Input).value.strip(),
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
