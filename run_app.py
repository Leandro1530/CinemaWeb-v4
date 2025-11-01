# run_app.py - Script para ejecutar la aplicación con configuración automática

import os
import sys
from pathlib import Path

def setup_environment():
    """Configura el entorno automáticamente"""
    
    # Determinar si estamos en desarrollo o producción
    is_production = os.getenv('FLASK_ENV') == 'production' or os.path.exists('/.dockerenv')
    
    # Cargar el archivo .env correspondiente
    if is_production:
        env_file = '.env.production'
        print("🚀 Modo PRODUCCIÓN detectado")
    else:
        env_file = '.env.development'
        print("🔧 Modo DESARROLLO detectado")
    
    # Verificar que el archivo .env existe
    if not os.path.exists(env_file):
        print(f"❌ Error: No se encontró {env_file}")
        print("📋 Archivos .env disponibles:")
        for f in os.listdir('.'):
            if f.startswith('.env'):
                print(f"   - {f}")
        sys.exit(1)
    
    # Cargar variables de entorno desde el archivo
    from dotenv import load_dotenv
    load_dotenv(env_file)
    print(f"✅ Variables cargadas desde {env_file}")
    
    # Verificar credenciales críticas
    required_vars = ['MP_ACCESS_TOKEN', 'MP_PUBLIC_KEY', 'SECRET_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Error: Variables faltantes en {env_file}:")
        for var in missing_vars:
            print(f"   - {var}")
        sys.exit(1)
    
    print("✅ Todas las variables críticas están configuradas")
    return is_production

def run_app():
    """Ejecuta la aplicación"""
    
    is_production = setup_environment()
    
    # Importar la aplicación
    try:
        from wsgi import app
        print("✅ Aplicación importada correctamente")
    except ImportError as e:
        print(f"❌ Error importando la aplicación: {e}")
        sys.exit(1)
    
    # Configurar y ejecutar
    if is_production:
        print("🚀 Iniciando en modo PRODUCCIÓN")
        print("💡 Para desarrollo, usa: python run_app.py --dev")
        # En producción, normalmente se usa gunicorn
        print("⚠️  En producción, usa gunicorn:")
        print("   gunicorn -c gunicorn.conf.py wsgi:app")
    else:
        print("🔧 Iniciando en modo DESARROLLO")
        host = os.getenv('FLASK_RUN_HOST', '127.0.0.1')
        port = int(os.getenv('FLASK_RUN_PORT', 5000))
        debug = os.getenv('FLASK_DEBUG', 'True').lower() in ['true', '1', 'yes']
        
        print(f"🌐 Servidor: http://{host}:{port}")
        print(f"🔍 Debug: {debug}")
        print(f"💳 MercadoPago: Configurado")
        print("\n🎬 ¡Cinema App lista!")
        print("=" * 40)
        
        app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    # Verificar argumentos
    if len(sys.argv) > 1 and sys.argv[1] == '--dev':
        os.environ['FLASK_ENV'] = 'development'
    
    run_app()