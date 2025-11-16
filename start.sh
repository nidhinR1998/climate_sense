#!/bin/bash
# start.sh

echo "Starting ClimateSense Agent Loop..."

# Ensure the .env file is present or the environment variables are set
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "WARNING: GOOGLE_API_KEY is not set. The agent will likely fail."
fi

# Execute the Python agent. The '&' runs it in the background.
python run_agent_loop.py &

# Wait for the background process to start and then wait indefinitely
# This is a common pattern for running long-lived background processes in Docker.
wait -n

# Exit with status of process that exited first
exit $?