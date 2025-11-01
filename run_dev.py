#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para ejecutar la aplicación en modo desarrollo
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

from app import create_app

if __name__ == '__main__':
    app = create_app()
    
    print("🚀 Iniciando Cinema3D...")
    print("📋 Configuración:")
    print(f"   • MercadoPago: {'✅ Configurado' if app.config.get('MERCADOPAGO_ACCESS_TOKEN') else '❌ No configurado'}")
    print(f"   • Precio entrada: ${app.config.get('TICKET_PRICE')}")
    print("📍 Rutas disponibles:")
    print("   • http://localhost:5000/ - Página principal")
    print("   • http://localhost:5000/cartelera - Ver películas")
    print("   • http://localhost:5000/pago - Sistema de pago unificado")
    print("   • http://localhost:5000/admin - Panel de administración")
    print()
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True
    )