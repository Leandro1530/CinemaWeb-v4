# 🚀 Manual de Despliegue - Cinema App

## 📋 Información del Servidor
- **VPS**: srv1060871.hstgr.cloud
- **IP**: 31.97.174.96
- **Dominio**: is-lr3d.shop
- **Sistema**: Ubuntu/Debian (recomendado)

## 🔧 Paso a Paso para Desplegar

### 1️⃣ Conectar al VPS
```bash
ssh root@31.97.174.96
# O si tienes un usuario específico:
ssh usuario@31.97.174.96
```

### 2️⃣ Configurar el servidor inicial
```bash
# Ejecutar el script de configuración inicial
chmod +x deploy.sh
sudo ./deploy.sh
```

### 3️⃣ Subir el código de la aplicación
```bash
# Opción A: Usando git (recomendado)
cd /var/www
sudo git clone https://github.com/tu-usuario/tu-repo.git cinema
cd cinema

# Opción B: Usando SCP desde tu máquina local
# scp -r C:\Users\Clari\Music\Web_3sprint\Web_v2 root@31.97.174.96:/var/www/cinema
```

### 4️⃣ Configurar variables de entorno
```bash
cd /var/www/cinema

# Copiar el archivo de producción
sudo cp .env.production .env

# Editar con tus datos reales
sudo nano .env
```

**⚠️ IMPORTANTE: Completar en el archivo .env:**
- `SECRET_KEY`: Generar una clave segura de 32+ caracteres
- `MP_ACCESS_TOKEN`: Tu token de acceso de MercadoPago
- `MP_PUBLIC_KEY`: Tu clave pública de MercadoPago
- `MAIL_USERNAME` y `MAIL_PASSWORD`: Datos de tu correo
- `DATABASE_URL`: postgresql://cinema_user:password_segura_aqui@localhost:5432/cinema_db

### 5️⃣ Instalar dependencias Python
```bash
cd /var/www/cinema
sudo -u www-data ./venv/bin/pip install -r requirements.txt
```

### 6️⃣ Configurar la base de datos
```bash
# Ejecutar migraciones
sudo -u www-data ./venv/bin/python -c "
from app import create_app
from app.db import create_schema
app = create_app()
with app.app_context():
    create_schema()
    print('Base de datos inicializada')
"
```

### 7️⃣ Configurar Nginx
```bash
# Copiar configuración de nginx
sudo cp nginx_config.conf /etc/nginx/sites-available/is-lr3d.shop
sudo ln -s /etc/nginx/sites-available/is-lr3d.shop /etc/nginx/sites-enabled/

# Verificar configuración
sudo nginx -t

# Reiniciar nginx
sudo systemctl restart nginx
```

### 8️⃣ Configurar el servicio systemd
```bash
# Copiar archivo de servicio
sudo cp cinema.service /etc/systemd/system/

# Copiar configuración de logrotate
sudo cp cinema_logrotate /etc/logrotate.d/cinema

# Recargar systemd y habilitar servicio
sudo systemctl daemon-reload
sudo systemctl enable cinema
sudo systemctl start cinema

# Verificar que está funcionando
sudo systemctl status cinema
```

### 9️⃣ Configurar SSL (HTTPS)
```bash
# Editar el script con tu email
sudo nano setup_ssl.sh
# Cambiar: EMAIL="tu_email@gmail.com"

# Ejecutar configuración SSL
chmod +x setup_ssl.sh
sudo ./setup_ssl.sh
```

### 🔟 Verificar DNS
Antes del SSL, asegúrate de que tu dominio apunte al servidor:
```bash
# Verificar DNS
dig +short is-lr3d.shop
# Debería mostrar: 31.97.174.96
```

## 🔍 Verificación y Monitoreo

### Verificar que todo funciona:
```bash
# Estado del servicio
sudo systemctl status cinema

# Logs de la aplicación
sudo tail -f /var/log/cinema/error.log

# Logs de nginx
sudo tail -f /var/log/nginx/cinema_error.log

# Verificar puertos
sudo netstat -tlnp | grep :8000  # Gunicorn
sudo netstat -tlnp | grep :80    # Nginx HTTP
sudo netstat -tlnp | grep :443   # Nginx HTTPS
```

### Comandos útiles:
```bash
# Reiniciar la aplicación
sudo systemctl restart cinema

# Reiniciar nginx
sudo systemctl restart nginx

# Ver logs en tiempo real
sudo journalctl -u cinema -f

# Verificar configuración nginx
sudo nginx -t
```

## 🛡️ Seguridad Adicional

### Configurar backup automático:
```bash
# Crear script de backup
sudo nano /usr/local/bin/backup_cinema.sh
```

### Monitoreo básico:
```bash
# Instalar htop para monitoreo
sudo apt install htop

# Verificar uso de recursos
htop
```

## 🚨 Troubleshooting

### Si la aplicación no inicia:
1. Verificar logs: `sudo journalctl -u cinema -n 50`
2. Verificar permisos: `ls -la /var/www/cinema`
3. Verificar variables de entorno: `sudo systemctl show cinema | grep Environment`

### Si nginx da error:
1. Verificar configuración: `sudo nginx -t`
2. Verificar logs: `sudo tail -f /var/log/nginx/error.log`
3. Verificar que gunicorn esté corriendo: `sudo netstat -tlnp | grep :8000`

### Si SSL falla:
1. Verificar DNS: `dig +short is-lr3d.shop`
2. Verificar puerto 80 abierto: `sudo netstat -tlnp | grep :80`
3. Verificar logs de certbot: `sudo tail -f /var/log/letsencrypt/letsencrypt.log`

## 📞 Contacto
Una vez que hayas completado estos pasos, tu aplicación debería estar funcionando en:
- **HTTP**: http://is-lr3d.shop (redirige a HTTPS)
- **HTTPS**: https://is-lr3d.shop

¡Tu aplicación de cinema estará lista para usar con MercadoPago funcionando! 🎬🍿