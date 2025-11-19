from textual.widgets import Static, Input, Button
from textual.containers import HorizontalGroup
from textual.app import ComposeResult

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

    def __init__(self, player_id: str, *, classes: str | None = None) -> None:
        super().__init__(classes=(classes or "player-card"))
        self.player_id = player_id
        # Avoid clashing with Widget.name property; store as player_name

    def render(self) -> str:
        return f"{self.player_id}"


class BorderedInputContainer(HorizontalGroup):
    def __init__(self, *, 
                 border_title: str,
                 input_placeholder: str | None = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = border_title
        self.input_placeholder = input_placeholder


    def compose(self) -> ComposeResult:
        yield Input(placeholder=self.input_placeholder, id=f"{self.id}-input")

    def on_mount(self) -> None:
        self.border_title = f"{self.border_title}"
        in1 = self.query_one(f"#{self.id}-input", Input)
        in1.styles.width = "1fr"
        self.border_title_align = "center"
        self.border_title_style = "bold"