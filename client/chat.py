# chat_markdown_stream.py
from __future__ import annotations
from typing import List
from datetime import datetime

from textual.containers import VerticalScroll
from textual.widgets import Markdown


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
