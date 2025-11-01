#!/bin/bash
# deploy.sh - Script completo de deployment

set -e

echo "🚀 Deploying Cinema3D to VPS..."

# Variables
APP_DIR="/var/www/cinema3d"
APP_USER="cinema3d"
DOMAIN="is-lr3d.shop"

# Función para logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 1. Preparar el entorno
log "Preparando entorno..."
sudo mkdir -p $APP_DIR
sudo useradd -m -s /bin/bash $APP_USER 2>/dev/null || true
sudo chown $APP_USER:$APP_USER $APP_DIR

# 2. Copiar archivos
log "Copiando archivos de la aplicación..."
sudo cp -r . $APP_DIR/
sudo chown -R $APP_USER:$APP_USER $APP_DIR

# 3. Crear entorno virtual e instalar dependencias
log "Configurando Python y dependencias..."
cd $APP_DIR
sudo -u $APP_USER python3.11 -m venv venv
sudo -u $APP_USER ./venv/bin/pip install --upgrade pip
sudo -u $APP_USER ./venv/bin/pip install -r requirements.txt

# 4. Crear directorios necesarios
log "Creando directorios..."
sudo -u $APP_USER mkdir -p logs static/comprobantes static/qr

# 5. Configurar variables de entorno
log "Configurando variables de entorno..."
sudo -u $APP_USER cp .env.production .env

# 6. Configurar Nginx
log "Configurando Nginx..."
sudo cp deploy/nginx_cinema3d.conf /etc/nginx/sites-available/cinema3d
sudo ln -sf /etc/nginx/sites-available/cinema3d /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

# 7. Configurar Supervisor
log "Configurando Supervisor..."
sudo cp deploy/supervisor_cinema3d.conf /etc/supervisor/conf.d/
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart cinema3d

# 8. Configurar firewall
log "Configurando firewall..."
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow ssh

log "✅ Deployment completado!"
log "🌍 Tu aplicación está disponible en:"
log "   http://$DOMAIN"
log "   http://31.97.174.96"
log ""
log "📊 Para ver logs:"
log "   sudo tail -f /var/www/cinema3d/logs/gunicorn.log"
log ""
log "🔧 Para reiniciar:"
log "   sudo supervisorctl restart cinema3d"