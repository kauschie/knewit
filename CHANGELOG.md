# Knewit Quiz System - Development Changelog

**Current Version:** v0.5.0 (Beta)
**Last Updated:** November 30, 2025
**Technology Stack:** FastAPI (WebSocket server), Textual (TUI clients), Python 3.12

---

## 🚀 New in v0.5.0 (Latest)

### 1. UI Overhaul & Standardization
- **Unified 2x2 Grid Layout:** Both Host and Student interfaces now feature a consistent, responsive layout:
  - **Top Left:** Active Question & Timer.
  - **Bottom Left:** Quiz Preview (Host) or Answer Buttons (Student).
  - **Top Right:** Live Leaderboard.
  - **Bottom Right:** Rich Text Chat.
- **Responsiveness:** Fixed widget resizing bugs (`min-width` constraints) to ensure the TUI scales gracefully on smaller terminal windows.
- **Dynamic Controls:** Host buttons now transition states automatically (`Lobby` → `Ready` → `Active`).

### 2. Advanced Scoring Engine
- **Server-Side Authority:** Moved scoring logic from client-reported timing to server-calculated elapsed time to prevent cheating.
- **Time-Decay Algorithm:** Implemented a linear decay scoring model:
  - **Max Points:** 10 (Default)
  - **Min Points:** 5 (50% of Max)
  - **Mechanism:** Faster answers earn significantly more points.
- **Accuracy Tracking:** Added a specific `correct_count` metric separate from the total score, displayed in a new column on the leaderboard.

### 3. Client Resilience ("Flight Recorder")
- **Session Logger:** Implemented a local JSON-based logging system (`client/session_log.py`) that records every event (Question Received, Answer Submitted, Chat).
- **Crash Recovery:** Clients now detect incomplete session logs on startup, notifying the user and enabling future auto-reconnection features.

### 4. Stability & Bug Fixes
- **Zombie Connections:** Fixed a race condition where kicking a player would leave a "ghost" connection that prevented the user from rejoining. Implemented a strict **Ban List** (`kicked_players`) on the server.
- **Leaderboard Crashes:** Fixed a critical bug where the client crashed if the server sent score history for rounds not yet rendered. Implemented "Safety Slice & Pad" logic in `_rebuild_leaderboard`.
- **Duplicate Data:** Fixed issues where the Host UI would double-count scores or plot duplicate points on the graph if the "End Question" event fired multiple times.
- **Logging Isolation:** Resolved root logger conflicts. Host and Student now write to separate, clean log files (`logs/host.log`, `logs/student.log`) with third-party library noise silenced.

---

## 📜 v0.1.0 - v0.4.0 (Previous History)

### Session Management
- **Architecture:** Migrated from direct connections to a Session-based architecture with unique 6-character IDs.
- **Lobby System:** Real-time player list updates, join/leave notifications, and "Kick/Mute" controls for the Host.
- **Persistence:** In-memory session storage with automatic cleanup on Host disconnect.

### Quiz Management
- **JSON Persistence:** Quizzes are saved/loaded from the `quizzes/` directory.
- **Quiz Creator:** Built a dedicated TUI (`quiz_creator.py`) for building quizzes with up to 20 questions.
- **Host Controls:** "Start Quiz", "Next Question", and "Stop Quiz" workflow.

### Core Communication
- **WebSocket Protocol:** Established robust JSON message types:
  - `session.create`, `session.join`, `lobby.update`
  - `question.next`, `answer.submit`, `question.results`
- **Heartbeat:** Implemented a Ping/Pong loop to track latency and detect stale connections.
- **Chat:** Rich text chat system with distinct styling for System, Host, and User messages.

### Visualization
- **Histograms:** Integrated `textual-plotext` to render live answer frequency charts on the Host dashboard.
- **Leaderboards:** `DataTable` implementation sorting players by total score in real-time.