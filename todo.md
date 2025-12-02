# Project Status & TODO

## 🚀 Up Next (Immediate Priorities)
- [ ] **Argument Parsing / Auto-Login:** Implement `argparse` logic in `student_ui.py` to accept CLI arguments or Environment Variables (e.g., `KNEWIT_USER`, `KNEWIT_SESSION`) for one-click login scripts.
- [ ] **Config Persistence:** Create a `config_manager.py` to save/load the last used Server IP, Port, and Username to a local JSON file (improves UX for repeated testing).
- [ ] **Stress Testing:** Validate `ws_client` stability with multiple concurrent connections (e.g., 30+ simulated students).

## 🏗️ Architecture & Refactoring
- [ ] **Orchestrator Integration:** Move game flow logic (state transitions, timer management) from `server/app.py` and `client/host_ui.py` into `server/quiz_orchestrator.py` to centralize authority.
- [ ] **Server-Side Timer Enforcement:** Currently, the server calculates scores based on client-reported `elapsed` time. Implement server-side start/stop timestamps to prevent "time travel" cheating.
- [ ] **Unified App Entry:** Create a single entry point (e.g., `python client/main.py`) with a TUI role selection screen (Host vs. Student).

## ✅ Completed Features
### Core Systems
- [x] **Lobby System:** Real-time player list updates with background broadcast ticker (3s interval) to reduce network noise.
- [x] **Player Controls:** Implemented Host controls for **Kicking** (with Ban List protection) and **Muting** players.
- [x] **Connection Reliability:** Fixed "Zombie Connection" race conditions and implemented robust auto-reconnection logic.
- [x] **Logging:** Separated logging into `host.log` and `student.log`, silenced third-party library noise, and removed root logger conflicts.

### Gameplay & Scoring
- [x] **Time-Based Scoring:** Implemented linear time-decay scoring (Max Points → 50%) based on elapsed time.
- [x] **Scoring Logic:** Separated data collection (`record_answer`) from logic (`close_question_scoring`) to prevent race conditions and duplicate point glitches.
- [x] **Leaderboard:** Fixed crashes caused by column/data mismatches and "Off-by-One" indexing errors between Host and Student UIs.
- [x] **Host Auto-End:** Host UI automatically triggers "End Question" when the local timer hits 0.0.

### Client UI
- [x] **UI Overhaul:** Standardized Host and Student UIs with a responsive 2x2 grid layout (Timer, Preview, Leaderboard, Chat).
- [x] **Client Resilience:** Integrated `SessionLogger` ("Flight Recorder") to log all events locally for crash recovery/analysis.
- [x] **Quiz Creator:** Fully functional TUI for creating and saving JSON quizzes.
- [x] **Chat System:** Rich text chat with separate channels for System, Host, and Users.