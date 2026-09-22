#!/bin/bash
set -e

# ==============================================================================
# Initial Server Bootstrap & Infrastructure Provisioning Script
# Run once when provisioning a fresh Ubuntu Linux VPS (Linode, AWS EC2, DigitalOcean).
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME=$(whoami)

echo "========================================="
echo "🛠️  Starting Initial Server Provisioning..."
echo "User: $USER_NAME"
echo "Project Directory: $PROJECT_DIR"
echo "========================================="

# 1. Update system packages and install system dependencies (including Certbot for SSL)
echo "📦 1. Installing Ubuntu system dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-venv nginx certbot python3-certbot-nginx curl git libpq-dev

# 2. Setup Python virtual environment
echo "🐍 2. Setting up Python virtual environment..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
    python3 -m venv "$PROJECT_DIR/venv"
fi
source "$PROJECT_DIR/venv/bin/activate"

# 3. Install Python dependencies
echo "📦 3. Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

# 4. Generate production .env file if missing
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "🔑 4. Generating production .env file..."
    touch "$PROJECT_DIR/.env"
    echo "DEBUG=False" >> "$PROJECT_DIR/.env"
    echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')" >> "$PROJECT_DIR/.env"
    echo "DATABASE_URL=postgres://user:password@localhost:5432/ecommerce_db" >> "$PROJECT_DIR/.env"
    echo "ALLOWED_HOSTS=api.yourstore.com,localhost,127.0.0.1" >> "$PROJECT_DIR/.env"
    echo "NUM_PROXIES=1" >> "$PROJECT_DIR/.env"
    echo "CORS_ALLOW_ALL_ORIGINS=False" >> "$PROJECT_DIR/.env"
    echo "CORS_ALLOWED_ORIGINS=https://yourstore.com,https://www.yourstore.com" >> "$PROJECT_DIR/.env"
    echo "USE_S3=False" >> "$PROJECT_DIR/.env"
    echo "---------------------------------------------------------"
    echo "⚠️  Generated template $PROJECT_DIR/.env."
    echo "Please configure your production DATABASE_URL & credentials in .env"
    read -p "Press [Enter] after editing .env to run database migrations and start services..."
    echo "---------------------------------------------------------"
fi

# 5. Prompt for Production Domain Name
read -p "Enter your production domain (e.g. api.yourstore.com) [default: api.yourstore.com]: " DOMAIN_NAME
DOMAIN_NAME=${DOMAIN_NAME:-api.yourstore.com}

# 6. Apply database schema migrations and create cache table
echo "🗄️  6. Applying database migrations & creating shared cache table..."
python manage.py migrate --noinput
python manage.py createcachetable

# 7. Create Gunicorn systemd service unit with ExecReload support
echo "⚙️  7. Creating Gunicorn systemd service unit..."
sudo tee /etc/systemd/system/gunicorn.service > /dev/null <<EOF
[Unit]
Description=Gunicorn daemon for E-Commerce Backend
After=network.target

[Service]
User=$USER_NAME
Group=www-data
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind 127.0.0.1:8000 \
          core.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 8. Start and enable Gunicorn daemon
echo "🚀 8. Starting and enabling Gunicorn daemon..."
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl enable gunicorn

# 9. Configure Nginx Reverse Proxy with Upstream Header Management
echo "🌐 9. Configuring Nginx Reverse Proxy..."
sudo tee /etc/nginx/sites-available/ecommerce > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN_NAME _;

    client_max_body_size 50M; # Allow high-resolution product image uploads

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }

    # Reverse proxy to Gunicorn WSGI server
    location / {
        proxy_set_header Host \$http_host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_pass http://127.0.0.1:8000;
    }
}
EOF

# 10. Enable Nginx configuration
echo "🔗 10. Enabling Nginx site configuration..."
sudo ln -sf /etc/nginx/sites-available/ecommerce /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 11. Test and reload Nginx
sudo nginx -t
sudo systemctl restart nginx

echo "========================================="
echo "✅ SERVER PROVISIONING COMPLETE!"
echo "Your backend API is now running and supervised by systemd & Nginx."
echo "Test by visiting: http://<SERVER_IP>/admin"
echo ""
echo "🔒 Next Step (SSL/TLS): Once your DNS ($DOMAIN_NAME) points to this server, run:"
echo "sudo certbot --nginx -d $DOMAIN_NAME"
echo "========================================="
