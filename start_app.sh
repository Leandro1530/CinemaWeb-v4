#!/bin/bash
# start_app.sh - Script para iniciar la aplicación en producción

# Configuración
APP_DIR="/var/www/cinema"
VENV_DIR="$APP_DIR/venv"
WORKERS=4
BIND_ADDRESS="127.0.0.1:8000"
TIMEOUT=120
KEEP_ALIVE=5

# Cargar entorno virtual
source "$VENV_DIR/bin/activate"

# Cambiar al directorio de la aplicación
cd "$APP_DIR"

# Verificar que el archivo .env existe
if [ ! -f ".env" ]; then
    echo "Error: Archivo .env no encontrado"
    exit 1
fi

# Crear directorios necesarios
mkdir -p logs
mkdir -p static/comprobantes
mkdir -p static/qr
mkdir -p static/uploads
mkdir -p instance

# Asegurar permisos correctos
chmod 755 static/comprobantes static/qr static/uploads
chmod 644 .env

# Ejecutar migraciones de base de datos si es necesario
echo "Verificando base de datos..."
python -c "
from app import create_app
from app.db import create_schema
app = create_app()
with app.app_context():
    create_schema()
    print('Base de datos lista')
"

# Iniciar la aplicación con gunicorn
echo "Iniciando aplicación con gunicorn..."
exec gunicorn \
    --workers=$WORKERS \
    --bind=$BIND_ADDRESS \
    --timeout=$TIMEOUT \
    --keep-alive=$KEEP_ALIVE \
    --max-requests=1000 \
    --max-requests-jitter=50 \
    --preload \
    --access-logfile=logs/access.log \
    --error-logfile=logs/error.log \
    --log-level=info \
    --capture-output \
    wsgi:app