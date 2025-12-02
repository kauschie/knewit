# Knewit: Terminal-Based Multiplayer Quiz Platform

**Knewit** is a robust, real-time multiplayer quiz system that runs entirely in your terminal. Built with **Textual** for the TUI and **FastAPI** for the WebSocket server, it offers a "Kahoot-like" experience with live histograms, time-decay scoring, and chat functionality.

## 🌟 Key Features

### For Hosts (Teachers/Admins)
- **Lobby System:** Create sessions with unique codes. Manage players with **Kick** (Ban) and **Mute** controls.
- **Quiz Creator:** Interactive TUI to build, edit, and save quizzes to JSON.
- **Live Dashboard:**
  - **2x2 Grid Layout:** Simultaneous view of Timer, Question Preview, Leaderboard, and Chat.
  - **Real-Time Histogram:** Watch answer distribution update live as students vote.
  - **Leaderboard:** Tracks Score (Time-weighted) and Accuracy (Correct Count).
- **Game Control:** Start quiz, auto-advance questions, or manually stop the game.

### For Students (Players)
- **One-Click Join:** Connect via Session ID.
- **Resilient Client:** Includes a local "Flight Recorder" (Session Logger) that saves game history to disk, allowing context recovery if the app crashes.
- **Interactive UI:** Big-button answer selection, rich-text chat, and personal performance feedback (Rank/Score).

---

## 🛠️ Technology Stack
- **Frontend (TUI):** [Textual](https://textual.textualize.io/) (Python)
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **Communication:** WebSockets (AsyncIO)
- **Visualization:** [Textual-Plotext](https://github.com/Textualize/textual-plotext) for terminal-based charting

---

## 🚀 Getting Started

### 1. Installation
Ensure you have Python 3.12+ installed.

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

```

### 2. Running the Server

Start the WebSocket server. It handles session state, broadcasting, and scoring.

# Run on all interfaces (0.0.0.0) on port 49000
```bash
uvicorn server.app:app --host 0.0.0.0 --port 49000 --log-level info
```

### 3. Running the Host Client

Open a new terminal window.
```Bash

python client/host_ui.py

    Login as "Host".

    Click "Create Quiz" to make a new deck, or "Load Quiz" to pick an existing one.

    Click "Create Session" to open a lobby.
```

### 4. Running the Student Client

Open a new terminal (or distribute the executable).
```Bash

python client/student_ui.py

    Enter the Session ID displayed on the Host screen.

    Enter a Username and the Server IP (e.g., 127.0.0.1 or the Host's LAN IP).
```


### 5. Project Structure
knewit/
├── client/
│   ├── host_ui.py          # Teacher Interface (Lobby, Controls, Graphs)
│   ├── student_ui.py       # Student Interface (Answers, Chat)
│   ├── session_log.py      # Client-side "Flight Recorder"
│   ├── ws_client.py        # Robust WebSocket wrapper with auto-reconnect
│   └── widgets/            # Reusable TUI components (Timer, Chat, Plots)
├── server/
│   ├── app.py              # FastAPI Application & Route Handlers
│   ├── quiz_types.py       # Data Models & Scoring Logic
│   └── quiz_manager.py     # Game State Management
├── quizzes/                # JSON storage for saved quizzes
├── logs/                   # Application logs (host.log, student.log)
└── session_logs/           # Client-side game history (for recovery)


---

