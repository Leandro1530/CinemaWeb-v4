# 📋 CHECKLIST DESPLIEGUE - Paso a Paso

## ✅ **ESTADO ACTUAL**
- [x] Aplicación funcionando localmente: `http://127.0.0.1:5000`
- [x] MercadoPago configurado con credenciales reales
- [x] Base de datos migrada correctamente
- [x] Scripts de despliegue creados
- [x] Configuración nginx y SSL lista

---

## 🚀 **PASO 1: WINSCP - TRANSFERIR ARCHIVOS**

### 📁 **Configuración WinSCP**
```
Host: 31.97.174.96
Usuario: root
Puerto: 22
Protocolo: SFTP
```

### 📂 **Archivos a subir**
Desde `C:\Users\Clari\Music\Web_3sprint\Web_v2\` 
Subir **TODA la carpeta** a `/var/www/cinema/`

**⚠️ IMPORTANTE**: 
- Crear primero la carpeta `/var/www/cinema/` en el servidor
- Transferir TODO el contenido de `Web_v2` dentro de esa carpeta

---

## 🔧 **PASO 2: PUTTY - COMANDOS EN SERVIDOR**

### 🔑 **Conectar SSH**
```
Host: 31.97.174.96
Puerto: 22
Usuario: root
```

### ⚡ **Comandos a ejecutar (uno por uno)**

```bash
# 1. Verificar archivos subidos
ls -la /var/www/cinema/

# 2. Ir al directorio
cd /var/www/cinema

# 3. Hacer ejecutables los scripts
chmod +x deploy.sh setup_ssl.sh start_app.sh

# 4. Ejecutar despliegue
sudo ./deploy.sh

# 5. (Opcional) Configurar SSL
sudo ./setup_ssl.sh
```

---

## 🔍 **PASO 3: VERIFICACIÓN**

### ✅ **Comandos de verificación**
```bash
# Estado de servicios
sudo systemctl status cinema
sudo systemctl status nginx

# Ver logs si hay errores
sudo journalctl -u cinema -f

# Probar conectividad
curl -I http://31.97.174.96
```

### 🌐 **URLs a probar**
- **HTTP**: http://31.97.174.96
- **Dominio**: http://is-lr3d.shop (después de configurar DNS)
- **HTTPS**: https://is-lr3d.shop (después del SSL)

---

## 🎯 **CONFIGURACIONES FINALES**

### 🔗 **MercadoPago Webhooks**
1. Ir a: https://www.mercadopago.com.ar/developers/
2. Tu aplicación → Webhooks
3. Configurar: `https://is-lr3d.shop/webhook/mercadopago`

### 🌐 **DNS (si no está configurado)**
En tu proveedor de dominio, apuntar:
- `A record`: `is-lr3d.shop` → `31.97.174.96`
- `CNAME`: `www.is-lr3d.shop` → `is-lr3d.shop`

---

## 🆘 **SI HAY PROBLEMAS**

### 🔥 **Errores comunes y soluciones**

**Error de permisos:**
```bash
sudo chown -R www-data:www-data /var/www/cinema
sudo chmod -R 755 /var/www/cinema
```

**Error de puerto:**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo systemctl restart nginx
```

**Error de Python:**
```bash
cd /var/www/cinema
source venv/bin/activate
pip install -r requirements.txt
```

**Reiniciar todo:**
```bash
sudo systemctl restart cinema
sudo systemctl restart nginx
```

---

## ⏱️ **TIEMPO ESTIMADO**
- Transferencia archivos: 5-10 minutos
- Despliegue automático: 10-15 minutos
- Configuración SSL: 5 minutos
- **Total**: ~30 minutos

---

## 📞 **¿LISTO PARA EMPEZAR?**

1. **Abre WinSCP** y conecta a tu servidor
2. **Sube todos los archivos** a `/var/www/cinema/`
3. **Abre PuTTY** y ejecuta los comandos
4. **¡Listo!** Tu app estará en línea

**🎬 ¡Comenzamos con el despliegue!**