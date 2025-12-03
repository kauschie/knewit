#!/bin/bash

# ==================================================================
# KnewIt Multi-Swarm Orchestrator
# Launches multiple swarms targeting different rooms.
# Usage: ./launch_multi_swarm.sh [number_of_swarms]
# Example: ./launch_multi_swarm.sh 5  -> Launches demo1..demo5
# ==================================================================

BASE_ROOM_NAME="demo"
# Use argument $1 if provided, otherwise default to 5
SWARM_COUNT="${1:-5}"

echo "🌪️  Initializing Attack with $SWARM_COUNT Swarms..."
echo "----------------------------------------"

for (( i=1; i<=$SWARM_COUNT; i++ ))
do
    ROOM_ID="${BASE_ROOM_NAME}${i}"       # e.g., demo1
    TMUX_SESSION="swarm_${ROOM_ID}"       # e.g., swarm_demo1
    
    # Launch the swarm in the background
    ./stress_test.sh "$TMUX_SESSION" "$ROOM_ID" &
    
    echo "   -> Launched Swarm $i targeting '$ROOM_ID' (Session: $TMUX_SESSION)"
    sleep 2
done

wait
echo "----------------------------------------"
echo "✅ All $SWARM_COUNT swarms deployed!"
echo "   View active sessions: tmux ls"
echo "   Kill all swarms:      killall tmux"