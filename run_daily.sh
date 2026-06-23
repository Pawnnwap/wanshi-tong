#!/bin/bash
# 万事通日报 - Daily runner
# Runs at 10:00 AM GMT+8 (02:00 UTC)

export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm use 22 > /dev/null 2>&1

export PATH="$HOME/.opencode/bin:$PATH"

cd /home/aaa/pyprojects/wanshi-tong
LOG_FILE="logs/run_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

python3 main.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

# Keep only last 30 logs
ls -t logs/run_*.log 2>/dev/null | tail -n +31 | xargs -r rm --

exit $EXIT_CODE
