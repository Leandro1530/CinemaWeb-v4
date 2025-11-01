#!/bin/bash
# deploy.sh - Script completo de despliegue para el servidor

set -e  # Salir en caso de error

echo "🚀 Iniciando despliegue de Cinema App..."

# Variables
APP_NAME="cinema"
APP_DIR="/var/www/cinema"
DOMAIN="is-lr3d.shop"
DB_NAME="cinema_db"
DB_USER="cinema_user"
APP_USER="www-data"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para mostrar mensajes
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que se ejecuta como root
if [ "$EUID" -ne 0 ]; then
    error "Este script debe ejecutarse como root (sudo)"
    exit 1
fi

# 1. Actualizar sistema
log "Actualizando sistema..."
apt update && apt upgrade -y

# 2. Instalar dependencias del sistema
log "Instalando dependencias del sistema..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libpq-dev \
    nginx \
    postgresql \
    postgresql-contrib \
    git \
    curl \
    certbot \
    python3-certbot-nginx \
    ufw \
    supervisor \
    logrotate

# 3. Configurar PostgreSQL
log "Configurando PostgreSQL..."
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || warn "Base de datos ya existe"
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD 'password_segura_aqui';" 2>/dev/null || warn "Usuario ya existe"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null || true
sudo -u postgres psql -c "ALTER USER $DB_USER CREATEDB;" 2>/dev/null || true

# 4. Crear directorios de la aplicación
log "Creando estructura de directorios..."
mkdir -p $APP_DIR
mkdir -p /var/log/cinema
mkdir -p /var/run/cinema
mkdir -p /var/www/cinema/static/{comprobantes,qr,uploads}
mkdir -p /var/www/cinema/instance

# 5. Configurar permisos
log "Configurando permisos..."
chown -R $APP_USER:$APP_USER $APP_DIR
chown -R $APP_USER:$APP_USER /var/log/cinema
chown -R $APP_USER:$APP_USER /var/run/cinema
chmod -R 755 $APP_DIR
chmod -R 755 /var/log/cinema

# 6. Crear entorno virtual
log "Creando entorno virtual Python..."
sudo -u $APP_USER python3 -m venv $APP_DIR/venv

# 7. Configurar firewall
log "Configurando firewall..."
ufw --force enable
ufw allow 22      # SSH
ufw allow 80      # HTTP
ufw allow 443     # HTTPS
ufw reload

# 8. Configurar nginx (configuración básica inicial)
log "Configurando nginx básico..."
rm -f /etc/nginx/sites-enabled/default

# 9. Configurar systemd service
log "Configurando servicio systemd..."
# El archivo cinema.service debe copiarse a /etc/systemd/system/

# 10. Configurar logrotate
log "Configurando rotación de logs..."
# El archivo cinema_logrotate debe copiarse a /etc/logrotate.d/cinema

log "✅ Configuración inicial del servidor completada"
echo
echo "📋 Próximos pasos:"
echo "1. Copiar el código de la aplicación a $APP_DIR"
echo "2. Configurar el archivo .env con las credenciales reales"
echo "3. Instalar dependencias Python: sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r requirements.txt"
echo "4. Ejecutar migraciones de base de datos"
echo "5. Configurar nginx con el archivo de configuración"
echo "6. Habilitar y iniciar el servicio: systemctl enable cinema && systemctl start cinema"
echo "7. Configurar SSL con el script setup_ssl.sh"
echo
echo "🌐 Dominio: $DOMAIN"
echo "📁 Directorio: $APP_DIR"
echo "🗄️  Base de datos: $DB_NAME"