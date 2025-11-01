# app/service/payments.py
import re, datetime as dt

def luhn_ok(pan: str) -> bool:
    s = ''.join(ch for ch in pan if ch.isdigit())
    if not s: return False
    tot = 0; alt = False
    for d in s[::-1]:
        n = ord(d) - 48
        if alt:
            n *= 2
            if n > 9: n -= 9
        tot += n
        alt = not alt
    return (tot % 10) == 0

def detectar_brand(pan: str) -> str:
    s = ''.join(ch for ch in pan if ch.isdigit())
    if s.startswith('4') and len(s) in (13,16,19): return "VISA"
    if s[:2] in {str(n) for n in range(51,56)} and len(s) == 16: return "MASTERCARD"
    if s[:2] in {"34","37"} and len(s) == 15: return "AMEX"
    return "DESCONOCIDA"

def vencimiento_valido(mes: int, anio: int) -> bool:
    if mes < 1 or mes > 12 or anio < 2000: return False
    # normalizar anio de 2 dígitos (25 -> 2025)
    if anio < 100: anio += 2000
    hoy = dt.date.today()
    # válido hasta el último día del mes
    first_next = dt.date(anio + (mes // 12), (mes % 12) + 1, 1)
    last_day = first_next - dt.timedelta(days=1)
    return last_day >= hoy

def cvv_valido(brand: str, cvv: str) -> bool:
    if not re.fullmatch(r"\d{3,4}", cvv or ""): return False
    if brand == "AMEX": return len(cvv) == 4
    if brand in {"VISA","MASTERCARD"}: return len(cvv) == 3
    # desconocidas: aceptar 3-4
    return len(cvv) in (3,4)

def validar_tarjeta(email, pan, nombre_tarjeta, exp_mes, exp_anio, cvv, monto_str):
    errores = []
    email = (email or "").strip()
    pan = (pan or "").replace(" ", "")
    nombre_tarjeta = (nombre_tarjeta or "").strip()
    cvv = (cvv or "").strip()
    try:
        monto = float((monto_str or "0").replace(",", "."))
        if monto <= 0: raise ValueError
    except ValueError:
        errores.append("Monto inválido.")
        monto = 0.0

    if not email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errores.append("Email inválido.")
    if len(nombre_tarjeta) < 2:
        errores.append("Nombre en tarjeta inválido.")
    if not luhn_ok(pan):
        errores.append("Número de tarjeta inválido.")
    brand = detectar_brand(pan)
    if not cvv_valido(brand, cvv):
        errores.append("CVV inválido.")
    if not vencimiento_valido(int(exp_mes or 0), int(exp_anio or 0)):
        errores.append("Tarjeta vencida.")

    return errores
