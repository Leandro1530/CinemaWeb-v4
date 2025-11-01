# 🚀 GUÍA DE DESPLIEGUE - Cinema App con MercadoPago

## 📦 **ARCHIVOS A TRANSFERIR AL SERVIDOR**

### 🎯 **Información del Servidor**
- **IP**: 31.97.174.96
- **Dominio**: is-lr3d.shop
- **Usuario**: root
- **Puerto SSH**: 22

---

## 📋 **PASO 1: TRANSFERIR ARCHIVOS CON WINSCP**

### 🔧 **Configuración WinSCP**
1. **Host**: `31.97.174.96`
2. **Usuario**: `root`
3. **Puerto**: `22`
4. **Protocolo**: SFTP

### 📁 **Archivos a transferir** (desde `C:\Users\Clari\Music\Web_3sprint\Web_v2\`)
```
TODA LA CARPETA Web_v2/ 
├── app/                    # Código de la aplicación
├── templates/              # Templates HTML
├── static/                 # CSS, JS, imágenes
├── requirements.txt        # Dependencias Python
├── wsgi.py                # Entrada principal
├── config.py              # Configuraciones
├── .env.production        # Variables de producción
├── deploy.sh              # Script de despliegue
├── start_app.sh           # Script de inicio
├── gunicorn.conf.py       # Config gunicorn
├── cinema.service         # Servicio systemd
├── nginx_config.conf      # Config nginx
└── setup_ssl.sh           # SSL automático
```

### 🎯 **Ubicación en el servidor**
- Subir todo a: `/var/www/cinema/`

---

## ⚡ **PASO 2: COMANDOS EN PUTTY (SSH)**

### 🔑 **Conectar con PuTTY**
```bash
# Host: 31.97.174.96
# Puerto: 22
# Usuario: root
```

### 📦 **Una vez conectado, ejecutar:**

```bash
# 1. Actualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar dependencias del sistema
sudo apt install -y python3 python3-pip python3-venv nginx git curl

# 3. Crear directorio de la aplicación
sudo mkdir -p /var/www/cinema
sudo chown $USER:$USER /var/www/cinema

# 4. Navegar al directorio (después de subir archivos con WinSCP)
cd /var/www/cinema

# 5. Crear entorno virtual
python3 -m venv venv

# 6. Activar entorno virtual
source venv/bin/activate

# 7. Instalar dependencias Python
pip install -r requirements.txt

# 8. Hacer ejecutables los scripts
chmod +x deploy.sh start_app.sh setup_ssl.sh

# 9. Ejecutar despliegue automático
sudo ./deploy.sh

# 10. Configurar SSL (opcional pero recomendado)
sudo ./setup_ssl.sh
```

---

## 🌐 **PASO 3: VERIFICAR FUNCIONAMIENTO**

### ✅ **Verificar servicios**
```bash
# Estado de la aplicación
sudo systemctl status cinema

# Estado de nginx
sudo systemctl status nginx

# Ver logs de la aplicación
sudo journalctl -u cinema -f

# Ver logs de nginx
sudo tail -f /var/log/nginx/error.log
```

### 🔍 **URLs a probar**
- **HTTP**: `http://31.97.174.96`
- **HTTPS**: `https://is-lr3d.shop` (después del SSL)
- **Pago MercadoPago**: `https://is-lr3d.shop/pago-mp/`
- **Admin**: `https://is-lr3d.shop/admin`

---

## 🛠️ **PASO 4: SOLUCIÓN DE PROBLEMAS COMUNES**

### 🔥 **Si hay errores:**

```bash
# Reiniciar aplicación
sudo systemctl restart cinema

# Reiniciar nginx
sudo systemctl restart nginx

# Ver logs detallados
sudo journalctl -u cinema --no-pager -l

# Verificar configuración nginx
sudo nginx -t

# Verificar puertos abiertos
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443
```

### 🔐 **Configurar firewall (si es necesario)**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

---

## 📱 **PASO 5: CONFIGURAR WEBHOOKS MERCADOPAGO**

### 🔗 **En el panel de MercadoPago:**
1. Ir a: https://www.mercadopago.com.ar/developers/
2. Seleccionar tu aplicación
3. Configurar webhook: `https://is-lr3d.shop/webhook/mercadopago`

---

## 🎯 **RESUMEN DE ACCIONES**

1. **WinSCP**: Subir toda la carpeta `Web_v2` a `/var/www/cinema/`
2. **PuTTY**: Conectar y ejecutar comandos de instalación
3. **Verificar**: Probar URLs y funcionalidades
4. **SSL**: Configurar certificado (opcional)
5. **Webhooks**: Configurar en MercadoPago

---

**🎬 ¡Tu aplicación estará lista en producción!**

### 📞 **¿Necesitas ayuda durante el proceso?**
- Envía capturas de pantalla de cualquier error
- Copia y pega los logs si algo falla
- Te ayudo a solucionarlo paso a paso

**¡Empezamos con WinSCP! 🚀**