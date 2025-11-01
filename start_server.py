#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script temporal para iniciar el servidor Flask
"""

import os
import sys
from pathlib import Path

# Agregar el directorio actual al path de Python
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Cambiar al directorio del proyecto
os.chdir(current_dir)

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Importar la aplicación
from app import create_app

if __name__ == '__main__':
    try:
        print("🔄 Iniciando Cinema3D...")
        app = create_app()
        
        print("📋 Configuración:")
        print(f"   • MercadoPago: {'✅ Configurado' if app.config.get('MERCADOPAGO_ACCESS_TOKEN') else '❌ No configurado'}")
        print(f"   • Precio entrada: ${app.config.get('TICKET_PRICE')}")
        print("📍 Rutas disponibles:")
        print("   • http://127.0.0.1:5000/ - Página principal")
        print("   • http://127.0.0.1:5000/cartelera - Ver películas") 
        print("   • http://127.0.0.1:5000/pago - Sistema de pago unificado")
        print("   • http://127.0.0.1:5000/admin - Panel de administración")
        print()
        print("✅ Servidor iniciado correctamente!")
        print("🌍 Para acceder: http://127.0.0.1:5000")
        print("⚠️  Presiona Ctrl+C para detener")
        print()
        
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=True,
            use_reloader=False  # Deshabilitar para evitar problemas
        )
        
    except Exception as e:
        print(f"❌ Error al iniciar la aplicación: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)