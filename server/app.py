# server/app.py
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
import time
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

# 1. Setup Log Directory
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "server.log"

# 2. Configure Root Logger
# force=True ensures we override Uvicorn's default logging config
logging.basicConfig(
    filename=str(log_file), 
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s [SERVER] %(message)s',
    filemode='w',  # Overwrite on restart (change to 'a' to keep history)
    force=True
)

# 3. Create Server Logger
logger = logging.getLogger("server")
logger.setLevel(logging.DEBUG) # <--- Enable DEBUG for app.py specific logs

# 4. Enable DEBUG for shared modules (like quiz_types which uses 'knewit')
logging.getLogger("knewit").setLevel(logging.DEBUG)


# Heartbeat config
PING_INTERVAL = 20

# Lobby broadcast interval
LOBBY_UPDATE_INTERVAL = 5

# Seconds of silence before we declare a player "stale"
PLAYER_TIMEOUT = 60

# Seconds of silence before we declare a player "removed" and drop them
HARD_TIMEOUT = 300


# Background task reference
_ping_task: asyncio.Task | None = None
_lobby_task: asyncio.Task | None = None

BLOCKED_IPS = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan handler."""
    global _ping_task, _lobby_task
    await printlog("[lifespan] starting")
    
    _ping_task = asyncio.create_task(ping_loop())
    _lobby_task = asyncio.create_task(lobby_broadcast_loop())
    
    try:
        yield
    finally:
        await printlog("[lifespan] shutting down")
        if _ping_task:
            _ping_task.cancel()
        if _lobby_task:
            _lobby_task.cancel()
        await asyncio.gather(_ping_task, _lobby_task,return_exceptions=True)
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
async def ws_endpoint(ws: WebSocket, session_id: str, player_id: str):
    """
    Modernized WebSocket endpoint for KnewIt.
    - Host identified dynamically via session.create.
    - Students join via session.join.
    - All logic remains inside this handler for simplicity.
    """

    await ws.accept()
    
    if ws.client.host in BLOCKED_IPS:
        await printlog(f"[ws] rejected connection from blocked IP={ws.client.host}")
        await ws.close()
        return
    
    # Per-connection state
    conn = {
        "session": None,     # Will point to QuizSession
        "is_host": False,    # True after session.create
        "attempts": 3        # Password retries
    }

    await printlog(f"[ws] connected player_id={player_id}")

    # Send initial welcome to client
    await ws.send_text(json.dumps({
        "type": "welcome",
        "player_id": player_id,
        "is_host": False
    }))

    try:
        while True:
            raw = await ws.receive_text()
            data: dict = json.loads(raw)
            msg_type = data.get("type")

            await printlog(f"[ws] recv player={player_id} type={msg_type}")

            # Update last_seen for any inbound message
            if conn["session"] and player_id in conn["session"].players:
                now = time.time()
                player = conn["session"].players[player_id]
                player.last_seen = now

            # ------------------------------------------------------
            # HEARTBEAT
            # ------------------------------------------------------
            if msg_type == "pong":
                await printlog(f"[ws] pong from player={player_id}")
                if conn["session"]:
                    now = time.time()
                    p = conn["session"].players.get(player_id)
                    if p:
                        p.last_pong = now
                        p.last_seen = now
                        p.latency_ms = (now - data.get("ts", now)) * 500 # really * 100 / 2 to get latency instead of RTT
                        await printlog(f"[ws] updated latency for player={player_id}: {p.latency_ms:.2f} ms")
                        
                # await broadcast_lobby(conn["session"]) # background task handles this now
                continue

            # ------------------------------------------------------
            # HOST CREATES SESSION
            # ------------------------------------------------------
            if msg_type == "session.create":
                conn["is_host"] = True
                pw = data.get("password")

                await printlog(
                    f"[session] host={player_id} creating session sid={session_id} with {f'pw={pw}' if pw else 'no pw'}"
                )

                try:
                    session = create_session(
                        host_id=player_id,
                        session_id=session_id,
                        password=pw
                    )
                except ValueError as e:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
                    continue

                session.add_player(player_id, ws=ws)
                conn["session"] = session
                player_list = [p.player_id for p in session.players.values()]
                await printlog(f"[session] current players in session: {player_list}")
                # session.connections[player_id] = ws

                await ws.send_text(json.dumps({
                    "type": "session.created",
                    "session_id": session.id,
                    "host": player_id
                }))

                await printlog(
                    f"[session] created session id={session.id} host={player_id}"
                )

                await broadcast_lobby(session, added_player=player_id)
                continue

            # ------------------------------------------------------
            # STUDENT JOINS SESSION
            # ------------------------------------------------------
            
            if msg_type == "session.join":
                pw = data.get("password")

                # await printlog(
                #     f"[session] player={player_id} join sid={sid} attempts remaining={conn['attempts']}"
                # )
                
                session = get_session(session_id)
                if not session:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Session not found"
                    }))
                    continue

                # Password
                if session.password:
                    if conn["attempts"] <= 0:
                        await ws.send_text(json.dumps({
                            "type": "reject.pw",
                            "message": "Too many incorrect password attempts"
                        }))
                        
                        # close connection
                        await ws.close()
                        # add ip blocking here if desired
                        # get ip
                        ip = ws.client.host
                        port = ws.client.port
                        await printlog(f"[ws] disconnecting player={player_id} from ip={ip}:{port} due to too many incorrect password attempts")
                        
                        break
                    
                    
                    if pw != session.password:
                        conn["attempts"] -= 1

                        await ws.send_text(json.dumps({
                            "type": "reject.pw",
                            "message": f"Incorrect password. {conn['attempts']} attempts left."
                        }))
                        continue

                # Add player
                await printlog(f"[session] player={player_id} joining session id={session.id}")
                player = session.add_player(player_id, ws=ws)
                player_list = [p.player_id for p in session.players.values()]
                await printlog(f"[session] current players in session: {player_list}")
                if not player:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Name already taken"
                    }))
                    continue

                conn["session"] = session
                # session.connections[player_id] = ws
                
                logger.debug(f"[ws] player={player_id} joined session={session.id}")
                for pid in session.players:
                    logger.debug(f"    player in session: {pid}")

                await ws.send_text(json.dumps({
                    "type": "session.joined",
                    "session_id": session.id,
                    "name": player_id,
                    "host_id": session.host_id
                }))

                await broadcast_lobby(session, added_player=player_id)
                
                continue

            # ------------------------------------------------------
            # Reject messages until session exists
            # ------------------------------------------------------
            if not conn["session"]:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": "No active session"
                }))
                continue

            session = conn["session"]

            # ------------------------------------------------------
            # HOST ONLY ACTIONS
            # ------------------------------------------------------
            if msg_type == "quiz.load" and conn["is_host"]:
                await printlog(f"[quiz] host={player_id} loading quiz into session={session.id}")
                quiz_data = data.get("quiz")
                if quiz_data:
                    quiz = Quiz.from_dict(quiz_data)
                    session.load_quiz(quiz)
                    await printlog(f"[quiz] loaded quiz '{quiz.title}' with {len(quiz.questions)} questions for session={session.id}")

    
                    #################
                    #   initialize quiz state in orchestrator
                    #################

                    await broadcast(session, {
                        "type": "quiz.loaded",
                        "quiz_title": quiz.title,
                        "num_questions": len(quiz.questions)
                    })
                    await printlog(f"[quiz] loaded quiz '{quiz.title}' with {len(quiz.questions)} questions for session={session.id}")
                else:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "No quiz data provided"
                    }))
                    await printlog(f"[quiz] no quiz data provided by host={player_id} for session={session.id}")
                continue

            if msg_type == "quiz.start" and conn["is_host"]:
                if session.start_quiz():
                    await printlog(f"[quiz] starting quiz for session={session.id}")
                    question = session.next_question()
                    if question:
                        sq = StudentQuestion.from_question(question)
                        sq.index = session.current_question_idx
                        sq.total = len(session.quiz.questions)
                        sq.timer = 10 # get from question or orchestrator later

                        await broadcast(session, {
                            "type": "question.next",
                            "question": sq.to_dict()
                        })
                    else:
                        await broadcast(session, {
                            "type": "quiz.finished",
                            "leaderboard": [
                                {"name": p.player_id, "score": p.score}
                                for p in sorted(
                                    session.players.values(),
                                    key=lambda x: x.score,
                                    reverse=True
                                )
                            ]
                        })
                    
                else:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "No quiz loaded"
                    }))
                continue

            if msg_type == "question.next" and conn["is_host"]:
                question = session.next_question()
                if question:
                    sq = StudentQuestion.from_question(question)
                    sq.index = session.current_question_idx
                    sq.total = len(session.quiz.questions)
                    sq.timer = 10 # get from question or orchestrator later

                    await broadcast(session, {
                        "type": "question.next",
                        "question": sq.to_dict()
                    })
                else:
                    await broadcast(session, {
                        "type": "quiz.finished",
                        "leaderboard": [
                            {"name": p.player_id, "score": p.score}
                            for p in sorted(
                                session.players.values(),
                                key=lambda x: x.score,
                                reverse=True
                            )
                        ]
                    })
                continue

            if msg_type == "question.end" and conn["is_host"]:
                # Retrieve the current question to verify the correct answer
                q = session.get_current_question()
                if not q:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "No active question to end"
                    }))
                    await printlog(f"[quiz] no active question to end for session={session.id}")
                    continue
                
                correct_idx = q.correct_idx
                final_counts = session.get_answer_counts()
                
                # finalize scoring history
                session.close_question_scoring()
                
                await printlog(f"[quiz] ended question {session.current_question_idx} for session={session.id}, correct_idx={correct_idx}, final_counts={final_counts}")
                
                # broadcast results
                await broadcast(session, {
                    "type": "question.results",
                    "correct_idx": correct_idx,
                    "histogram": final_counts
                })
                
                await broadcast_lobby(session)
                
                continue

            if msg_type == "player.kick" and conn["is_host"]:
                kid = data.get("player_id")
                if kid in session.connections:
                    try:
                        await session.connections[kid].send_text(json.dumps({
                            "type": "kicked"
                        }))
                        await session.connections[kid].close()
                    except:
                        pass
                    session.remove_player(kid)
                    await broadcast_lobby(session, removed_player=kid)
                continue

            if msg_type == "quiz.stop" and conn["is_host"]:
                # mark session as finished
                session.state = QuizState.FINISHED
                
                # generate final leaderboard
                leaderboard = [
                    {"name": p.player_id, "score": p.score}
                    for p in sorted(
                        session.players.values(),
                        key=lambda x: x.score,
                        reverse=True
                    )
                ]
                
                await printlog(f"[quiz] stopping quiz for session={session.id}, final leaderboard: {leaderboard}")
                await broadcast(session, {
                    "type": "quiz.finished",
                    "leaderboard": leaderboard
                })
                continue

            # ------------------------------------------------------
            # STUDENT ACTIONS
            # ------------------------------------------------------
            if msg_type == "answer.submit":
                answer_idx = int(data.get("answer_idx", -1))
                elapsed = data.get("elapsed", None)
                correct = session.record_answer(player_id, answer_idx, elapsed)
                
                # update histogram for host
                hist = session.get_answer_counts()
                host_ws = session.connections.get(session.host_id)
                if host_ws:
                    try:
                        await host_ws.send_text(json.dumps({
                            "type": "question.histogram",
                            "question": session.current_question_idx,
                            "histogram": hist
                        }))
                    except:
                        pass
                
                await ws.send_text(json.dumps({
                    "type": "answer.recorded",
                    "correct": correct
                }))
                continue

            # ------------------------------------------------------
            # CHAT
            # ------------------------------------------------------
            if msg_type == "chat":
                msg = data.get("msg", "")
                p = session.players.get(player_id)
                # name = p.player_id if p else "Unknown"

                if p and p.is_muted:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "You are muted"
                    }))
                    continue

                await broadcast(session, {
                    "type": "chat",
                    "player_id": player_id,
                    "msg": msg
                })
                continue

            # ------------------------------------------------------
            # FALLBACK
            # ------------------------------------------------------
            await ws.send_text(json.dumps({
                "type": "error",
                "message": f"Unknown message: {msg_type}"
            }))

    except WebSocketDisconnect:
        await printlog(f"[ws] disconnect player={player_id}")

    finally:
        session = conn["session"]

        if session:
            # Remove connection
            session.connections.pop(player_id, None)

            if conn["is_host"]:
                # Host disconnected: close session
                await printlog(
                    f"[session] host disconnected; closing session={session.id}"
                )
                await broadcast(session, {
                    "type": "session.closed",
                    "message": "Host disconnected"
                })

                # Close all students
                for p_ws in list(session.connections.values()):
                    try:
                        await p_ws.close()
                    except:
                        pass

                delete_session(session.id)
            else:
                # Normal student disconnect
                session.remove_player(player_id)
                await broadcast_lobby(session, removed_player=player_id)


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


async def broadcast_lobby(session: QuizSession, removed_player: str | None = None, added_player: str | None = None):
    """Broadcast lobby state to all connections."""
    players = [p.to_dict() for p in session.players.values()]
    
    # identify the change
    if removed_player:
        await broadcast(session, {
            "type": "lobby.update",
            "players": players,
            "state": session.state.value,
            "removed": removed_player
    })
    elif added_player:
        await broadcast(session, {
            "type": "lobby.update",
            "players": players,
            "state": session.state.value,
            "added": added_player
    })
    else:
        await broadcast(session, {
            "type": "lobby.update",
            "players": players,
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
                    await broadcast_lobby(session, removed_player=pid) # implement multiple updates in the future to be more efficient
                    
                
                # Notify remaining clients that lobby changed
async def lobby_broadcast_loop():
    """Periodically broadcast lobby state to all sessions."""
    from quiz_types import quiz_sessions

    while True:
        await asyncio.sleep(LOBBY_UPDATE_INTERVAL)  # every 5 seconds
        for session in list(quiz_sessions.values()):
            if session.players:
                await broadcast_lobby(session)

async def printlog(message: str):
    """Helper to log messages to both console and file."""
    # print(message)
    logger.debug(message)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=49000, log_level="debug", log_config=None)
