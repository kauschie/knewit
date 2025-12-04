#!/bin/bash

# KnewIt Auto-Login & Safe Launcher Script
# Usage: ./knewit_auto_login.sh [username]

# --- 1. Configuration ---
# 
# Determine Username: Use argument $1 if provided, else default to OS user
USERNAME="${1:-$(whoami)}"

# Server Defaults
SESSION_ID="demo"
SERVER_IP="0.0.0.0"
SERVER_PORT="49000"

# Path to the Shared Executable
# IMPORTANT: This MUST be an ABSOLUTE path because we change directories below.
# EXE_PATH="/home/stu/mkausch/public_html/knewit/knewit_student_linux" # on Odin
EXE_PATH="/home/mkausch/dev/3640/project/knewit/dist/knewit_student_linux" # local

# --- 2. Runtime Environment Setup ---

# Create a unique temporary directory for THIS specific run in the current folder
# This bypasses /tmp 'noexec' restrictions and isolates logs per-user/per-run.
UNIQUE_TMP_DIR=$(mktemp -d -p "$(pwd)" "knewit_runtime.XXXXXX")

# Safety Trap: Delete the temp folder (and all logs inside it) when the script exits
trap 'rm -rf "$UNIQUE_TMP_DIR"' EXIT

# Tell PyInstaller to unpack its internal libraries into this folder
export TMPDIR="$UNIQUE_TMP_DIR"

# Move execution into the temp folder
# This forces the app to write 'logs/' and 'session_logs/' here.
# Result: The user's home directory stays clean.
cd "$UNIQUE_TMP_DIR" || exit


# --- 3. Launch Application ---

echo "--------------------------------------------------"
echo "🚀 Launching KnewIt Quiz Client"
echo "--------------------------------------------------"
echo "👤 User:    $USERNAME"
echo "🏠 Session: $SESSION_ID"
echo "🌐 Server:  $SERVER_IP:$SERVER_PORT"
echo "📂 Runtime: $UNIQUE_TMP_DIR (Will be cleaned up on exit)"
echo "--------------------------------------------------"

# Run the executable with the auto-login arguments
"$EXE_PATH" --user "$USERNAME" --session "$SESSION_ID" --ip "$SERVER_IP" --port "$SERVER_PORT"