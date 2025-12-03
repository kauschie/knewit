#!/bin/bash

# ==================================================================
# KnewIt Persistent Launcher
# First run: Starts in background.
# Subsequent runs: Opens the window.
# ==================================================================

SESSION_NAME="knewit_lobby"
CURRENT_USER="${1:-$(whoami)}"
REAL_LAUNCHER="/home/mkausch/dev/3640/project/knewit/run.sh"

# 1. Check if session exists
tmux has-session -t "$SESSION_NAME" 2>/dev/null

if [ $? != 0 ]; then
    # ==============================================================
    # SCENARIO A: FIRST RUN (Session doesn't exist)
    # ==============================================================
    echo "🚀 Initializing background lobby for $CURRENT_USER..."
    
    # Create detached session (-d)
    # Force UTF-8 (-u) and 256-color (-2)
    tmux -u -2 new-session -d -s "$SESSION_NAME"
    
    # Configure the session
    tmux send-keys -t "$SESSION_NAME" "$REAL_LAUNCHER $CURRENT_USER" C-m
    
    echo "✅ Session running in background."
    echo "   Run this command again to open the lobby."
    
    # CRITICAL CHANGE: Exit here so we don't attach!
    exit 0
fi

# ==============================================================
# SCENARIO B: SUBSEQUENT RUNS (Session exists)
# ==============================================================
echo "✅ Found active lobby. Opening..."
exec tmux -u -2 attach-session -t "$SESSION_NAME"