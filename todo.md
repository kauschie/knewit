## TODO

### 🚀 Features & Enhancements
- [ ] **Host Auto-End:** Trigger `end_question` automatically when the Host UI timer hits zero.
- [ ] **Config Persistence:** Create a `config_manager.py` to save/load User ID and Session ID to a local file (avoid re-typing login details).
- [ ] **Orchestrator Integration:** Move game logic (timers, state transitions) from `app.py` and `host_ui.py` into `server/quiz_orchestrator.py` to centralize authority.
- [ ] **Unified App Entry:** Combine Host and Student clients into a single entry point (e.g., `python client/main.py`) with a role selection screen.
- [ ] **Server-Side Timer Enforcement:** Enforce strict submission windows on the server (currently visual-only on client).

### 🧪 Testing & Optimization
- [ ] **Stress Testing:** Test with multiple concurrent connections to verify `ws_client` stability.
- [ ] **Remote Testing:** Implement automated tests for the full client-server flow.

### ✅ Completed
- [x] **Lobby Broadcast Optimization:** Refactored `broadcast_lobby` to use a background ticker (3s interval) to reduce network noise.
- [x] **Logging System:** Fixed logging to write to separate `host.log` and `student.log` files and silenced third-party library noise.
- [x] **Player Controls:** Implemented robust Kicking (with Ban List) and Muting functionality.
- [x] **Connection Stability:** Fixed "Zombie Connection" race conditions and client state transitions on kick/disconnect.
- [x] **Leaderboard Logic:** Fixed crashes due to column mismatches and off-by-one errors.
- [x] **Scoring Logic:** Fixed duplicate scoring and plotting bugs.
- [x] **Client UI:** Implemented comprehensive Textual interfaces for Host and Student.
- [x] **Quiz Creator:** Built and integrated `QuizCreator` TUI.