#!/bin/bash

# ==================================================================
# KnewIt Host Session Orchestrator
# Launches multiple Host clients in a single tmux session.
# Usage: ./launch_hosts.sh [number_of_hosts]
# ==================================================================

# --- Configuration ---
HOST_COUNT="${1:-5}"
TMUX_SESSION="knewit_hosts"
BASE_SESSION_ID="odin"
SERVER_IP="0.0.0.0"
SERVER_PORT="49000"

# ABSOLUTE path to your Host executable
# (Update this if your path is different!)
EXE_PATH="/home/stu/mkausch/public_html/knewit/knewit_host_linux"  # on Odin

# --- 1. Clean Start ---
tmux kill-session -t "$TMUX_SESSION" 2>/dev/null

echo "🚀 Spawning $HOST_COUNT Host sessions in tmux session '$TMUX_SESSION'..."

# Create the session with a generic control window
tmux -u -2 new-session -d -s "$TMUX_SESSION" -n "control"

# --- 2. Spawn Hosts ---
for (( i=1; i<=$HOST_COUNT; i++ ))
do
    SESSION_ID="${BASE_SESSION_ID}${i}"
    HOST_USER="host_${SESSION_ID}"
    
    # Create a window for this host
    tmux new-window -t "$TMUX_SESSION" -n "$SESSION_ID"
    
    # --- SAFE LAUNCH LOGIC INLINE ---
    # 1. Create unique temp dir (mktemp)
    # 2. Set TRAP to delete it on EXIT
    # 3. Export TMPDIR and CD into it
    # 4. Run Executable
    
    SAFE_CMD="
    TD=\$(mktemp -d -p \"\$(pwd)\" \"host_runtime.XXXXXX\"); 
    trap \"rm -rf \$TD\" EXIT; 
    export TMPDIR=\$TD; 
    cd \$TD; 
    $EXE_PATH --user $HOST_USER --session $SESSION_ID --ip $SERVER_IP --port $SERVER_PORT
    "
    
    # Send the safe command to the window
    echo "   -> Starting Host for '$SESSION_ID'..."
    tmux send-keys -t "$TMUX_SESSION:$SESSION_ID" "$SAFE_CMD" C-m
    
    sleep 1
done

# --- 3. Finalize ---
tmux select-window -t "$TMUX_SESSION:$BASE_SESSION_ID1"

echo "----------------------------------------"
echo "✅ All hosts running in session: $TMUX_SESSION"
echo "   Attach to view: tmux attach -t $TMUX_SESSION"
