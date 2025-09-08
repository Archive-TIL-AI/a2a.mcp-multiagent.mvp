#!/bin/bash

# MCP 관련 모든 프로세스 정리

echo "🔍 현재 실행 중인 MCP 관련 프로세스:"
ps aux | grep -E "(server\.py|uv.*server)" | grep -v grep

echo ""
echo "🧹 정리 중..."

# 1. server.py 관련 UV 프로세스 종료
echo "  • UV 프로세스 종료 중..."
pkill -f "uv.*server.py" 2>/dev/null || true

# 2. server.py 프로세스 직접 종료
echo "  • server.py 프로세스 종료 중..."
pkill -f "server.py" 2>/dev/null || true

# 3. 잠시 대기 (프로세스 정리 시간)
sleep 2

# 4. 강제 종료 (혹시나)
echo "  • 남은 프로세스 강제 종료..."
pkill -9 -f "server.py" 2>/dev/null || true
pkill -9 -f "uv.*server" 2>/dev/null || true

sleep 1

# 5. 결과 확인
echo ""
echo "🔍 정리 후 남은 프로세스:"
remaining=$(ps aux | grep -E "(server\.py|uv.*server)" | grep -v grep | wc -l)

if [ "$remaining" -eq 0 ]; then
    echo "✅ 모든 MCP 프로세스가 정리되었습니다!"
else
    echo "⚠️  아직 남은 프로세스가 있습니다:"
    ps aux | grep -E "(server\.py|uv.*server)" | grep -v grep
fi

echo ""
echo "🚀 이제 FastAPI 앱을 재시작하세요:"
echo "   python main.py"
echo "   또는"
echo "   uvicorn main:app --reload --port 8081"