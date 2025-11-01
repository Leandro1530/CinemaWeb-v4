# 🚀 GUÍA DE INSTALACIÓN - Cinema3D en VPS Hostinger

## 📋 Información del VPS
- **IP**: 31.97.174.96
- **Dominio**: is-lr3d.shop
- **Sistema**: Ubuntu/Debian
- **Usuario**: root

## 🔧 PASO A PASO

### 1. Conectar al VPS
```bash
ssh root@31.97.174.96
```

### 2. Ejecutar script de preparación
```bash
chmod +x install_on_vps.sh
./install_on_vps.sh
```

### 3. Copiar archivos de la aplicación
```bash
# Los archivos deben estar en /var/www/cinema3d/
cp -r * /var/www/cinema3d/
chown -R cinema3d:cinema3d /var/www/cinema3d
```

### 4. Instalar dependencias Python
```bash
cd /var/www/cinema3d
sudo -u cinema3d ./venv/bin/pip install -r requirements.txt
```

### 5. Configurar variables de entorno
```bash
cd /var/www/cinema3d
cp .env.production .env
# Editar .env con tus configuraciones reales
nano .env
```

### 6. Configurar Nginx
```bash
cp deploy/nginx_cinema3d.conf /etc/nginx/sites-available/cinema3d
ln -sf /etc/nginx/sites-available/cinema3d /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

### 7. Configurar Supervisor
```bash
cp deploy/supervisor_cinema3d.conf /etc/supervisor/conf.d/
supervisorctl reread
supervisorctl update
supervisorctl start cinema3d
```

### 8. Verificar funcionamiento
```bash
# Ver logs
tail -f /var/www/cinema3d/logs/gunicorn.log

# Ver estado
supervisorctl status

# Probar la aplicación
curl http://localhost:8000
```

## 🌍 Acceso
- **Dominio**: http://is-lr3d.shop
- **IP**: http://31.97.174.96

## 🔧 Comandos útiles
```bash
# Reiniciar aplicación
supervisorctl restart cinema3d

# Ver logs en tiempo real
tail -f /var/www/cinema3d/logs/gunicorn.log

# Reiniciar Nginx
systemctl reload nginx

# Ver estado del sistema
systemctl status nginx
supervisorctl status
```

## 🔒 Configurar SSL (Opcional)
```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d is-lr3d.shop
```

## ⚠️ Variables importantes a configurar en .env
- SECRET_KEY (cambiar por una clave segura)
- MERCADOPAGO_ACCESS_TOKEN (tu token real)
- MAIL_PASSWORD (si usas email)