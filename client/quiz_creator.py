"""Quiz creation interface for hosts."""
import asyncio
import json
import secrets
from pathlib import Path

from textual import on, work
from textual.binding import Binding
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button, Input
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen


class QuizCreator(ModalScreen):
    """Interface for creating quizzes."""
    
    
    CSS = """
    Screen {
        layout: vertical;
        padding: 1;
    }

    #header {
        height: 3;
        content-align: center middle;
        background: blue;
    }

    #status {
        height: 1;
        color: yellow;
        margin-bottom: 1;
    }

    #quiz-title-section {
        height: 4;
        margin-bottom: 1;
    }

    #quiz_title {
        width: 100%;
    }

    #questions-container {
        height: 1fr;
        border: solid cyan;
        margin-bottom: 1;
    }

    .question-block {
        border: solid green;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    .question-block.current {
        border: solid yellow;
    }

    .question-num {
        color: cyan;
        text-style: bold;
        margin-bottom: 1;
    }

    .answer-row {
        height: auto;
        margin-bottom: 1;
    }

    .answer-label {
        width: 3;
        content-align: right middle;
    }

    .answer-input {
        width: 1fr;
    }

    .correct-btn {
        width: 5;
        min-width: 5;
    }

    #button-container {
        height: 3;
    }

    #load-container {
        height: 3;
    }

    #load_path {
        width: 1fr;
    }

    Button {
        margin: 0 1;
    }

    #save-btn {
        background: green;
    }

    #add-question-btn {
        background: blue;
    }

    #cancel-btn {
        background: red;
    }

    #load-quiz-btn {
        background: purple;
    }
    """

    quiz_title = reactive("")
    questions = reactive([])


    def __init__(self) -> None:
        super().__init__()
        self.questions_data: list[dict] = []  # {prompt, options[4], correct_idx}
        self.current_q_index: int = 0
        self.quiz_path: Path | None = None
    # ------------------------------------------------------------------ layout

    def compose(self) -> ComposeResult:
        """Create widgets."""
        yield Header()

        yield Static("Quiz Creator", id="header")
        yield Static("", id="status")

        with Vertical(id="quiz-title-section"):
            yield Static("Quiz Title:")
            yield Input(id="quiz_title", placeholder="Enter quiz title")

        with ScrollableContainer(id="questions-container"):
            # Question blocks added in on_mount / load
            pass

        with Horizontal(id="button-container"):
            yield Button("Prev Question", id="prev-question-btn")
            yield Button("Next Question", id="next-question-btn")
            yield Button("Add Question", id="add-question-btn")
            yield Button("Remove Question", id="remove-question-btn")
            yield Button("Save Quiz", id="save-btn")
            yield Button("Cancel", id="cancel-btn")


        '''
        with Horizontal(id="load-container"):
            yield Button("Load Quiz from path:", id="load-quiz-btn")
            yield Input(id="load_path", placeholder="quizzes/abcd1234.json")
        '''

        yield Footer()

    async def on_mount(self) -> None:
        """Start with one blank question."""
        self.questions_data.append(
            {"prompt": "", "options": ["", "", "", ""], "correct_idx": 0}
        )
        self._add_question_block_from_existing()
        self.go_to_question(0)

    # ------------------------------------------------------------------ UI helpers

    def _remove_question_block(self, index: int) -> None:
        """Remove a question block from the UI and data."""
        if not (0 <= index < len(self.questions_data)):
            return

        container = self.query_one("#questions-container")
        block = self.query_one(f"#q-block-{index+1}", Vertical)
        block.remove()
        del self.questions_data[index]

        # # Renumber remaining blocks
        # for i in range(index, len(self.questions_data)):
        #     blk = self.query_one(f"#q-block-{i+2}", Vertical)
        #     blk.id = f"q-block-{i+1}"
        #     num_lbl = blk.query_one(".question-num", Static)
        #     num_lbl.update(f"Question {i+1}")

        #     prompt_input = blk.query_one(f"#q-prompt-{i+2}", Input)
        #     prompt_input.id = f"q-prompt-{i+1}"

        #     for j in range(4):
        #         ans_row = blk.query_one(f".answer-row:nth-child({j+2})", Horizontal)
        #         opt_input = ans_row.query_one(f"#q-{i+2}-opt-{j}", Input)
        #         opt_input.id = f"q-{i+1}-opt-{j}"
        #         correct_btn = ans_row.query_one(f"#q-{i+2}-correct-{j}", Button)
        #         correct_btn.id = f"q-{i+1}-correct-{j}"

    def _add_question_block_from_existing(self) -> None:
        """Create a question block for an existing questions_data entry."""
        question_num = len(self.questions_data)
        q_index = question_num - 1
        q_data = self.questions_data[q_index]

        container = self.query_one("#questions-container")

        block = Vertical(classes="question-block", id=f"q-block-{question_num}")
        block.compose_add_child(Static(f"Question {question_num}", classes="question-num"))

        prompt_input = Input(
            placeholder="Enter question prompt",
            id=f"q-prompt-{question_num}",
        )
        prompt_input.value = q_data["prompt"]
        block.compose_add_child(prompt_input)

        for i, label in enumerate(["A", "B", "C", "D"]):
            row = Horizontal(classes="answer-row")
            row.compose_add_child(Static(f"{label}:", classes="answer-label"))
            opt_input = Input(
                placeholder=f"Answer option {label}",
                id=f"q-{question_num}-opt-{i}",
                classes="answer-input",
            )
            opt_input.value = q_data["options"][i] if i < len(q_data["options"]) else ""
            row.compose_add_child(opt_input)

            is_correct = i == q_data["correct_idx"]
            row.compose_add_child(
                Button(
                    "✓" if is_correct else " ",
                    id=f"q-{question_num}-correct-{i}",
                    classes="correct-btn",
                    variant="success" if is_correct else "default",
                )
            )
            block.compose_add_child(row)

        container.mount(block)

    def add_question_block(self) -> None:
        """Add a new question (data + UI block) and jump to it."""
        if len(self.questions_data) >= 20:
            self.query_one("#status").update("[red]Maximum 20 questions reached")
            return

        self.questions_data.append(
            {"prompt": "", "options": ["", "", "", ""], "correct_idx": 0}
        )
        self._add_question_block_from_existing()
        self.go_to_question(len(self.questions_data) - 1)

    def go_to_question(self, index: int) -> None:
        """Set the current question index, highlight it, and focus its prompt."""
        if not (0 <= index < len(self.questions_data)):
            return

        self.current_q_index = index
        q_num = index + 1

        for i in range(len(self.questions_data)):
            block = self.query_one(f"#q-block-{i+1}", Vertical)
            block.remove_class("current")
        curr_block = self.query_one(f"#q-block-{q_num}", Vertical)
        curr_block.add_class("current")

        prompt = self.query_one(f"#q-prompt-{q_num}", Input)
        prompt.focus()

        self.query_one("#status").update(
            f"[green]Editing Question {q_num} of {len(self.questions_data)}"
        )

    # ------------------------------------------------------------------ events

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        button_id = event.button.id

        if button_id == "add-question-btn":
            self.add_question_block()

        elif button_id == "save-btn":
            await self.save_quiz()

        elif button_id == "cancel-btn":
            self.dismiss()
            
        elif button_id == "remove-question-btn":
            if len(self.questions_data) <= 1:
                self.query_one("#status").update("[red]At least one question is required")
                return
            self._remove_question_block(self.current_q_index)
            new_index = min(self.current_q_index, len(self.questions_data) - 1)
            self.go_to_question(new_index)

        elif button_id == "prev-question-btn":
            if self.current_q_index > 0:
                self.go_to_question(self.current_q_index - 1)

        elif button_id == "next-question-btn":
            if self.current_q_index < len(self.questions_data) - 1:
                self.go_to_question(self.current_q_index + 1)

        elif button_id == "load-quiz-btn":
            await self.load_quiz_from_path()

        elif button_id and "correct" in button_id:
            # Format: q-{num}-correct-{idx}
            parts = button_id.split("-")
            q_num = int(parts[1])
            opt_idx = int(parts[3])

            self.questions_data[q_num - 1]["correct_idx"] = opt_idx

            for i in range(4):
                btn = self.query_one(f"#q-{q_num}-correct-{i}", Button)
                btn.label = "✓" if i == opt_idx else " "
                btn.variant = "success" if i == opt_idx else "default"

    # ------------------------------------------------------------------ loading

    async def load_quiz_from_path(self) -> None:
        """Load an existing quiz from the path in the load_path input."""
        path_str = self.query_one("#load_path", Input).value.strip()
        if not path_str:
            self.query_one("#status").update("[red]Please enter a path to a quiz JSON file")
            return

        path = Path(path_str)
        if not path.exists() or not path.is_file():
            self.query_one("#status").update(f"[red]File not found: {path}")
            return

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.query_one("#status").update(f"[red]Failed to read file: {e}")
            return

        self.quiz_path = path
        self.questions_data.clear()
        self.current_q_index = 0

        container = self.query_one("#questions-container")
        for child in list(container.children):
            child.remove()

        title = data.get("title", "")
        self.query_one("#quiz_title", Input).value = title

        for q in data.get("questions", []):
            options = q.get("options", [])
            opts4 = (options + ["", "", "", ""])[:4]
            self.questions_data.append(
                {
                    "prompt": q.get("prompt", ""),
                    "options": opts4,
                    "correct_idx": int(q.get("correct_idx", 0))
                    if q.get("correct_idx", 0) in range(4)
                    else 0,
                }
            )

        if not self.questions_data:
            self.questions_data.append(
                {"prompt": "", "options": ["", "", "", ""], "correct_idx": 0}
            )

        for _ in self.questions_data:
            self._add_question_block_from_existing()

        self.go_to_question(0)
        self.query_one("#status").update(f"[green]Loaded quiz from {path}")

    # ------------------------------------------------------------------ saving / validation

    async def save_quiz(self) -> None:
        """Collect and save the quiz."""
        try:
            title = self.query_one("#quiz_title", Input).value.strip()
            if not title:
                self.query_one("#status").update("[red]Please enter a quiz title")
                return

            quiz_data: dict[str, object] = {
                "title": title,
                "questions": [],
            }

            for i, q_data in enumerate(self.questions_data):
                q_num = i + 1

                prompt_input = self.query_one(f"#q-prompt-{q_num}", Input)
                prompt = prompt_input.value.strip()
                if not prompt:
                    self.query_one("#status").update(
                        f"[red]Question {q_num} is missing a prompt"
                    )
                    self.go_to_question(i)
                    return

                raw_opts: list[str] = []
                for opt_idx in range(4):
                    opt_val = self.query_one(
                        f"#q-{q_num}-opt-{opt_idx}", Input
                    ).value.strip()
                    raw_opts.append(opt_val)

                nonempty_indices = [idx for idx, txt in enumerate(raw_opts) if txt]

                if len(nonempty_indices) < 2:
                    self.query_one("#status").update(
                        f"[red]Question {q_num} needs at least two options"
                    )
                    self.go_to_question(i)
                    return

                correct_orig = q_data["correct_idx"]

                if correct_orig not in nonempty_indices:
                    self.query_one("#status").update(
                        f"[red]Question {q_num}: the correct option must be a non-empty choice"
                    )
                    self.go_to_question(i)
                    return

                options: list[str] = []
                correct_idx: int | None = None
                for orig_idx in nonempty_indices:
                    new_idx = len(options)
                    options.append(raw_opts[orig_idx])
                    if orig_idx == correct_orig:
                        correct_idx = new_idx

                if correct_idx is None:
                    self.query_one("#status").update(
                        f"[red]Question {q_num}: no correct option chosen"
                    )
                    self.go_to_question(i)
                    return

                quiz_data["questions"].append(
                    {
                        "prompt": prompt,
                        "options": options,
                        "correct_idx": correct_idx,
                    }
                )

            if not quiz_data["questions"]:
                self.query_one("#status").update(
                    "[red]Please add at least one question"
                )
                return
            
            if getattr(self.app, 'quiz_path', None) is not None:
                self.app.quiz_path = self.quiz_path
            self.dismiss(quiz_data)

        except Exception as e:
            self.query_one("#status").update(f"[red]Error: {e}")
            import traceback

            traceback.print_exc()


def main() -> dict | None:
    """Run the quiz creator, then save or update the quiz file."""

    app = QuizCreatorApp()
    result = app.run()

    if result:
        quizzes_dir = Path(__file__).parent.parent / "quizzes"
        quizzes_dir.mkdir(exist_ok=True)

        if app.quiz_path is not None:
            quiz_file = app.quiz_path
            quiz_id = quiz_file.stem
        else:
            quiz_id = secrets.token_urlsafe(6)
            quiz_file = quizzes_dir / f"{quiz_id}.json"

        with quiz_file.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"\nQuiz '{result['title']}' saved as {quiz_id}.json")
        print(f"Location: {quiz_file}")
        print(f"Questions: {len(result['questions'])}\n")

    return result


class QuizCreatorApp(App[dict[str, object] | None]):
    """App that uses QuizCreator(Screen) for creating quizzes."""
    CSS = QuizCreator.CSS
    BINDINGS = [Binding("ctrl+q", "quit", "Quit", show=False, priority=True)]
    
    
    def __init__(self):
        self.quiz_path: Path | None = None
        super().__init__()
    
    @work
    async def on_mount(self) -> None:
        """Mount the QuizCreator screen."""
        quiz_data = await self.push_screen_wait(QuizCreator())
        # exit the wrapper app and return the result from run()/run_async()
        self.exit(quiz_data)


async def run_async() -> dict | None:
    """Run quiz creator asynchronously."""
    app = QuizCreatorApp()
    return await app.run_async()


if __name__ == "__main__":
    result = main()
