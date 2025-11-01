# Cinema3D – WebApp (Flask)

Webapp de venta de entradas de cine con flujo completo: **cartelera → reserva de asientos → combos → pago simulado → comprobante PDF + QR → envío por email**.

---

## 🚀 Características

- ✅ Flujo end-to-end de compra (sin PSP real).
- 🔐 Validaciones de tarjeta: **Luhn**, marca (Visa/Master/Amex), **CVV** y **vencimiento**.
- 🧾 Generación de **PDF** con **FPDF2** y **QR** (PNG) con **qrcode**.
- ✉️ Envío por email vía **Flask-Mail** (modo *debug* opcional).
- 🗂️ Almacenamiento de comprobantes y QR en carpetas dedicadas.
- 🗃️ Base **SQLite** simple para usuarios y transacciones.
- 🧱 Arquitectura modular (Blueprints + Services).

---

## 📦 Stack

- **Python 3.10+**, **Flask 3.x**
- **Jinja2**, **Werkzeug**
- **SQLite**
- **Flask-Mail**, **python-dotenv**
- **fpdf2**, **qrcode[pil]**
- **pytest** (para testing)

---

## 📂 Estructura de carpetas

```text
cinema/
  __init__.py            # create_app(), config base y registro de blueprints
  extensions.py          # mail, (luego limiter, etc.)
  db.py                  # helper sqlite (get_conn) + create_schema()
  data/
    seed.py              # MOVIES, BRANCHES, COMBOS_CATALOG
  services/
    payments.py          # luhn, detectar_brand, validaciones
    pdfs.py              # generar_comprobante_pdf(...)
    qrs.py               # generar_qr(...)
    emailer.py           # enviar_ticket(...)
  blueprints/
    main.py              # bienvenida, set/clear branch
    venta.py             # cartelera, asientos, combos, confirmación
    pago.py              # pago (GET/POST), inserta transacción, PDF/QR/email
    archivos.py          # descarga de comprobante (ideal: autenticada)
templates/
static/
  comprobantes/          # PDFs generados (en dev; en prod, fuera de /static)
  qr/                    # PNGs de QR generados (ídem)
wsgi.py                  # entrypoint (flask run / gunicorn / waitress)
requirements.txt
requirements-dev.txt
.env.example
README.md
```

> Mantener **un solo punto de arranque**: `wsgi.py`.

---

## ⚙️ Instalación

1) **Clonar repo y entrar**
```bash
git clone https://github.com/tuusuario/cinema3d.git
cd cinema3d
```

2) **Crear venv + instalar deps**
- Windows (PowerShell):
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

- Linux/macOS (Bash):
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

3) **Configurar .env**
```bash
cp .env.example .env
```
Completar:
```
FLASK_SECRET=clave-larga-aleatoria
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_cuenta@example.com
SMTP_PASS=tu_password_o_app_password
SENDER_NAME=Cinema3D
EMAIL_DEBUG=1
DB_PATH=usuarios.db
COMPROBANTES_DIR=static/comprobantes
QR_DIR=static/qr
DEFAULT_BRANCH=Cine Pelagio B. Luna 960
```

4) **Ejecutar**
```bash
flask --app wsgi run --debug
```
Corre en: `http://127.0.0.1:5000/`.

---

## 🔄 Flujo funcional

1. Bienvenida → elegir sucursal.
2. Cartelera → seleccionar película/función.
3. Reserva de asientos → elegir butacas.
4. Combos → seleccionar combos opcionales.
5. Confirmación → revisar.
6. Pago (simulado) → valida tarjeta, guarda en SQLite.
7. Genera comprobante PDF + QR, lo descarga y (si EMAIL_DEBUG=0) envía por email.

---

## 🗃️ Base de datos

- SQLite (`usuarios.db`)
- Inicializa en el arranque con `create_schema()`.
- **No** versionar la DB (ya está en `.gitignore`).

---

## 🔐 Seguridad

- Siempre definir `FLASK_SECRET` en `.env`.
- Evitar exponer PDFs/QR en `/static` en producción.
- Agregar CSRF (Flask-WTF) para formularios sensibles.
- Configurar headers de seguridad (`X-Content-Type-Options`, `Referrer-Policy`, `CSP`).

---

## 🚀 Despliegue

- Linux:
  ```bash
  pip install gunicorn
  gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
  ```
- Windows:
  ```powershell
  pip install waitress
  waitress-serve --listen=0.0.0.0:8000 wsgi:app
  ```

Servir `/static` con Nginx/Apache o CDN.

---

## 🧪 Testing

### Instalar dependencias de desarrollo
```bash
pip install -r requirements-dev.txt
```

### Ejecutar tests
```bash
pytest
```

### Cobertura
```bash
pytest --cov=app --cov-report=term-missing
```

### Estructura de tests
- `tests/test_payments.py`: pruebas unitarias de validaciones de tarjeta.
- `tests/test_app_flow.py`: smoke tests del flujo de vistas (cartelera → asientos → combos → confirmación → pago GET).
- `tests/conftest.py`: fabrica la app con `create_app()` y DB temporal.

---

## 📋 Roadmap

- [ ] Proteger POSTs con CSRF (Flask-WTF).
- [ ] Mover PDFs/QR fuera de `/static` en prod.
- [ ] Agregar Flask-Limiter para rate limiting en `/pago`.
- [ ] CI con pytest + cobertura.

---

## 📜 Licencia

MIT (o la que definas).
