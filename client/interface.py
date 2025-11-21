from dataclasses import dataclass, field
from typing import Optional, Deque
from collections import deque
import sys
import asyncio
from random import randint
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
    host_id: Optional[str] = None
    ws: Optional[WSClient] = field(default=None, init=False)
    ws_task: Optional[asyncio.Task] = field(default=None, init=False)
    is_connected: bool = False
    app: App | None = None
    # ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    pending_events: Deque[dict] = field(default_factory=deque, init=False)

    def __init__(self):
        self.pending_events = deque()

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
            
    def get_screen(self, screen_type:str = "main"):
        """Helper to access the MainScreen instance."""
        if screen_type != "main" and screen_type != "lobby":
            raise ValueError("screen_type must be 'main' or 'lobby'")
        if not self.app:
            raise RuntimeError("App reference is None.")
        
        screen = self.app.get_screen(screen_type)
        if screen is None:
            raise RuntimeError(f"{screen_type.capitalize()}Screen is not mounted yet.")
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
        logger.debug(f"[StudentInterface] Received message: {message}")
        
        # check if screen is available

        ############################################
        #    Process events for login screen first
        ############################################

        msg_type = message.get("type")
        if msg_type == "welcome":
            logger.debug("Student contacted server successfully.")
            screen = self.get_screen("login")
            if not screen:
                logger.debug("[StudentInterface] Login screen not available, ignoring title and subtitle update.")
            else:
                screen.title = f"Contacted server as {self.username}"
                screen.sub_title = f"Session: {self.session_id}"
            return
        
        elif msg_type == "session.joined":
            logger.info(f"[StudentInterface] Student joined session {self.session_id}.")
            self.session_id = message.get("session_id", self.session_id) # update session id if a differeont one as assigned for some reason
            self.username = message.get("name", self.username) # update username if changed by server
            self.host_id = message.get("host_id", self.host_id)
            await self.app.push_screen("main", wait_for_dismiss=False)
            screen = self.get_screen("main")
            screen.title = f"Connected as {self.username}"
            screen.sub_title = f"Session: {self.session_id}"
            # screen.append_chat("System", f"Connected to server as {self.username}.")
            return

        ############################################
        #    Process events for main screen
        ############################################

        screen = self.get_screen("main")
        if not screen:
            self.pending_events.append(message)
            logger.debug(f"[StudentInterface] Main screen not available, queuing event.")
            return
        
        if msg_type == "chat":
            msg = message.get("msg", "")
            p = message.get("player_id", "unknown")
            screen.append_chat(p, msg)

        elif msg_type == "question.next":
            qdata = message.get("question")
            if qdata:
                sq = StudentQuestion.from_dict(qdata)
                screen.set_quiz_question(sq)

        elif msg_type == "quiz.loaded":
            quiz_title = message.get("quiz_title", "Untitled Quiz")
            logger.debug(f"Quiz loaded: {quiz_title}")
            msg = f"Quiz '{quiz_title}' loaded. Waiting for host to start..."
            screen.append_chat("System", msg)

        elif msg_type == "answer.recorded":
            # Optional: lock UI or log confirmation
            logger.debug("Answer recorded by server.")

        elif msg_type == "quiz.finished":
            screen.end_quiz()

        elif msg_type == "lobby.update":
            logger.debug("[Student Interface] Updating player list from server.")
            plist = message.get("players", [])
            rmved = message.get("removed")
            added = message.get("added")
            if rmved:
                # screen.append_chat("System", f"'{rmved}' has left the session.")
                screen.append_rainbow_chat("System", f"'{rmved}' has left the session.")
            elif added:
                # screen.append_chat("System", f"{added} has joined the session.")
                screen.append_rainbow_chat("System", f"'{added}' has joined the session.")
            screen.players = message.get("players", [])
            screen._rebuild_leaderboard()

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
        logger.debug(f"[HostInterface] Received message: {message}")
        
        # check if screen is available

        ############################################
        #    Process events for login screen first
        ############################################
        
        msg_type = message.get("type")
        if msg_type == "welcome":
            logger.debug("[HostInterface] Host contacted server successfully.")
            screen = self.get_screen("login")
            if not screen:
                logger.debug("[HostInterface] Login screen not available, ignoring title update.")
            else:
                screen.title = f"Contacted server as {self.username}"
                screen.sub_title = f"Creating Session {self.session_id}"
                await self.send_create()
            return
            
        elif msg_type == "session.created":
            logger.info(f"[HostInterface] Host created {self.session_id} successfully.")
            # self.ready_event.set()
            await self.app.push_screen("main", wait_for_dismiss=False)
            screen = self.get_screen("main")
            screen.title = f"Hosting as {self.username}"
            screen.sub_title = f"Session: {self.session_id}"
            # screen.append_chat("System", f"Session {self.session_id} created successfully.")
            return
       
        ############################################
        #    Process events for main screen
        ############################################
       
        screen = self.get_screen("main")
        if not screen:
            self.pending_events.append(message)
            logger.debug(f"[HostInterface] Screen not available, queuing event.")
            return
        
        if msg_type == "chat":
            msg = message.get("msg", "")
            p = message.get("player_id", "Host")
            screen.append_chat(p, msg)
            
        elif msg_type == "lobby.update":
            logger.debug("[Host Interface] Updating player list from server.")
            plist = message.get("players", [])
            rmved = message.get("removed")
            added = message.get("added")
            if rmved:
                screen.append_chat("System", f"'{rmved}' has left the session.")
                # screen.append_rainbow_chat("System", f"{rmved} has left the session.")
            elif added:
                # screen.append_chat("System", f"'{added}' has joined the session.")
                screen.append_rainbow_chat("System", f"{added} has joined the session.")
            screen.players = message.get("players", [])
            screen._rebuild_leaderboard()
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

        
    # async def wait_until_create(self, timeout: float = 10.0) -> bool:
    #     """Wait until the session has been created (or timeout)."""
    #     try:
    #         logger.debug("Waiting for created message to arrive...")
    #         await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
    #         return True
    #     except asyncio.TimeoutError:
    #         logger.debug(f"Timed out waiting for session creation after {timeout} seconds.")
    #         return False