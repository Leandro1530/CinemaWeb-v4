#!/usr/bin/env python3
# test_mercadopago.py - Script para probar la integración de MercadoPago

import os
import sys
from datetime import datetime

# Agregar el directorio de la app al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_mp_credentials():
    """Prueba las credenciales de MercadoPago"""
    print("🔑 Probando credenciales de MercadoPago...")
    
    try:
        import mercadopago
        
        # Usar las credenciales reales
        access_token = "APP_USR-2229963271715129-101016-bd6c6658b787c662a7dee2a84a2ce61f-374207808"
        public_key = "APP_USR-893a9f3c-59f1-4728-84d0-d24ccc8383b8"
        
        # Inicializar SDK
        sdk = mercadopago.SDK(access_token)
        
        # Probar obteniendo información de la cuenta
        result = sdk.user().get()
        
        if result["status"] == 200:
            user_info = result["response"]
            print(f"✅ Credenciales válidas!")
            print(f"   Usuario: {user_info.get('first_name', 'N/A')} {user_info.get('last_name', 'N/A')}")
            print(f"   Email: {user_info.get('email', 'N/A')}")
            print(f"   ID: {user_info.get('id', 'N/A')}")
            print(f"   País: {user_info.get('country_id', 'N/A')}")
            return True
        else:
            print(f"❌ Error al obtener información del usuario: {result}")
            return False
            
    except ImportError:
        print("❌ SDK de MercadoPago no instalado. Ejecuta: pip install mercadopago")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_create_preference():
    """Prueba crear una preferencia de pago"""
    print("\n💳 Probando creación de preferencia...")
    
    try:
        import mercadopago
        
        access_token = "APP_USR-2229963271715129-101016-bd6c6658b787c662a7dee2a84a2ce61f-374207808"
        sdk = mercadopago.SDK(access_token)
        
        # Crear preferencia de prueba
        preference_data = {
            "items": [
                {
                    "id": "entrada_test",
                    "title": "Entrada - Película Test",
                    "description": "Función de prueba",
                    "category_id": "tickets",
                    "quantity": 1,
                    "unit_price": 2500.00,
                    "currency_id": "ARS"
                }
            ],
            "payer": {
                "email": "test@test.com"
            },
            "external_reference": f"TEST_{int(datetime.now().timestamp())}",
            "statement_descriptor": "CINEMA APP",
            "back_urls": {
                "success": "http://localhost:5000/webhook/success",
                "failure": "http://localhost:5000/webhook/failure",
                "pending": "http://localhost:5000/webhook/pending"
            },
            "auto_return": "approved"
        }
        
        result = sdk.preference().create(preference_data)
        
        if result["status"] == 201:
            preference = result["response"]
            print(f"✅ Preferencia creada exitosamente!")
            print(f"   ID: {preference['id']}")
            print(f"   Init Point: {preference['init_point']}")
            print(f"   Sandbox: {preference.get('sandbox_init_point', 'N/A')}")
            return True
        else:
            print(f"❌ Error creando preferencia: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_app_integration():
    """Prueba la integración con la app Flask"""
    print("\n🔧 Probando integración con la app...")
    
    try:
        # Configurar variables de entorno
        os.environ['MP_ACCESS_TOKEN'] = "APP_USR-2229963271715129-101016-bd6c6658b787c662a7dee2a84a2ce61f-374207808"
        os.environ['MP_PUBLIC_KEY'] = "APP_USR-893a9f3c-59f1-4728-84d0-d24ccc8383b8"
        
        # Importar servicio
        from app.service.mercadopago_service import mp_service
        
        # Crear items de prueba
        entradas = [{
            "funcion_id": 1,
            "asiento": "A1",
            "precio": 2500.00,
            "pelicula": "Test Movie",
            "fecha": "2025-10-20",
            "hora": "20:00"
        }]
        
        combos = [{
            "id": 1,
            "nombre": "Combo Test",
            "descripcion": "Test combo",
            "precio": 1500.00,
            "cantidad": 1
        }]
        
        items = mp_service.crear_items_desde_carrito(entradas, combos)
        
        resultado = mp_service.crear_preferencia_pago(
            items=items,
            payer_email="test@test.com",
            external_reference=f"APP_TEST_{int(datetime.now().timestamp())}",
            metadata={"test": True}
        )
        
        if resultado["success"]:
            print(f"✅ Integración con la app funcionando!")
            print(f"   Preference ID: {resultado['preference_id']}")
            print(f"   Total: ${resultado['total']}")
            print(f"   Public Key: {resultado['public_key'][:20]}...")
            return True
        else:
            print(f"❌ Error en integración: {resultado}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def main():
    """Función principal"""
    print("🧪 Probando integración de MercadoPago para Cinema App")
    print("=" * 60)
    
    # Pruebas
    tests = [
        test_mp_credentials,
        test_create_preference,
        test_app_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print("-" * 40)
    
    print(f"\n📊 Resultado: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! La integración está lista.")
        print("\n🚀 Próximos pasos:")
        print("1. Configura tu email en .env para las notificaciones")
        print("2. Despliega en tu servidor usando el manual")
        print("3. Configura los webhooks en el panel de MercadoPago")
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa la configuración.")

if __name__ == "__main__":
    main()