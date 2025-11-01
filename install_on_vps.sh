#!/bin/bash
# install_on_vps.sh - Script de instalación para VPS Hostinger

echo "🚀 Instalando Cinema3D en VPS Hostinger..."
echo "IP: 31.97.174.96"
echo "Dominio: is-lr3d.shop"
echo ""

# Función para logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Variables
APP_NAME="cinema3d"
APP_DIR="/var/www/$APP_NAME"
APP_USER="$APP_NAME"
DOMAIN="is-lr3d.shop"

# 1. Actualizar sistema
log "Actualizando sistema..."
apt update && apt upgrade -y

# 2. Instalar dependencias
log "Instalando dependencias..."
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
apt install -y nginx supervisor git curl unzip

# 3. Crear usuario para la aplicación
log "Creando usuario $APP_USER..."
useradd -m -s /bin/bash $APP_USER 2>/dev/null || log "Usuario ya existe"

# 4. Crear directorios
log "Creando directorios..."
mkdir -p $APP_DIR
chown $APP_USER:$APP_USER $APP_DIR

# 5. Configurar Python y entorno virtual
log "Configurando entorno Python..."
cd $APP_DIR
sudo -u $APP_USER python3.11 -m venv venv
sudo -u $APP_USER ./venv/bin/pip install --upgrade pip

# 6. Instalar dependencias Python (las instalaremos después de copiar requirements.txt)
log "Preparando para instalar dependencias Python..."

echo "✅ Preparación inicial completada."
echo ""
echo "📋 Próximos pasos:"
echo "1. Copiar archivos de la aplicación a $APP_DIR"
echo "2. Ejecutar: sudo -u $APP_USER ./venv/bin/pip install -r requirements.txt"
echo "3. Configurar Nginx"
echo "4. Configurar Supervisor"
echo "5. Configurar variables de entorno"
echo ""