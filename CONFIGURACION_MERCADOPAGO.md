# 💳 Configuración de MercadoPago para Cinema App

## 🔧 Configuración Requerida

### 1. Credenciales de MercadoPago

Para obtener tus credenciales de MercadoPago:

1. **Crea una cuenta en MercadoPago** (si no tienes):
   - Ve a [developers.mercadopago.com](https://developers.mercadopago.com)
   - Crea tu cuenta de desarrollador

2. **Obtén tus credenciales**:
   - **Access Token**: Token para realizar operaciones
   - **Public Key**: Clave pública para el frontend
   - **Client ID** y **Client Secret**: Para OAuth (opcional)

3. **Configura en el archivo .env**:
   ```bash
   # MercadoPago - TUS CREDENCIALES REALES
   MP_ACCESS_TOKEN=APP_USR-2229963271715129-101016-bd6c6658b787c662a7dee2a84a2ce61f-374207808
   MP_PUBLIC_KEY=APP_USR-893a9f3c-59f1-4728-84d0-d24ccc8383b8
   ```

### 2. URLs de Callback

En tu panel de MercadoPago, configura estas URLs:

```bash
# URLs que ya están configuradas en .env.production
MP_WEBHOOK_URL=https://is-lr3d.shop/webhook/mercadopago    # Notificaciones automáticas
MP_SUCCESS_URL=https://is-lr3d.shop/webhook/success        # Pago exitoso
MP_FAILURE_URL=https://is-lr3d.shop/webhook/failure        # Pago fallido
MP_PENDING_URL=https://is-lr3d.shop/webhook/pending        # Pago pendiente
```

### 3. Configuración de Webhooks

1. **En el panel de MercadoPago**:
   - Ve a **Configuración** → **Webhooks**
   - Agrega la URL: `https://is-lr3d.shop/webhook/mercadopago`
   - Selecciona los eventos: `payment`, `merchant_order`

2. **Verificar en el servidor**:
   ```bash
   # Verificar que el webhook recibe notificaciones
   tail -f /var/log/cinema/app.log | grep "Webhook MP"
   ```

## 🔧 Configuración del Servidor

### 1. Instalar dependencias adicionales

Actualiza el requirements.txt que ya creamos:
```bash
pip install mercadopago>=2.2
```

### 2. Configurar variables de entorno

Edita `/var/www/cinema/.env`:
```bash
# ---- MERCADO PAGO (PRODUCCIÓN) ----
MP_ACCESS_TOKEN=APP_USR-2229963271715129-101016-bd6c6658b787c662a7dee2a84a2ce61f-374207808
MP_PUBLIC_KEY=APP_USR-893a9f3c-59f1-4728-84d0-d24ccc8383b8
MP_WEBHOOK_URL=https://is-lr3d.shop/webhook/mercadopago
MP_SUCCESS_URL=https://is-lr3d.shop/webhook/success  
MP_FAILURE_URL=https://is-lr3d.shop/webhook/failure
MP_PENDING_URL=https://is-lr3d.shop/webhook/pending

# ---- EMAIL PARA NOTIFICACIONES ----
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=tu_email@gmail.com
MAIL_PASSWORD=tu_app_password_de_gmail  # No usar tu contraseña normal
MAIL_DEFAULT_SENDER=tu_email@gmail.com
```

### 3. Configurar SSL para webhooks

⚠️ **IMPORTANTE**: MercadoPago requiere HTTPS para webhooks en producción.

```bash
# Asegúrate de que SSL esté configurado
sudo systemctl status nginx
sudo systemctl status cinema

# Verificar certificados
sudo certbot certificates
```

## 🧪 Testing

### 1. Credenciales de Test

Para pruebas, usa credenciales de sandbox:
```bash
# Test credentials (usar solo en desarrollo)
MP_ACCESS_TOKEN=TEST-1234567890-abcdef-ghijklmnopqrstuvwxyz-123456789
MP_PUBLIC_KEY=TEST-12345678-abcd-4321-efgh-123456789012
```

### 2. Tarjetas de prueba

Para testear pagos:
- **Visa aprobada**: 4509 9535 6623 3704
- **Mastercard aprobada**: 5031 7557 3453 0604
- **Visa rechazada**: 4000 0000 0000 0002
- **CVV**: 123 (cualquier CVV de 3 dígitos)
- **Vencimiento**: Cualquier fecha futura

### 3. Verificar funcionamiento

```bash
# 1. Crear una compra de prueba
curl -X POST https://is-lr3d.shop/pago/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "metodo_pago=mercadopago&email=test@test.com"

# 2. Verificar logs
tail -f /var/log/cinema/app.log

# 3. Verificar base de datos
sqlite3 /var/www/cinema/instance/cinema_prod.db
SELECT * FROM transacciones ORDER BY created_at DESC LIMIT 5;
```

## 📊 Monitoreo

### 1. Logs importantes

```bash
# Logs de la aplicación
tail -f /var/log/cinema/app.log | grep -E "(MercadoPago|Webhook|Payment)"

# Logs de nginx
tail -f /var/log/nginx/cinema_ssl_access.log | grep webhook

# Logs del sistema
journalctl -u cinema -f
```

### 2. Verificar estado de pagos

```bash
# Conectar a la base de datos
sqlite3 /var/www/cinema/instance/cinema_prod.db

# Consultas útiles
SELECT estado, COUNT(*) FROM transacciones GROUP BY estado;
SELECT * FROM transacciones WHERE mp_payment_id IS NOT NULL ORDER BY created_at DESC LIMIT 10;
SELECT * FROM payment_logs ORDER BY created_at DESC LIMIT 20;
```

## 🚨 Troubleshooting

### Problemas comunes:

1. **Webhooks no llegan**:
   - Verificar SSL: `curl -I https://is-lr3d.shop`
   - Verificar URL en panel MP
   - Revisar firewall: `sudo ufw status`

2. **Error al crear preferencia**:
   - Verificar credentials: `echo $MP_ACCESS_TOKEN`
   - Verificar conexión: `curl -X GET "https://api.mercadopago.com/v1/account/me" -H "Authorization: Bearer $MP_ACCESS_TOKEN"`

3. **Pagos no se actualizan**:
   - Verificar logs: `grep "webhook" /var/log/cinema/app.log`
   - Verificar base de datos: transacciones con estado PENDIENTE

4. **Emails no se envían**:
   - Verificar config SMTP: `EMAIL_DEBUG=0`
   - Verificar password de app Gmail (no contraseña normal)

### Comandos de diagnóstico:

```bash
# Verificar servicio funcionando
curl -s https://is-lr3d.shop/pago/estado/1 | jq .

# Probar webhook manualmente
curl -X POST https://is-lr3d.shop/webhook/mercadopago \
  -H "Content-Type: application/json" \
  -d '{"action":"test","data":{"id":"123"}}'

# Verificar conexión con MP
curl -H "Authorization: Bearer $MP_ACCESS_TOKEN" \
  https://api.mercadopago.com/v1/account/me
```

## 🔒 Seguridad

1. **Variables de entorno**: Nunca commitear credentials reales
2. **HTTPS**: Obligatorio para webhooks en producción  
3. **Validación**: Verificar que webhooks vengan de MercadoPago
4. **Logs**: No loggear tokens completos

## 📈 Métricas importantes

- Tasa de conversión de pagos
- Tiempo promedio de procesamiento
- Métodos de pago más usados
- Errores de webhooks

¡Tu integración con MercadoPago está lista! 🎉