# Progress Presentation – Distributed Quiz Platform (Knewit)

This overview explains what our software is, the distributed approaches it uses, the main classes/functions, example use-cases, and concrete code examples. It also shows how we can evolve the system to be more scalable, secure, and consistent in the face of communication errors.

## What it is (quick tour)

- Real-time, distributed quiz platform
  - Server: FastAPI + WebSockets (`server/app.py`)
  - Clients: Textual terminal apps for host and students (`client/host_tui.py`, `client/student_tui.py`)
  - Transport: Reusable async WebSocket client (`client/ws_client.py`)
  - Data model: Dataclasses for quiz/state (`server/quiz_types.py`)
  - Storage: Quizzes saved as JSON in `quizzes/`
- Communication model
  - Event-driven message passing over WebSockets
  - Broadcast per-session to all connected clients
  - Heartbeat ping/pong with latency measurement; automatic client reconnection

## Supported distributed computing approaches

- Message-based, event-driven coordination
  - Clients send typed JSON messages (e.g., `session.create`, `session.join`, `answer.submit`)
  - Server routes messages, mutates in-memory session state, and broadcasts events (`lobby.update`, `question.next`, `histogram`, `quiz.finished`)
- Asynchronous concurrency (asyncio)
  - Server websockets and background heartbeat task
  - Client reconnect loop, receiver/sender tasks with queues
- Pub-sub style broadcasting (in-process)
  - Helper `broadcast(session, payload)` fans out to all session connections
- Fault tolerance primitives
  - Heartbeat pings and client-side reconnects; server updates latency and last_seen

## Main components and responsibilities

- `server/quiz_types.py`
  - `Question` (prompt, 4 options, correct_idx)
  - `Player` (player_id, name, score; latency metadata)
  - `Quiz` (title, questions; save/list JSON)
  - `QuizSession` (players, connections, state, current question, histograms)
  - Global in-memory registry and helpers: `create_session`, `get_session`, `delete_session`

- `server/app.py`
  - FastAPI app exposing `GET /ping` and `WS /ws`
  - WebSocket endpoint handles messages:
    - Session: `session.create`, `session.join`, `session.joined`, `session.closed`
    - Quiz: `quiz.load`, `quiz.saved`, `quiz.list`, `quiz.start`, `question.next`, `quiz.finished`
    - Answers: `answer.submit`, `answer.recorded`, `histogram`
    - Admin: `player.kick`
    - Heartbeat: server `ping` → client `pong`
  - Helpers: `broadcast(session, payload)`, `broadcast_lobby(session)`, `ping_loop()`

- `client/ws_client.py`
  - `WSClient(url, on_event)`
    - Maintains a single persistent connection
    - Auto-reconnect with capped backoff
    - Replies to `ping` with `pong`
    - Outbound send queue and async `send()` API

- `client/host_tui.py`
  - Host creates session, loads/starts quiz, advances questions, kicks players
  - Displays lobby, question prompt, histogram

- `client/student_tui.py`
  - Student joins session, receives questions, submits answers, sees results/leaderboard

- Quiz tools
  - `client/quiz_creator.py` to build quizzes (title + questions)
  - `client/quiz_selector.py` to browse saved quizzes

## Example problems this software solves

- Classroom live quizzes and formative assessments
- Remote team icebreakers and learning checks
- Training sessions with instant feedback via histograms
- Interactive polls where options are revealed and tracked in real-time

## End-to-end example: minimal client using WSClient

Below is a simple headless client that joins a session and prints events. It uses the existing `WSClient` class.

```python
# examples/minimal_client.py
import asyncio
import json
from client.ws_client import WSClient

SERVER = "ws://127.0.0.1:8000"
SESSION = "demo"        # share the session code from the host UI
NAME = "bot-alice"       # bot name

async def on_event(msg: dict):
    print("event:", msg)
    t = msg.get("type")
    if t == "welcome":
        await client.send({
            "type": "session.join",
            "session_id": SESSION,
            "name": NAME,
        })
    elif t == "question.next":
        # Always choose option 0 just for demonstration
        await client.send({"type": "answer.submit", "answer_idx": 0})

async def main():
    global client
    url = f"{SERVER}/ws?player_id={NAME}&is_host=false"
    client = WSClient(url, on_event)
    # Run until canceled (Ctrl+C)
    await client.start()

if __name__ == "__main__":
    asyncio.run(main())
```

How it interacts with the server:
- On `welcome` from the server, it sends `session.join`.
- On `question.next`, it submits an answer. The server responds with
  `answer.recorded` and updates the histogram.

## Server-side message flow (simplified)

```python
# server/app.py (selected snippets)
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, player_id: str = "anon", is_host: str = "false"):
    await ws.accept()
    is_host_bool = is_host.lower() == "true"
    # ... send "welcome" ... read loop ...
    if msg_type == "session.create" and is_host_bool:
        session = create_session(player_id)
        session.connections[player_id] = ws
        await ws.send_text(json.dumps({"type": "session.created", "session_id": session.id}))

    elif msg_type == "session.join":
        session = get_session(data["session_id"])  # validate
        session.add_player(player_id, data["name"]) 
        session.connections[player_id] = ws
        await ws.send_text(json.dumps({"type": "session.joined", "session_id": session.id}))
        await broadcast_lobby(session)

    elif msg_type == "quiz.start" and is_host_bool:
        if session.start_quiz():
            q = session.next_question()
            await broadcast(session, {
                "type": "question.next",
                "prompt": q.prompt,
                "options": q.options,
                "question_num": session.current_question_idx + 1,
                "total_questions": len(session.quiz.questions),
            })

    elif msg_type == "answer.submit":
        correct = session.record_answer(player_id, int(data.get("answer_idx", 0)))
        await ws.send_text(json.dumps({"type": "answer.recorded", "correct": correct}))
        bins = [session.answer_counts.get(i, 0) for i in range(4)]
        await broadcast(session, {"type": "histogram", "bins": bins})
```

## How to scale: performance, security, and consistency

Below are drop-in style changes and patterns to evolve the system. Items marked “implemented” already exist; others are proposed with code sketches.

### Performance and scalability

1) Use concurrent broadcast fan-out (micro-optimization)

```python
# server/app.py – replace sequential sends with concurrent fan-out
async def broadcast(session: QuizSession, payload: dict):
    data = json.dumps(payload)
    tasks = []
    dead = []
    for pid, ws in list(session.connections.items()):
        async def send_one(pid=pid, ws=ws):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(pid)
        tasks.append(asyncio.create_task(send_one()))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    for pid in dead:
        session.connections.pop(pid, None)
```

2) Multi-process workers behind a load balancer (requires shared state)

- Current state is in-process per worker. To scale horizontally, store session state in Redis and use pub/sub for broadcasts.
- Sticky sessions are a quick workaround, but true scaling needs shared state.

Redis sketch:

```python
# server/state.py (conceptual)
import aioredis

redis = await aioredis.from_url("redis://localhost")
SESSIONS_KEY = "knewit:sessions"  # hash or JSON per session

async def save_session(session):
    await redis.hset(SESSIONS_KEY, session.id, json.dumps(session.to_dict()))

async def get_session_dict(session_id):
    data = await redis.hget(SESSIONS_KEY, session_id)
    return json.loads(data) if data else None

# pub/sub channel per session for fan-out across workers
SESSION_CH = lambda sid: f"knewit:ch:{sid}"
```

3) Debounce high-frequency lobby updates

- Batch player changes and broadcast at most every N ms during churn.
- Reduces redundant updates with large numbers of clients.

### Security

1) Require an auth token (shared secret or JWT) for WS connections

```python
# server/app.py – validate a token in query params
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, player_id: str = "anon", is_host: str = "false", token: str | None = None):
    await ws.accept()
    if token != os.environ.get("QUIZ_TOKEN"):
        await ws.close(code=4401)  # unauthorized
        return
    # proceed...
```

2) TLS termination and WebSocket security

- Run behind a reverse proxy (nginx/Traefik) to expose `wss://`.
- Set CORS to the allowed domains only (currently `*`).
- Tune `max_size` in `WSClient` / server to limit payloads; add server-side size checks.

3) Rate limiting and input validation

- Add request/message rate limiting per connection to mitigate abuse.
- Validate message schema (types and required fields) before mutating state.

### Consistency and fault tolerance (dropped messages, network failures)

Implemented today:
- Heartbeat pings and client pong → server updates `last_seen` and `latency_ms`.
- Client auto-reconnect with exponential backoff.
- Server-side single-answer rule per question (idempotency for `answer.submit`).

Proposed improvements:

1) Idempotent, at-least-once messaging with acknowledgements

```python
# Client: attach a message_id; server: keep a per-player ack set per question
msg = {"type": "answer.submit", "answer_idx": 2, "msg_id": "uuid-123"}

# Server inside ws loop
seen = session.__dict__.setdefault("seen_msg_ids", set())
if data.get("msg_id") in seen:
    # re-send prior confirmation or ignore
    await ws.send_text(json.dumps({"type": "answer.recorded", "duplicate": True}))
    continue
seen.add(data.get("msg_id"))
```

2) Re-synchronization snapshot on reconnect

- On client reconnect, server sends `session.snapshot` with lobby state, current question, and histogram so the client can rebuild UI.

```python
# Example snapshot payload
{
  "type": "session.snapshot",
  "state": "active",
  "players": [...],
  "question": {"prompt": "...", "options": ["A","B","C","D"], "num": 3, "total": 10},
  "histogram": [1,4,2,0]
}
```

3) Timeouts and retries for critical actions

- For operations like `quiz.load` and `quiz.save`, send explicit `...ok`/`...error` replies and have clients retry if no ack within a timeout.

## How to run locally (quick reference)

```bash
# 1) Start the server (one terminal)
uvicorn server.app:app --host 0.0.0.0 --port 8000 --log-level debug

# 2) Host UI (second terminal)
python client/host_tui.py

# 3) Student UI (third terminal, run multiple if desired)
python client/student_tui.py

# 4) Optional: create a quiz
python client/quiz_creator.py
```

Notes:
- By default the server maintains sessions in-memory. For multiple processes/hosts, adopt the Redis-backed sketch above.
- The clients will reconnect automatically if the network blips; latency shows in lobby when pings are received.

## Roadmap (selected next steps)

- Shared session state and pub/sub via Redis for true horizontal scaling
- Message schema validation and structured error codes
- Optional JWT-based authentication and `wss://` deployment profile
- Snapshot-on-reconnect and idempotent message IDs
- Debounced/batched broadcasts and metrics for back-pressure
