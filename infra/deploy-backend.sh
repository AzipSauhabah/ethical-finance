#!/bin/bash
# ─── Deploy backend ──────────────────────────────────────────────────────────
# Usage: sudo bash infra/deploy-backend.sh
# git pull + docker cp des fichiers modifiés + restart API
set -e

PROJECT="/volume1/docker/ethical-finance"
CONTAINER="ethical-finance-api"

echo "📥 Git pull..."
cd "$PROJECT"
export PATH="/volume1/docker/bin:$PATH"
git pull

echo "📦 Copie fichiers backend..."
find backend -name "*.py" | while read f; do
  sudo docker cp "$PROJECT/$f" "$CONTAINER:/app/$f" 2>/dev/null || true
done

echo "🔄 Restart API..."
sudo docker restart "$CONTAINER"
sleep 12

echo "✅ Vérification..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health)
if [ "$STATUS" = "200" ]; then
  STRATEGIES=$(curl -s http://localhost:8000/api/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('strategies','?'))")
  echo "✅ Deploy backend OK — $STRATEGIES stratégies — HTTP $STATUS"
else
  echo "❌ Deploy FAILED — HTTP $STATUS"
  sudo docker logs "$CONTAINER" --tail 10
  exit 1
fi
