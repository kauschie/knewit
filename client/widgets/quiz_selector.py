"""Quiz selector - allows host to choose from saved quizzes."""
import asyncio
from pathlib import Path
from textual.app import App, ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Vertical, ScrollableContainer, Grid
from textual.reactive import reactive
import logging
import json
import sys
from pathlib import Path
# Add server directory to path so we can import quiz_types
sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))
from client.common import logger

QUIZ_DIR = Path(__file__).parent.parent.parent / "quizzes"

# logging.basicConfig(filename='logs/quiz_selector.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
# logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.debug("QuizSelector module loaded.")

class QuizFileNotFound(Exception):
    """Custom exception for file not found errors."""
    pass

class QuizSelector(ModalScreen[dict]):
    """Select a quiz from saved quizzes."""
    
    CSS = """
    Screen {
        layout: vertical;
        padding: 1;
    }
    
    QuizSelector {
        align: center middle;
        }
    
    #header {
        height: 3;
        content-align: center middle;
        # background: $surface;
        width: 60%;
        border: thick $boost;
        text-style: bold;
        # color: cyan;
        
    }
    
    #status {
        height: 1;
        width: 60%;
        content-align: center middle;

    }
    
    #quiz-list {
        height: 20;
        width: 60%;
        # content-align: center middle;
        align: center middle;
        border: solid $accent;
        padding: 1;
    }

    #cancel-btn {
        margin-top: 1;
        width: 20%;
        height: 3;
        align: center middle;
    }
    
    #quiz-selection {
        height: 100%;
        background: $panel;
        border: thick $accent;
        padding: 2;
        layout: vertical;
        width: 60%;
        align: center middle;
    }
    
    .quiz-item {
        width: 60%;
        height: 3;
        padding: 1;
        margin-bottom: 1;
        # border: solid green;
    }
    
    .quiz-item:hover {
        # background: $boost 20%;
    }
    
    .selection-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        width: 60%;
    }
    
    .selection-subtitle {
        height: 2;
        content-align: center middle;
        color: yellow;
        width: 60%;
    }
    
    .quiz-select-btn {
        width: 60%;
        min-height: 3;
        margin-bottom: 1;
        background: $secondary 30%;
        border: round $boost;
    }
    
    .quiz-select-btn:hover {
        background: $primary 30%;
        # background: pink;
    }
    
    #cancel-selection {
        width: 60%;
        height: 3;
    }
    
    Vertical {
        align: center middle;
        width: 60%;
        }
    
    Button {
        margin: 1;
        # background: pink;
        # background: $primary 50%;
    }
    
    #main-grid {
        align: center middle;
        width: 70%;
        height: 80%;
        border: thick $accent;
        padding: 2;
    }
    """
    
    def __init__(self, quiz_list: list | None = None):
        super().__init__()
        self.status: Static | None = None
        self.quiz_list = quiz_list
        self.quiz_dir = QUIZ_DIR
        self.msg = f"Found {len(self.quiz_list)} saved quizzes" if self.quiz_list else "No saved quizzes found."

    def compose(self) -> ComposeResult:
        """Create widgets."""


        with Vertical(id="main-grid"):
            yield Static("Select a Quiz", id="header")
            yield Static(self.msg, id="status")

            with ScrollableContainer(id="quiz-list"):
                if not self.quiz_list:
                    yield Static("No saved quizzes found. Create one first!")
                else:
                    for quiz in self.quiz_list:
                        yield Button(
                            f"{quiz['title']}\n{len(quiz['questions'])} questions",
                            id=f"quiz-{quiz['quiz_id']}",
                            classes="quiz-item"
                        )
            
            with Vertical():
                yield Button("Cancel", id="cancel-btn")
    
    async def on_mount(self) -> None:
        """Load quizzes on mount."""
        self.status = self.query_one("#status", Static) 
        self.quiz_list_widget = self.query_one("#quiz-list", ScrollableContainer)
        has_loaded = await self._load_quizzes()
        if not has_loaded:
            self.status.update("[red]Failed to load quizzes.")
        else:
            self.status.update(f"[green]Loaded {len(self.quiz_list)} quizzes.")
            # Re-compose to show loaded quizzes
        self.refresh(repaint=True)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        button_id = event.button.id
        
        if button_id == "cancel-btn" or button_id == "cancel-selection":
            # self.app.switch_mode("main")
            self.dismiss(None)
        elif button_id and button_id.startswith("quiz-"):
            # Extract quiz_id
            quiz_id = button_id[5:]  # Remove "quiz-" prefix
            
            # Find the quiz data
            for quiz in self.quiz_list:
                if quiz['quiz_id'] == quiz_id:
                    self.selected_quiz = quiz
                    logger.info(f"Selected quiz: {self.selected_quiz['title']}")
                    # self.app.switch_mode("main", quiz=self.selected_quiz)
                    self.dismiss(self.selected_quiz)
                    return

    async def _load_quizzes(self) -> bool:
        """Load saved quizzes."""
        logger.info("Loading saved quizzes from directory.")
        try:
            # Get list of saved quizzes

            if not self.quiz_dir.exists():
                logger.error("Quizzes directory does not exist")
                raise QuizFileNotFound("Quizzes directory does not exist")

            # Read all quiz files
            quiz_files = list(self.quiz_dir.glob("*.json"))
            if not quiz_files:
                logger.info("No quiz files found in quizzes directory")
                raise QuizFileNotFound("No quiz files found in quizzes directory")
            
            # Build quiz list
            quiz_list = []
            for quiz_file in quiz_files:
                try:
                    with open(quiz_file, 'r') as f:
                        data = json.load(f)
                        quiz_list.append({
                            'quiz_id': quiz_file.stem,
                            'title': data.get('title', 'Untitled'),
                            'questions': data.get('questions', []),
                        })
                except Exception as e:
                    logger.exception(f"Error reading quiz {quiz_file}: {e}")
            
            if not quiz_list:
                logger.info("No valid quizzes found after loading.")
                raise QuizFileNotFound("No valid quizzes found")
            
            # set quiz list
            self.quiz_list = quiz_list

            logger.info("Successfully loaded quizzes.")
            await self._show_quiz_selection()
            return True
        except QuizFileNotFound as fnf_error:
            logger.error(fnf_error)        
        except Exception as e:
            logger.exception(f"Unexpected error loading quizzes: {e}") 
            self.query_one("#status").update(f"[red]Error loading quiz: {e}")
            import traceback
            traceback.print_exc()
        return False

    async def _show_quiz_selection(self):
        """Show an inline quiz selection menu."""
        # Clear existing content
        self.quiz_list_widget.remove_children()
        selection_container = self.quiz_list_widget
        # Add title
        # selection_container.mount(Static("Select a Quiz", classes="selection-title"))
        selection_container.mount(Static(f"Found {len(self.quiz_list)} saved quizzes", classes="selection-subtitle"))

        logger.info("Displaying quiz selection menu.")
        # Add quiz buttons
        for quiz in self.quiz_list:
            btn = Button(
                f"{quiz['title']}\n({len(quiz['questions'])} questions)",
                id=f"quiz-{quiz['quiz_id']}",
                classes="quiz-select-btn"
            )
            self.quiz_list_widget.mount(btn)
        
        # Add cancel button
        cancel_btn = Button("Cancel", id="cancel-selection", variant="error")
        self.quiz_list_widget.mount(cancel_btn)
        self.refresh(repaint=True)