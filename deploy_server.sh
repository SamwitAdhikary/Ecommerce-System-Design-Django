#!/bin/bash
set -e

# ==============================================================================
# Automated Continuous Deployment Script for E-Commerce Backend
# Executes on every production update for zero-downtime releases.
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================="
echo "🚀 Starting Production Code Deployment..."
echo "Directory: $PROJECT_DIR"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="

# 1. Pull latest code from repository
echo "📥 1. Pulling latest commits from Git origin/main..."
git pull origin main

# 2. Activate Python virtual environment
echo "🐍 2. Activating Python virtual environment..."
source venv/bin/activate

# 3. Synchronize Python dependencies
echo "📦 3. Synchronizing Python package dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Apply database schema migrations
echo "🗄️  4. Applying database schema migrations..."
python manage.py migrate --noinput

# 5. Compile static files with WhiteNoise compression & hashing
echo "🎨 5. Compiling static assets (WhiteNoise Manifest)..."
python manage.py collectstatic --noinput

# 6. Graceful zero-downtime service reload
echo "🔄 6. Reloading Gunicorn worker processes (Zero-Downtime)..."
sudo systemctl reload gunicorn

echo "========================================="
echo "✅ DEPLOYMENT SUCCESSFUL!"
echo "Your backend services have been updated and reloaded with zero downtime."
echo "========================================="
