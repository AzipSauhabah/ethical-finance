#!/bin/bash
# ─── Deploy frontend ─────────────────────────────────────────────────────────
# Usage: sudo bash infra/deploy-frontend.sh
# Buildé depuis frontend/, copié vers dist/ racine, Nginx redémarré
set -e

PROJECT="/volume1/docker/ethical-finance"
FRONTEND="$PROJECT/frontend"
DIST="$PROJECT/dist"
API_URL="https://api.sauhabah-advisory.eu"

echo "🔨 Build frontend..."
sudo docker run --rm \
  -v "$PROJECT":/app \
  -w /app/frontend \
  -e VITE_API_URL="$API_URL" \
  node:20-alpine \
  sh -c "npm run build"

echo "📦 Copie vers dist/..."
sudo cp -rf "$FRONTEND/dist/." "$DIST/"
sudo chmod -R 755 "$DIST"

echo "🔄 Restart Nginx..."
sudo docker restart ethical-finance-frontend
sleep 3

echo "✅ Vérification..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001)
if [ "$STATUS" = "200" ]; then
  HASH=$(curl -s http://localhost:3001 | grep -o 'index-[^"]*\.js' | head -1)
  echo "✅ Deploy OK — $HASH — HTTP $STATUS"
else
  echo "❌ Deploy FAILED — HTTP $STATUS"
  exit 1
fi
