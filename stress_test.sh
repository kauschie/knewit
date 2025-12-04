#!/bin/bash

# ==================================================================
# KnewIt Single Swarm Launcher
# Spawns 20 bots into a specific room via tmux.
# Usage: ./stress_test.sh [tmux_session_name] [room_id]
# ==================================================================

SESSION_NAME="${1:-knewit_stress}"
TARGET_SESSION="${2:-demo}"

BOT_COUNT=20
BASE_NAME="bot"
SERVER_IP="0.0.0.0"
SERVER_PORT="49000"

# ABSOLUTE Path to Student Executable
# (Or python script if testing locally: "python /absolute/path/to/client/student_ui.py")
EXE_PATH="/home/mkausch/dev/3640/project/knewit/dist/knewit_student_linux"

# --- 1. Clean Start ---
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# --- 2. Create Session ---
echo "🚀 Spawning $BOT_COUNT bots for Room '$TARGET_SESSION' in Session '$SESSION_NAME'"
tmux -u -2 new-session -d -s "$SESSION_NAME" -n "control"

# --- 3. Spawn Bots ---
for (( i=1; i<=$BOT_COUNT; i++ ))
do
    USER_ID="${BASE_NAME}_${TARGET_SESSION}_${i}"
    tmux new-window -t "$SESSION_NAME" -n "$USER_ID"
    
    # --- SAFE LAUNCH LOGIC INLINE ---
    # Same trap logic as hosts, but for students
    SAFE_CMD="
    TD=\$(mktemp -d -p \"\$(pwd)\" \"bot_runtime.XXXXXX\"); 
    trap \"rm -rf \$TD\" EXIT; 
    export TMPDIR=\$TD; 
    cd \$TD; 
    $EXE_PATH --user $USER_ID --session $TARGET_SESSION --ip $SERVER_IP --port $SERVER_PORT
    "
    
    tmux send-keys -t "$SESSION_NAME:$USER_ID" "$SAFE_CMD" C-m
    sleep 0.1
done

# --- 4. Finalize ---
tmux select-window -t "$SESSION_NAME:control"
echo "✅ Swarm '$SESSION_NAME' ready."
