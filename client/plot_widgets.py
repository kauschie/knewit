from textual_plotext import PlotextPlot
from textual.reactive import reactive

class _BasePlot(PlotextPlot):
    _pending: bool = False
    
    def replot(self) -> None:
        if self._pending:
            return
        self._pending = True
        
        def _do():
            self._pending = False
            self._draw()
            self.refresh()
            
        # run after the *next* refresh/layout
        self.call_after_refresh(_do)
    
    # redraw on resize
    def on_resize(self) -> None:
        self.replot()
        
class AnswerHistogramPlot(_BasePlot):
    """Plot showing answer distribution histogram."""
    labels = reactive(tuple(), init=False) # e.g., ("A", "B", "C", "D", "E")
    counts = reactive(tuple(), init=False) # e.g., (5, 10, 3, 0, 2), same length as labels
    
    def on_mount(self) -> None:
        self.labels = tuple()
        self.counts = tuple()
        self.replot()
        
    def reset_question(self, labels: list[str]) -> None:
        self.labels = tuple(labels)
        self.counts = tuple(0 for _ in labels)
        
    def bump(self, idx: int) -> None:
        if 0 <= idx < len(self.counts):
            counts = list(self.counts)
            counts[idx] += 1
            self.counts = tuple(counts)

    def watch_labels(self, _old: tuple, new: tuple) -> None:
        self.replot()

    def watch_counts(self, _old: tuple, new: tuple) -> None:
        self.replot()

    def _draw(self) -> None:
        plt = self.plt
        plt.clear_data()
        plt.title("Current Question - Answers")
        plt.xlabel("Choice")
        plt.ylabel("Count")
        if not self.labels or not self.counts:
            return
        plt.bar(list(self.labels), list(self.counts))
        plt.ylim(0, max(self.counts) + 1)

class PercentCorrectPlot(_BasePlot):
    percents = reactive(tuple(), init=False) # e.g., (50.0, 75.0, 100.0), one per question

    def on_mount(self) -> None:
        self.percents = tuple()
        self.replot()
    
    # public API
    def append_result(self, percent_correct: float) -> None:
        p = max(0.0, min(100.0, percent_correct))
        self.percents = (*self.percents, p) # should trigger watch method
        
    def set_series(self, percents: list[float]) -> None:
        self.percents = tuple(max(0.0, min(100.0, float(p))) for p in percents)

    # watcher
    def watch_percents(self, _old, _new) -> None:
        self.replot()
    
    def _draw(self) -> None:
        plt = self.plt
        plt.clear_data()
        n = len(self.percents)
        xs = list(range(1, n + 1))
        if xs:
            plt.plot(xs, list(self.percents), marker="hd")
        plt.title("% Correct by Question")
        plt.xlabel("Question #")
        plt.ylabel("% Correct")
        plt.ylim(0, 100)
        plt.xlim(0, max(1, n+1))
        xticks = list(range(0, max(2, n + 2)))
        plt.xticks(xticks)

