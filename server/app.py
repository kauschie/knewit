# server/app_new.py
"""
Enhanced quiz server with lobby system, quiz creation, and session management.

Responsibilities:
- Exposes HTTP health-check `/ping`.
- Exposes WebSocket endpoint `/ws` (handles host vs student roles).
- Routes JSON messages (examples: `session.create`, `session.join`, `quiz.load`,
    `quiz.save`, `quiz.start`, `answer.submit`) and performs server-side session
    management using typed dataclasses from `knewit/server/quiz_types.py`.
- Provides helpers to broadcast session-level messages to connected clients.

Notes / operational caveats:
- Session state is kept in-process (see `quiz_types.py`). For multi-worker or
    multi-host deployments you must migrate state to an external store (Redis, DB)
    or implement a shared coordination layer.
- Some filesystem operations (saving quizzes) are synchronous; they are off-
    loaded to a thread to avoid blocking the event loop.
- The app starts a background ping loop at startup to emit application-level
    "ping" messages to connected clients; clients should reply with `pong` so
    the server can measure latency.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path
# Add server directory to path so we can import quiz_types
sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))

from quiz_types import (
    QuizSession, Quiz, Question, QuizState, StudentQuestion,
    create_session, get_session, delete_session
)
import logging
logging.basicConfig(filename='logs/server.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.debug("Logger module loaded from app.py")


# Heartbeat config
PING_INTERVAL = 20


# Seconds of silence before we declare a player "stale"
PLAYER_TIMEOUT = 60

# Seconds of silence before we declare a player "removed" and drop them
HARD_TIMEOUT = 300


# Background task reference
_ping_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan handler."""
    global _ping_task
    await printlog("[lifespan] starting")
    
    _ping_task = asyncio.create_task(ping_loop())
    
    try:
        yield
    finally:
        await printlog("[lifespan] shutting down")
        if _ping_task:
            _ping_task.cancel()
            await asyncio.gather(_ping_task, return_exceptions=True)
        await printlog("[lifespan] bye")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
def health_check():
    """Health check endpoint."""
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(
    ws: WebSocket,
    session_id: str = "demo",
    player_id: str = "anon",
    is_host: str = "false"
):
    """WebSocket endpoint for quiz sessions."""
    await ws.accept()
    is_host_bool = is_host.lower() == "true"
    session: QuizSession | None = None
    session_id: str | None = None
    
    await printlog(f"[ws] connect player={player_id} is_host={is_host_bool}")
    
    try:
        # Send welcome
        await ws.send_text(json.dumps({
            "type": "welcome",
            "player_id": player_id,
            "is_host": is_host_bool # prob don't need anymore
        }))
        
        # Main message loop
        while True:
            await printlog(f"[ws] waiting for player={player_id} message")
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            await printlog(f"[ws] recv player={player_id} type={msg_type}")

            # Update last_seen on ANY inbound message (not only 'pong')
            if session and player_id in session.players:
                import time
                player = session.players.get(player_id)
                if player:
                    player.last_seen = time.time()
            
            # Heartbeat (client pong replies to our application-level ping)
            if msg_type == "pong":
                # Expect client to echo back the server ts we sent in ping.
                ts = data.get("ts")
                try:
                    ts = float(ts) if ts is not None else None
                except Exception:
                    ts = None

                if ts and session and player_id in session.players:
                    # Compute RTT (server_now - ts) in milliseconds
                    import time
                    now = time.time()
                    latency_ms = (now - ts) * 1000.0

                    player = session.players.get(player_id)
                    if player:
                        player.last_pong = now
                        player.latency_ms = latency_ms
                        player.last_seen = now
                        # Broadcast updated lobby so UIs can show latency next to names
                        await broadcast_lobby(session)

                        # If previously stale, mark active again
                        recovered = False
                        if player.status == "stale":
                            player.status = "active"
                            recovered = True
                            print(f"[recover] player={player_id} is active again in session={session.id}")
                        
                        if recovered:    
                            await broadcast_lobby(session)
                
                # Nothing more to do for heartbeat messages.
                continue
            
            # Session creation (host only)
            elif msg_type == "session.create" and is_host_bool:
                session = create_session(player_id)
                session_id = session.id
                session.connections[player_id] = ws
                
                await ws.send_text(json.dumps({
                    "type": "session.created",
                    "session_id": session_id
                }))
                await printlog(f"[session] created session_id={session_id} host={player_id}")
            
            # Join session
            elif msg_type == "session.join":
                await printlog(f"[session] player={player_id} joining session")
                session_id = data.get("session_id")
                name = data.get("name")
                
                if not session_id or not name:
                    await printlog(f"[session] join failed for player={player_id}, missing session_id or name") 
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Missing session_id or name"
                    }))
                    continue
                
                session = get_session(session_id)
                if not session:
                    await printlog(f"[session] join failed for player={player_id}, session_id={session_id} not found")
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Session not found"
                    }))
                    
                    continue
                
                # Add player
                player = session.add_player(player_id, name)
                if not player:
                    await printlog(f"[session] join failed for player={player_id}, name={name} already taken in session={session_id}")
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Name already taken"
                    }))
                    continue
                
                session.connections[player_id] = ws
                
                await ws.send_text(json.dumps({
                    "type": "session.joined",
                    "session_id": session_id,
                    "name": name
                }))
                # Broadcast updated lobby
                await broadcast_lobby(session)
                await printlog(f"[session] {name} joined session_id={session_id}")
                
            # Load quiz (host only)
            elif msg_type == "quiz.load" and is_host_bool and session:
                quiz_data = data.get("quiz")
                if quiz_data:
                    quiz = Quiz.from_dict(quiz_data)
                    session.load_quiz(quiz)
                    
                    await broadcast(session, {
                        "type": "quiz.loaded",
                        "quiz_title": quiz.title,
                        "num_questions": len(quiz.questions)
                    })
                    await printlog(f"[quiz] loaded quiz={quiz.title} in session={session_id}")

            
            # Start quiz (host only)
            elif msg_type == "quiz.start" and is_host_bool and session:
                if session.start_quiz():
                    # Send first question
                    question = session.next_question()
                    if question:
                        await broadcast(session, {
                            "type": "question.next",
                            "prompt": question.prompt,
                            "options": question.options,
                            "question_num": session.current_question_idx + 1,
                            "total_questions": len(session.quiz.questions)
                        })
                        await printlog(f"[quiz] started in session={session_id}")
                else:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "No quiz loaded"
                    }))
            
            # Next question (host only)
            elif msg_type == "question.next" and is_host_bool and session:
                question = session.next_question()
                if question:
                    sq = StudentQuestion.from_question(question)
                    sq["index"] = session.current_question_idx
                    sq["total"] = len(session.quiz.questions)
                    await broadcast(session, {
                        "type": "question.next",
                        "question": sq,
                        "duration": data.get("duration", 30)
                    })
                    
                else:
                    # Quiz finished
                    await broadcast(session, {
                        "type": "quiz.finished",
                        "leaderboard": [
                            {"name": p.name, "score": p.score}
                            for p in sorted(session.players.values(), key=lambda x: x.score, reverse=True)
                        ]
                    })
                    await printlog(f"[quiz] finished in session={session_id}")
            
            # Submit answer (students)
            elif msg_type == "answer.submit" and session:
                answer_idx = int(data.get("answer_idx", 0))
                correct = session.record_answer(player_id, answer_idx)
                
                # Send confirmation to player
                await ws.send_text(json.dumps({
                    "type": "answer.recorded",
                    "correct": correct
                }))
                
                # # Broadcast updated histogram
                # bins = [session.answer_counts.get(i, 0) for i in range(4)]
                # await broadcast(session, {
                #     "type": "histogram",
                #     "bins": bins
                # })
            
            # Kick player (host only)
            elif msg_type == "player.kick" and is_host_bool and session:
                kick_player_id = data.get("player_id")
                if kick_player_id and kick_player_id in session.connections:
                    kick_ws = session.connections[kick_player_id]
                    await kick_ws.send_text(json.dumps({
                        "type": "kicked",
                        "message": "You were removed from the session"
                    }))
                    await kick_ws.close()
                    session.remove_player(kick_player_id)
                    await broadcast_lobby(session)
                    await printlog(f"[session] kicked player={kick_player_id} from session={session_id}")
    
            elif msg_type == "chat" and session:
                msg = data.get("msg", "")
                player = session.players.get(player_id)
                name = player.name if player else "Unknown"
                if player.is_muted:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "You are muted"
                    }))
                    continue

                # Broadcast chat message to all in session
                await broadcast(session, {
                    "type": "chat",
                    "player_id": player_id,
                    "name": name,
                    "msg": msg
                })
                
            elif msg_type == "player.mute" and is_host_bool and session:
                mute_player_id = data.get("player_id")
                if mute_player_id and mute_player_id in session.players:
                    player = session.players[mute_player_id]
                    mute = player.is_muted
                    prompt = "unmuted" if mute else "muted"
                    player.is_muted = not mute
                    await printlog(f"[session] player={mute_player_id} in session={session_id} is now {prompt}")
                    await broadcast_lobby(session)
                    status = "muted" if mute else "unmuted"
    
    except WebSocketDisconnect:
        await printlog(f"[ws] disconnect player={player_id}")
    finally:
        # Cleanup
        if session and player_id in session.connections:
            session.connections.pop(player_id, None)
            
            if is_host_bool:
                # Host disconnected - close session
                await printlog(f"[session] host disconnected, closing session={session_id}")
                await broadcast(session, {
                    "type": "session.closed",
                    "message": "Host disconnected"
                })
                for p_ws in list(session.connections.values()):
                    try:
                        await p_ws.close()
                    except:
                        pass
                if session_id:
                    delete_session(session_id)
            else:
                # Student disconnected
                session.remove_player(player_id)
                await broadcast_lobby(session)


async def broadcast(session: QuizSession, payload: dict):
    """Broadcast message to all connections in a session."""
    dead = []
    for pid, ws in list(session.connections.items()):
        try:
            await ws.send_text(json.dumps(payload))
        except:
            dead.append(pid)
    
    for pid in dead:
        session.connections.pop(pid, None)


async def broadcast_lobby(session: QuizSession):
    """Broadcast lobby state to all connections."""
    await broadcast(session, {
        "type": "lobby.update",
        "players": [p.to_dict() for p in session.players.values()],
        "state": session.state.value
    })


async def ping_loop():
    """Send periodic, application-level pings to all connected sockets.

    This emits a lightweight JSON `{"type": "ping", "ts": <epoch>}` message
    to every connection so clients can respond with `pong`. The server can use
    the round-trip time to measure latency per-player (for UI/leaderboard
    features) and to detect dead peers.
    """
    # Import inside the function to avoid potential circular imports at module
    # load time. `quiz_sessions` is the in-memory mapping of active sessions.
    # Use the same import style as the top of this module (plain `quiz_types`) so
    # the module can be run in the repo layout the project uses.
    from quiz_types import quiz_sessions
    import time

    while True:
        await asyncio.sleep(PING_INTERVAL)
        now = time.time()

        # Iterate a snapshot of sessions to avoid mutation while iterating.
        for session in list(quiz_sessions.values()):
            for pid, ws in list(session.connections.items()):
                try:
                    await ws.send_text(json.dumps({"type": "ping", "ts": now}))
                except Exception:
                    # Ignore send errors here; connection cleanup happens elsewhere
                    # (broadcast/remove on send failure or during receive loop).
                    continue

            # The following is to identify the stale players based on PLAYER_TIMEOUT
            stale_players = []
            dead_players = []

            for pid, player in list(session.players.items()):
                last = player.last_seen or player.last_pong
                if last is None:
                    # Haven't heard from them yet; give them more time
                    continue
                silence = now - last

                if silence > HARD_TIMEOUT:
                    dead_players.append(pid)
                elif silence > PLAYER_TIMEOUT and player.status == "active":
                    stale_players.append(pid)

            # Identify stale players
            if stale_players:
                from quiz_types import QuizState  # if needed / already imported above
                for pid in stale_players:
                    session.players[pid].status = "stale"
                    await printlog(f"[stale] player={pid} in session={session.id}")

            # Drop dead players
            if dead_players:
                for pid in dead_players:
                    ws = session.connections.get(pid)
                    if ws is not None:
                        try:
                            await ws.close()
                        except:
                            pass

                    session.remove_player(pid)
                    await printlog(f"[dead] removed player={pid} in session={session.id}")
                
                # Notify remaining clients that lobby changed
                await broadcast_lobby(session)

async def printlog(message: str):
    """Helper to log messages to both console and file."""
    print(message)
    logger.info(message)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
