#!/bin/bash
# install_cinema3d.sh - Script de instalación para VPS

echo "🚀 Instalando Cinema3D en VPS..."

# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.11 y dependencias
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
sudo apt install -y nginx git supervisor

# Crear usuario para la aplicación
sudo useradd -m -s /bin/bash cinema3d
sudo mkdir -p /var/www/cinema3d
sudo chown cinema3d:cinema3d /var/www/cinema3d

# Cambiar a directorio de trabajo
cd /var/www/cinema3d

# Crear entorno virtual
sudo -u cinema3d python3.11 -m venv venv
sudo -u cinema3d ./venv/bin/pip install --upgrade pip

# Clonar repositorio (si usas Git) o copiar archivos
# git clone https://github.com/tu-usuario/cinema3d.git .

# Instalar dependencias
sudo -u cinema3d ./venv/bin/pip install -r requirements.txt

# Crear directorios necesarios
sudo -u cinema3d mkdir -p logs static/comprobantes static/qr

# Configurar permisos
sudo chown -R cinema3d:www-data /var/www/cinema3d
sudo chmod -R 755 /var/www/cinema3d

echo "✅ Cinema3D instalado correctamente"