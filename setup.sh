#!/bin/bash
# setup.sh — 라즈베리파이5 부동산 AI 설치
set -e
echo "=== 부동산 AI 설치 시작 ==="

PROJ="$HOME/realestate_ai"

# 디렉터리 생성
mkdir -p "$PROJ"/{config,logs,data,modules}

# venv 생성
python3 -m venv "$PROJ/venv"
source "$PROJ/venv/bin/activate"

# 패키지 설치
pip install --upgrade pip
pip install \
    anthropic \
    "python-telegram-bot[job-queue]" \
    python-dotenv \
    requests \
    aiohttp \
    beautifulsoup4 \
    lxml

echo "패키지 설치 완료"

# .env 파일 생성
if [ ! -f "$PROJ/.env" ]; then
    cp "$PROJ/.env.example" "$PROJ/.env"
    echo ".env 생성됨 — API 키 입력 필요: nano $PROJ/.env"
fi

# __init__.py 생성 (modules 패키지)
touch "$PROJ/modules/__init__.py"

# systemd 서비스 등록
sudo tee /etc/systemd/system/realestate_ai.service > /dev/null << EOF
[Unit]
Description=부동산 AI 모니터링 봇
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJ
ExecStart=$PROJ/venv/bin/python main.py
Restart=always
RestartSec=15
EnvironmentFile=$PROJ/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable realestate_ai.service

echo ""
echo "=== 설치 완료 ==="
echo ""
echo "다음 단계:"
echo "1. API 키 입력:  nano $PROJ/.env"
echo "2. DB 초기화:    cd $PROJ && venv/bin/python -c 'from modules.db import init_db; init_db()'"
echo "3. 봇 시작:      sudo systemctl start realestate_ai"
echo "4. 로그 확인:    journalctl -u realestate_ai -f"
