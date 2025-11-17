# client/common.py
from dataclasses import dataclass, field
from typing import Optional
import sys
import logging
import asyncio
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))
from knewit_arch.server.quiz_types import StudentQuestion
from textual.app import App

logging.basicConfig(filename='logs/host_log.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.debug("Logger module loaded from common.")


from client.ws_client import WSClient

@dataclass
class SessionInterface:
    server_ip: str
    server_port: int
    session_id: str
    username: str
    password: str
    ws: Optional[WSClient] = field(default=None, init=False)
    ws_task: Optional[asyncio.Task] = field(default=None, init=False)
    is_connected: bool = False
    app: App | None = None

    @classmethod
    def from_dict(cls, data):
        return cls(
            app=data["app"],
            server_ip=data["server_ip"],
            server_port=data["server_port"],
            session_id=data["session_id"],
            username=data["username"],
            password=data["password"]
        )

    async def start(self) -> bool:
        logger.debug("StudentInterface.start() called")

        url = f"ws://{self.server_ip}:{self.server_port}/ws" \
            f"?session_id={self.session_id}&username={self.username}"
        
        self.ws = WSClient(url, self.on_event)

        # Use Textual-safe async runner
        self.ws_task = self.app.run_worker(
            self.ws.start(),
            name="websocket-client",
            group="session",
            description="WebSocket connection to quiz server",
            thread=False,  # make sure it's an async task, not a thread
        )

        # Optionally wait until connected (see earlier Event-based logic)
        connected = await self.ws.wait_until_connected(timeout=5.0)
        logger.debug(f"WebSocket connected: {connected}")
        self.is_connected = connected

        return connected


    async def send(self, payload: dict):
        if self.ws and self.is_connected:
            await self.ws.send(payload)

    def get_main_screen(self):
        """Helper to access the MainScreen instance."""
        screen = self.app.get_screen("main")
        if screen is None:
            raise RuntimeError("MainScreen is not mounted yet.")
        return screen


    def stop(self):
        """Signal WSClient to shut down and cancel its task."""
        if self.ws:
            self.ws.stop()
        if self.ws_task:
            self.ws_task.cancel()
        self.is_connected = False

    async def on_event(self, message: dict):
        """Override in subclass (HostSessionModel or StudentSessionModel)."""
        logger.debug(f"[SessionModel] Received: {message}")


@dataclass
class StudentInterface(SessionInterface):

    async def on_event(self, message: dict):
        msg_type = message.get("type")
        screen = self.get_main_screen()

        if msg_type == "welcome":
            logger.info("Student contacted server successfully.")
            screen.title = f"Contacted server as {self.username}"
            screen.sub_title = f"Session: {self.session_id} 1"
            screen.append_chat("System", "Connected to server.")

        elif msg_type == "session.joined":
            logger.info("Student joined session.")
            screen.title = f"Connected as {self.username}"
            screen.sub_title = f"Session: {self.session_id} 2"
            screen.append_chat("System", "Connected to server.")
            screen.student_load_quiz()

        elif msg_type == "question.next":
            qdata = message.get("question")
            if qdata:
                sq = StudentQuestion.from_dict(qdata)
                screen.set_quiz_question(sq)

        elif msg_type == "quiz.loaded":
            quiz_title = message.get("quiz_title", "Untitled Quiz")
            logger.info(f"Quiz loaded: {quiz_title}")
            screen.append_chat("System", f"Quiz '{quiz_title}' loaded.")

        elif msg_type == "answer.recorded":
            # Optional: lock UI or log confirmation
            logger.info("Answer recorded by server.")

        elif msg_type == "quiz.finished":
            screen.end_quiz()

        elif msg_type == "lobby.update":
            screen.update_players(message.get("players", []))

        elif msg_type == "kicked":
            logger.warning("Student was kicked from session.")
            # TODO: show modal or redirect to login
            screen.append_chat("System", "You were removed from the session.")

        elif msg_type == "session.closed":
            logger.info("Session closed by host.")
            # TODO: show modal or redirect to login
            screen.append_chat("System", "Session has ended.")

        elif msg_type == "error":
            logger.error(f"Server error: {message.get('detail')}")
            screen.append_chat("System", f"Error: {message.get('detail')}")

        else:
            logger.debug(f"[StudentInterface] Unhandled message type: {msg_type}")
            await super().on_event(message)
            



    async def send_answer(self, index: int):
        """Send an answer selection to the server."""
        await self.send({
            "type": "answer.submit",
            "index": index
        })

    async def send_chat(self, msg: str):
        """Send a chat message to the server."""
        await self.send({
            "type": "chat",
            "msg": msg
        })

            
@dataclass
class HostInterface(SessionInterface):

    async def on_event(self, message: dict):
        if message.get("type") == "answer":
            print(f"[HOST] Received answer: {message}")
        elif message.get("type") == "student_joined":
            print(f"[HOST] Student joined: {message}")
        else:
            await super().on_event(message)