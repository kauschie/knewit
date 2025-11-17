# client/common.py

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Optional

from client.ws_client import WSClient


@dataclass
class SessionModel:
    server_ip: str = ""
    server_port: int = 0
    session_id: str = ""
    username: str = ""
    password: str = ""

    ws: Optional[WSClient] = field(default=None, init=False)
    is_connected: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionModel":
        return cls(
            server_ip=data.get("server_ip", ""),
            server_port=data.get("server_port", 0),
            session_id=data.get("session_id", ""),
            username=data.get("username", ""),
            password=data.get("password", "")
        )

    async def connect(self) -> bool:
        """Attempt to connect and initialize WebSocket session."""
        if not self.is_valid():
            print("[SessionModel] Invalid connection parameters.")
            return False

        url = f"ws://{self.server_ip}:{self.server_port}/ws?session_id={self.session_id}&username={self.username}"
        self.ws = WSClient(url=url, on_event=self.on_event)

        try:
            await self.ws.connect()
            self.is_connected = True
            print(f"[SessionModel] Connected to {url}")
            return True
        except Exception as e:
            print(f"[SessionModel] Connection failed: {e}")
            self.ws = None
            self.is_connected = False
            return False

    async def send(self, msg: dict):
        if self.ws and self.is_connected:
            await self.ws.send(msg)

    async def disconnect(self):
        if self.ws:
            await self.ws.disconnect()
            self.is_connected = False

    def is_valid(self) -> bool:
        return (
            self.server_ip and
            isinstance(self.server_port, int) and
            0 < self.server_port < 65536 and
            self.session_id and
            self.username
        )

    async def on_event(self, message: dict):
        """Override this in app to respond to incoming server events."""
        logger.debug(f"[SessionModel] Unhandled event: {message}")




logging.basicConfig(filename='logs/host_log.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.debug("Logger module loaded from common.")


