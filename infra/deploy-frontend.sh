#!/bin/bash
# Deploy frontend — build + copy to dist/ + restart Nginx
set -e
cd /volume1/docker/ethical-finance

sudo docker run --rm \
  -v /volume1/docker/ethical-finance:/app \
  -w /app/frontend \
  -e VITE_API_URL=https://api.sauhabah-advisory.eu \
  node:20-alpine \
  sh -c "npm run build"

sudo cp -rf /volume1/docker/ethical-finance/frontend/dist/* /volume1/docker/ethical-finance/dist/
sudo docker restart ethical-finance-frontend
echo "✅ Deploy frontend OK"
