# chat_markdown_stream.py
from __future__ import annotations
from typing import List
from datetime import datetime
from collections import deque

from textual.containers import VerticalScroll
from textual.widgets import Markdown, RichLog
from textual.events import Resize
from rich.text import Text
from common import logger


class MarkdownChat(VerticalScroll):
    """Scrollable Markdown chat using Markdown.get_stream() with FIFO and batching."""

    MAX_LINES = 20

    def on_mount(self) -> None:
        self._md = Markdown("", id="chat-md")
        self._lines: List[str] = []       # full logical buffer (max 20)
        self._pending = False             # coalesce multiple appends per frame
        self.mount(self._md)

    # --- public API ---------------------------------------------------------
    def clear_feed(self) -> None:
        self._lines.clear()
        self._pending = False
        self._md.update("")
        self.scroll_home(animate=False)

    def append(self, user: str, msg: str) -> None:
        ts = datetime.now().strftime("[%H:%M:%S]")
        # self._lines.append(f"{ts} **{self._esc(user)}**: {self._esc(msg)}")
        self._lines.append(f"{ts} **{user}**: {msg}")
        if len(self._lines) > self.MAX_LINES:
            # prune from head; mark as needing a full render
            self._lines = self._lines[-self.MAX_LINES:]

        if not self._pending:
            self._pending = True
            self.call_after_refresh(self._flush)

    # --- internals ----------------------------------------------------------
    def _flush(self) -> None:
        self._pending = False
        self._md.update("\n\n".join(self._lines))
        # auto-scroll if we're already near the bottom
        # (prevents yanking if user scrolled up)
        near_bottom = self.scroll_y >= (self.size.height - 2)
        if near_bottom:
            self.scroll_end(animate=False)

    @staticmethod
    def _esc(t: str) -> str:
        # Minimal escaping so user input can’t break formatting
        return (t.replace("\\", "\\\\")
                 .replace("*", "\\*").replace("_", "\\_")
                 .replace("`", "\\`").replace("[", "\\[")
                 .replace("]", "\\]").replace("<", "\\<")
                 .replace(">", "\\>"))

class RichLogChat(RichLog):
    """Scrollable RichLog chat with FIFO and batching."""
    wrap = True
    markup = True
    auto_scroll = True
    min_width = 1        # let it shrink to container

    CSS = """
    RichLogChat {
        border: solid $boost 50%;
        background: $boost 10%;
        height: 1fr;
        width: 1fr;
        # overflow-x: hidden;
    }
    """    

    MAX_LINES = 200


    def on_mount(self) -> None:
        self._lines: List[str] = []       # full logical buffer (max 20)
        self.history = deque(maxlen=self.MAX_LINES)

    def append_chat(self, user: str, msg: str, role: str | None = None) -> None:
        prefix = Text(datetime.now().strftime("[%H:%M:%S] "), style="dim")
        prefix.append(user, style={"host":"bold magenta","mod":"bold cyan","sys":"bold yellow"}.get(role,"bold green"))
        prefix.append(": ")
        
        try:
            t = Text.from_markup(msg)
        except Exception as e:
            logger.error(f"Error parsing markup in chat message: {e}")
            t = Text(msg)

        line = Text.assemble(prefix, t)
        self.history.append(line)
        # no width= -> allow expand/shrink to work
        self.write(line, expand=True, shrink=True)

    def on_resize(self, _: Resize) -> None:
        # reflow at the new width
        self.clear()
        for line in self.history:
            self.write(line, expand=True, shrink=True)

