# wsgi.py — autodetección de tu app Flask (simple y sin romper tu backend)
# Colocá este archivo en la raíz del proyecto y corré:  python -m flask run
import os, sys, importlib

# Asegura que la carpeta actual esté en el sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Candidatos comunes de paquete/archivo donde suele estar la app
CANDIDATES = [
    # paquetes (carpetas con __init__.py)
    "app", "cine", "backend", "src", "application", "project",
    # módulos sueltos
    "app", "main", "server", "wsgi",
]

app = None
last_err = None

for name in CANDIDATES:
    try:
        mod = importlib.import_module(name)
    except Exception as e:
        last_err = e
        continue

    # 1) Factory create_app()
    create = getattr(mod, "create_app", None)
    if callable(create):
        try:
            app = create()
            break
        except Exception as e:
            last_err = e
            # si falla la factory, probamos siguiente candidate
            pass

    # 2) Objeto app = Flask(...)
    obj = getattr(mod, "app", None)
    if obj is not None:
        app = obj
        break

if app is None:
    raise RuntimeError(
        "wsgi.py no pudo ubicar tu aplicación Flask automáticamente.\n"
        "Probé módulos/paquetes: %s\n"
        "Soluciones:\n"
        "  A) Editá este archivo y reemplazá manualmente las 2 líneas por:\n"
        "       from NOMBRE_REAL import create_app\n"
        "       app = create_app()\n"
        "     o bien:\n"
        "       from NOMBRE_REAL import app as app\n"
        "  B) Corré con nombre explícito:\n"
        "       set FLASK_APP=NOMBRE_REAL:create_app   (o NOMBRE_REAL:app)\n"
        "       python -m flask run\n\n"
        "Último error visto: %r"
        % (", ".join(CANDIDATES), last_err)
    )
