#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para el sistema de recuperación de contraseñas
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.db_migrations import migrate_add_password_reset_support
from app.db import create_password_reset_token, validate_password_reset_token, use_password_reset_token

def test_password_reset_system():
    """Prueba el sistema de recuperación de contraseñas"""
    
    app = create_app()
    
    with app.app_context():
        print("🧪 Iniciando pruebas del sistema de recuperación de contraseñas...")
        
        # 1. Ejecutar migración
        print("\n📊 Ejecutando migración...")
        try:
            migrate_add_password_reset_support()
            print("✅ Migración ejecutada correctamente")
        except Exception as e:
            print(f"❌ Error en migración: {e}")
            return False
        
        # 2. Probar crear token (usando user_id ficticio)
        print("\n🔑 Probando creación de token...")
        try:
            # Supongamos que existe un usuario con ID 1
            token = create_password_reset_token(1)
            print(f"✅ Token creado: {token[:10]}...")
        except Exception as e:
            print(f"❌ Error creando token: {e}")
            return False
        
        # 3. Probar validación de token
        print("\n🔍 Probando validación de token...")
        try:
            user_id = validate_password_reset_token(token)
            if user_id == 1:
                print("✅ Token validado correctamente")
            else:
                print(f"❌ Token retornó user_id incorrecto: {user_id}")
                return False
        except Exception as e:
            print(f"❌ Error validando token: {e}")
            return False
        
        # 4. Probar usar token
        print("\n🎯 Probando uso de token...")
        try:
            result = use_password_reset_token(token)
            if result:
                print("✅ Token marcado como usado")
            else:
                print("❌ Error marcando token como usado")
                return False
        except Exception as e:
            print(f"❌ Error usando token: {e}")
            return False
        
        # 5. Probar validar token usado
        print("\n🚫 Probando validación de token usado...")
        try:
            user_id = validate_password_reset_token(token)
            if user_id is None:
                print("✅ Token usado no es válido (comportamiento esperado)")
            else:
                print(f"❌ Token usado sigue siendo válido: {user_id}")
                return False
        except Exception as e:
            print(f"❌ Error validando token usado: {e}")
            return False
        
        print("\n🎉 ¡Todas las pruebas pasaron correctamente!")
        print("\n📝 Sistema de recuperación de contraseñas implementado:")
        print("   • Rutas: /forgot-password y /reset-password/<token>")
        print("   • Templates: forgot_password.html y reset_password.html")
        print("   • Enlace agregado en login.html")
        print("   • Base de datos actualizada con tabla password_reset_tokens")
        print("   • Integración con servicio de email existente")
        
        return True

if __name__ == "__main__":
    test_password_reset_system()