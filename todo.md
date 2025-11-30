## TODO

### 🐛 Bug Fixes & Stability
- [x] **Fix Leaderboard Crash:** Implemented "Safety Slice & Pad" in `_rebuild_leaderboard` (Host & Student) to prevent `DataTable` crashes when server history mismatches client columns.
- [x] **Fix Duplicate Scoring:** Made `server.close_question_scoring` idempotent to prevent double-counting points.
- [x] **Fix Duplicate Plotting:** Updated `HostUI` to prevent appending duplicate data points to the % Correct graph.
- [x] **Reset History on Load:** Ensured `QuizSession.load_quiz` clears `player.round_scores` to prevent old data from polluting new games.
- [x] **Fix Off-by-One Error:** Synchronized round indexing between Host (1-based) and Student (0-based) UIs.

### 🚀 Features & Enhancements
- [ ] **Config Persistence:** Create a `config_manager.py` to save/load User ID and Session ID to a local file (avoid re-typing login details).
- [ ] **Orchestrator Integration:** Move game logic (timers, state transitions) from `app.py` and `host_ui.py` into `server/quiz_orchestrator.py` to centralize authority.
- [ ] **Unified App Entry:** Combine Host and Student clients into a single entry point (e.g., `python client/main.py`) with a role selection screen.
- [ ] **Server-Side Timer Enforcement:** Enforce strict submission windows on the server (currently visual-only on client).

### 🧪 Testing & Optimization
- [ ] **Lobby Broadcast Optimization:** Refactor `broadcast_lobby` to use a background ticker (debounce/throttle) to reduce network noise from high-frequency pings/joins.
- [ ] **Stress Testing:** Test with multiple concurrent connections to verify `ws_client` stability.
- [ ] **Remote Testing:** Implement automated tests for the full client-server flow.

### ✅ Completed Features
- [x] **Client UI:** Implemented comprehensive Textual interfaces for Host and Student.
- [x] **Quiz Creator:** Built and integrated `QuizCreator` TUI into the Host interface.
- [x] **Chat:** Implemented broadcasting, rich text rendering, and separate channels.
- [x] **Basic Game Flow:** Implemented `start_quiz`, `next_question`, and `end_question` flows.
- [x] **WS Reliability:** Fixed `ws.send` calls and implemented auto-reconnection in `ws_client.py`.
- [x] **Player Management:** Implemented kicking, muting, and stale player detection.
- [x] **Quiz Persistence:** Saving and loading JSON quizzes works.