#!/bin/bash
# setup_ssl.sh - Script para configurar SSL con Let's Encrypt

DOMAIN="is-lr3d.shop"
EMAIL="tu_email@gmail.com"  # Cambia por tu email real
WEBROOT="/var/www/cinema"

echo "=== Configurando SSL para $DOMAIN ==="

# Verificar que nginx esté instalado
if ! command -v nginx &> /dev/null; then
    echo "Error: Nginx no está instalado"
    exit 1
fi

# Instalar certbot si no está instalado
if ! command -v certbot &> /dev/null; then
    echo "Instalando certbot..."
    apt update
    apt install -y certbot python3-certbot-nginx
fi

# Verificar que el dominio apunte al servidor
echo "Verificando DNS del dominio..."
DOMAIN_IP=$(dig +short $DOMAIN)
SERVER_IP=$(curl -s ifconfig.me)

if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
    echo "Advertencia: El dominio $DOMAIN no apunta a este servidor"
    echo "Dominio apunta a: $DOMAIN_IP"
    echo "IP del servidor: $SERVER_IP"
    echo "Por favor, configura el DNS antes de continuar"
    read -p "¿Continuar de todas formas? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Crear directorio para el desafío ACME
mkdir -p $WEBROOT/.well-known/acme-challenge
chown -R www-data:www-data $WEBROOT/.well-known

# Configurar nginx temporal para el desafío
cat > /etc/nginx/sites-available/temp-ssl-setup << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root $WEBROOT;
        try_files \$uri =404;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}
EOF

# Habilitar la configuración temporal
ln -sf /etc/nginx/sites-available/temp-ssl-setup /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Obtener certificado SSL
echo "Obteniendo certificado SSL..."
certbot certonly \
    --webroot \
    --webroot-path=$WEBROOT \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    --domains $DOMAIN,www.$DOMAIN

if [ $? -eq 0 ]; then
    echo "✅ Certificado SSL obtenido exitosamente"
    
    # Crear configuración nginx con SSL
    cat > /etc/nginx/sites-available/$DOMAIN << 'EOF'
# Redirección HTTP a HTTPS
server {
    listen 80;
    server_name is-lr3d.shop www.is-lr3d.shop;
    return 301 https://$server_name$request_uri;
}

# Configuración HTTPS
server {
    listen 443 ssl http2;
    server_name is-lr3d.shop www.is-lr3d.shop;

    # Certificados SSL
    ssl_certificate /etc/letsencrypt/live/is-lr3d.shop/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/is-lr3d.shop/privkey.pem;
    
    # Configuración SSL moderna
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    root /var/www/cinema;
    access_log /var/log/nginx/cinema_ssl_access.log;
    error_log /var/log/nginx/cinema_ssl_error.log;

    # Archivos estáticos
    location /static/ {
        alias /var/www/cinema/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Archivos de comprobantes (protegidos)
    location /static/comprobantes/ {
        alias /var/www/cinema/static/comprobantes/;
        internal;
        expires 1h;
    }

    # Archivos QR
    location /static/qr/ {
        alias /var/www/cinema/static/qr/;
        expires 1d;
    }

    # Proxy a la aplicación Flask
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Webhook de MercadoPago
    location /webhook/mercadopago {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # Bloquear archivos sensibles
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    location ~ \.(env|py|pyc|pyo|db)$ {
        deny all;
        access_log off;
        log_not_found off;
    }

    # Configuración de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    client_max_body_size 16M;
    client_body_timeout 60s;
    client_header_timeout 60s;

    # Compresión
    gzip on;
    gzip_vary on;
    gzip_min_length 1000;
    gzip_types
        text/plain
        text/css
        text/js
        text/xml
        text/javascript
        application/javascript
        application/json
        application/xml+rss;
}
EOF

    # Habilitar la nueva configuración
    rm -f /etc/nginx/sites-enabled/temp-ssl-setup
    ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
    
    # Verificar y recargar nginx
    nginx -t && systemctl reload nginx
    
    echo "✅ Configuración SSL completada"
    echo "🌐 Tu sitio está disponible en: https://$DOMAIN"
    
    # Configurar renovación automática
    echo "Configurando renovación automática..."
    (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
    
else
    echo "❌ Error al obtener el certificado SSL"
    echo "Verifica que:"
    echo "1. El dominio apunte a este servidor"
    echo "2. El puerto 80 esté abierto"
    echo "3. Nginx esté funcionando"
    exit 1
fi