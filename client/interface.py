from dataclasses import dataclass, field
from typing import Optional
import sys
import logging
import asyncio
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))
from server.quiz_types import StudentQuestion
from textual.app import App
from client.ws_client import WSClient
from common import logger



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
    ready_event: asyncio.Event = field(default_factory=asyncio.Event)

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

    def set_from_dict(self, data):
        self.app = data["app"]
        self.session_id = data["session_id"]
        self.username = data["username"]
        self.password = data["password"]
        self.server_ip = data["server_ip"]
        self.server_port = data["server_port"]

    async def start(self) -> bool:
        logger.debug("StudentInterface.start() called")
        
        if self.is_connected:
            logger.debug("Already connected, skipping start.")
            return True
        
        url = f"ws://{self.server_ip}:{self.server_port}/ws" \
            f"?session_id={self.session_id}&player_id={self.username}"
        logger.info(f"Connecting to WebSocket URL: {url}")
        
        
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
        if not self.ws:
            logger.warning("Tried to send but WSClient is None")
            return
        logger.debug("Sending payload through WSClient.")
        await self.ws.send(payload)
            
    def get_main_screen(self):
        """Helper to access the MainScreen instance."""
        screen = self.app.get_screen("main")
        if screen is None:
            raise RuntimeError("MainScreen is not mounted yet.")
        return screen

    async def stop(self):
        """Signal WSClient to shut down and cancel its task."""
        if not self.ws:
            return

        self.ws.stop()           # signal WSClient loop to exit

        if self.ws_task:
            try:
                await self.ws_task.wait()
            except Exception:
                pass

    async def on_event(self, message: dict):
        """Override in subclass (HostSessionModel or StudentSessionModel)."""
        logger.debug(f"[SessionModel] Received: {message}")


@dataclass
class StudentInterface(SessionInterface):

    async def on_event(self, message: dict):
        msg_type = message.get("type")
        screen = self.get_main_screen()

        if msg_type == "welcome":
            logger.debug("Student contacted server successfully.")
            screen.title = f"Contacted server as {self.username}"
            screen.sub_title = f"Session: {self.session_id} 1"
            # await self.send_join()

        elif msg_type == "session.joined":
            logger.info(f"Student joined session {self.session_id}.")
            self.session_id = message.get("session_id", self.session_id) # update session id if a differeont one as assigned for some reason
            self.username = message.get("name", self.username) # update username if changed by server
            screen.title = f"Connected as {self.username}"
            screen.sub_title = f"Session: {self.session_id}"
            screen.append_chat("System", f"Connected to server as {self.username}.")
            self.app.push_screen("main")
            # self.ready_event.set()
            # screen.student_load_quiz()
            
        elif msg_type == "chat":
            msg = message.get("msg", "")
            p = message.get("player_id", "Host")
            screen.append_chat(p, msg)

        elif msg_type == "question.next":
            qdata = message.get("question")
            if qdata:
                sq = StudentQuestion.from_dict(qdata)
                screen.set_quiz_question(sq)

        elif msg_type == "quiz.loaded":
            quiz_title = message.get("quiz_title", "Untitled Quiz")
            logger.debug(f"Quiz loaded: {quiz_title}")
            screen.append_chat("System", f"Quiz '{quiz_title}' loaded.")

        elif msg_type == "answer.recorded":
            # Optional: lock UI or log confirmation
            logger.debug("Answer recorded by server.")

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
            
        elif msg_type == "reject.pw":
            logger.error("Password rejected by server.")
            screen.append_chat("System", "Error: Incorrect password.")
            screen._show_error(message["msg"])
        else:
            logger.debug(f"[StudentInterface] Unhandled message type: {msg_type}")
            await super().on_event(message)

################################################
#            Student Event Callbacks              #
################################################


    async def send_join(self):
        """Send join session message to server."""
        await self.send({
            "type": "session.join",
            "password": self.password
        })
        
    async def send_answer(self, index: int):
        """Send an answer selection to the server."""
        await self.send({
            "type": "answer.submit",
            "answer_idx": index,   # <-- match server
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
        msg_type = message.get("type")
        screen = self.get_main_screen()
        logger.debug(f"[HostInterface] Received message: {message}")
        
        if msg_type == "welcome":
            logger.debug("Host contacted server successfully.")
            screen.title = f"Contacted server as {self.username}"
            # screen.sub_title = f"Session: {self.session_id}"
            await self.send_create()   
        elif msg_type == "session.created":
            logger.debug("Host session created successfully.")
            self.ready_event.set()
            logger.info(f"Host created session {self.session_id}.")
            screen.title = f"Hosting as {self.username}"
            # screen.sub_title = f"Session: {self.session_id}"
            screen.append_chat("System", "Session created successfully.")
        # elif msg_type == "error":
        elif msg_type == "chat":
            msg = message.get("msg", "")
            p = message.get("player_id", "Host")
            screen.append_chat(p, msg)
        else:
            await super().on_event(message)
    
    ###############################################
    #            Host Event Callbacks              #
    ##############################################
    async def send_chat(self, msg: str):
        """Send a chat message to the server."""
        await self.send({
            "type": "chat",
            "msg": msg
        })
    
    async def send_create(self):
        """Send a session creation request to the server."""
        logger.debug("send_create called")
        packet = {
            "type": "session.create",
        }
        
        if self.password is not None and self.password != "":
            packet["password"] = self.password
            
        await self.send(packet)
        logger.debug("Sent session.create message to server.")

        
    async def wait_until_create(self, timeout: float = 10.0) -> bool:
        """Wait until the session has been created (or timeout)."""
        try:
            logger.debug("Waiting for created message to arrive...")
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.debug(f"Timed out waiting for session creation after {timeout} seconds.")
            return False