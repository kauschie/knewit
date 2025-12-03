#!/bin/bash

# ==================================================================
# KnewIt Persistent Launcher
# Usage: ./knewit_persistent.sh [username]
# ==================================================================

SESSION_NAME="knewit_lobby"
CURRENT_USER="${1:-$(whoami)}"

# ABSOLUTE path to your safe launcher script (the one that handles /tmp)
# Update this if your path changes!
REAL_LAUNCHER="/home/stu/mkausch/public_html/knewit/knewit_auto_login.sh"

# 1. Check if the persistent session already exists
tmux has-session -t "$SESSION_NAME" 2>/dev/null

if [ $? != 0 ]; then
    # ---------------------------------------------------------------
    # CASE A: Session Missing -> Create it (Detached)
    # ---------------------------------------------------------------
    echo "🚀 Initializing background lobby for $CURRENT_USER..."
    
    # Create session in background (-d)
    tmux new-session -d -s "$SESSION_NAME"
    
    # Send the launch command to the hidden session
    # We pass the username as a direct argument ($1) to the launcher
    # 'C-m' simulates pressing ENTER
    tmux send-keys -t "$SESSION_NAME" "$REAL_LAUNCHER $CURRENT_USER" C-m
    
else
    # ---------------------------------------------------------------
    # CASE B: Session Exists -> Just notify
    # ---------------------------------------------------------------
    echo "✅ Found active lobby. Reconnecting..."
fi

# 2. Attach the user to the session
# ---------------------------------
# This brings the background app to the foreground.
# - User sees the TUI.
# - User presses 'Ctrl+B' then 'D' to detach (hide) it again.
exec tmux attach-session -t "$SESSION_NAME"