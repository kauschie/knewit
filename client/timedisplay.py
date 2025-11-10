from time import monotonic

from textual.widgets import Static
from textual.reactive import reactive


class TimeDisplay(Static):
    """A countdown timer widget (MM:SS.ss)."""

    # total duration (seconds) and remaining time are reactive so UI updates automatically
    duration: float = reactive(0.0)
    remaining: float = reactive(0.0)

    def on_mount(self) -> None:
        # internal bookkeeping
        self._elapsed_base = 0.0       # elapsed time from previous runs (paused total)
        self._t0 = 0.0                 # start time of current run (monotonic)
        self._running = False

        # 60 FPS-ish update; starts paused
        self._ticker = self.set_interval(1 / 60, self._tick, pause=True)

        # initial display
        self._render_remaining()

    # ----- public API -------------------------------------------------------

    def start(self, seconds: float | None = None) -> None:
        """Start (or restart) the countdown. Optionally set a new duration in seconds."""
        if seconds is not None:
            self.duration = float(seconds)
        # reset elapsed and set remaining to full duration
        self._elapsed_base = 0.0
        self.remaining = self.duration
        # run
        self._t0 = monotonic()
        self._running = True
        self._ticker.resume()

    def resume(self) -> None:
        """Resume after a pause (keeps remaining time)."""
        if self.remaining <= 0 or self._running:
            return
        self._t0 = monotonic()
        self._running = True
        self._ticker.resume()

    def stop(self) -> None:
        """Pause the countdown."""
        if not self._running:
            return
        self._elapsed_base += monotonic() - self._t0
        self._running = False
        self._ticker.pause()
        # force a recompute to keep remaining in sync
        self._recompute_remaining()

    def reset(self, seconds: float | None = None) -> None:
        """Reset to full duration (optionally change duration)."""
        if seconds is not None:
            self.duration = float(seconds)
        self._elapsed_base = 0.0
        self._running = False
        self._ticker.pause()
        self.remaining = self.duration

    # ----- internals --------------------------------------------------------

    def _tick(self) -> None:
        """Timer callback while running."""
        if not self._running:
            return
        self._recompute_remaining()
        if self.remaining <= 0.0:
            # hit zero—stop cleanly
            self._running = False
            self._ticker.pause()
            self.remaining = 0.0  # clamp

    def _recompute_remaining(self) -> None:
        elapsed = self._elapsed_base + (monotonic() - self._t0 if self._running else 0.0)
        self.remaining = max(0.0, self.duration - elapsed)

    def watch_remaining(self, value: float) -> None:
        """Reactive hook: update the label whenever remaining changes."""
        self._render_remaining()

    def _render_remaining(self) -> None:
        # Format MM:SS.ss
        minutes, seconds = divmod(self.remaining, 60)
        self.update(f"{int(minutes):02d}:{seconds:05.2f}")
