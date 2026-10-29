#!/bin/bash
set -e

FURHAT_DIR="/Users/yuvalzohar/Documents/GitHub/furhat-emotion-study"
CE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== 1/3  בונה את סקיל הרובוט ==="
cd "$FURHAT_DIR"
export JAVA_HOME=$(/usr/libexec/java_home -v 11 2>/dev/null)
./rebuild.sh

echo ""
echo "=== 2/3  בדשבורד של Furhat: טעני את הסקיל (הנתיב ב-clipboard), לחצי Start Skill ==="
echo "    המתיני לשורות:"
echo "    [RemoteControl] Listening on http://localhost:8765/react"
echo "    [RemoteControl] Listening on http://localhost:8765/say"
echo "    [RemoteControl] Listening on http://localhost:8765/health"
read -p "לחצי Enter כשהרובוט מוכן... "

echo ""
echo "=== 3/3  מפעילה את ממשק השיחה ==="
cd "$CE_DIR"
source venv/bin/activate
export LLM_PROVIDER=openai
streamlit run interaction_app.py
