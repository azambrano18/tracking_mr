import psycopg2
import logging
import os
from pytz import timezone, UTC
from flask import Flask, request, send_from_directory
from datetime import datetime
from tabla import crear_tabla_aperturas

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)

PIXEL_PATH = "static"
PIXEL_NAME = "pixel.png"

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está definido como variable de entorno")

# app.py (reemplazo parcial)
def registrar_apertura(remitente, destinatario, enviado, abierto, demora, ip, ua):
    query = """
    INSERT INTO aperturas (remitente, destinatario, enviado, abierto, demora_segundos, ip_address, user_agent)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (remitente, destinatario, enviado, abierto, demora, ip, ua))
        logging.info(f"Apertura registrada: {remitente} -> {destinatario} ({demora} seg.)")
    except Exception:
        logging.exception("Error al registrar apertura")

@app.route("/pixel")
def pixel():
    remitente = request.args.get("from")
    destinatario = request.args.get("to")
    enviado_str = request.args.get("sent")

    response = send_from_directory(PIXEL_PATH, PIXEL_NAME, mimetype="image/png")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    if not all([remitente, destinatario, enviado_str]):
        logging.warning("Parámetros faltantes en /pixel")
        return response

    try:
        enviado = datetime.fromisoformat(enviado_str)
    except ValueError:
        enviado = datetime.utcnow()

    abierto = datetime.utcnow()
    demora = int((abierto - enviado).total_seconds())
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0").split(",")[0].strip()
    ua = request.headers.get("User-Agent", "Desconocido")

    # Evitar registrar si:
    # 1. remitente == destinatario (autoprueba)
    # 2. user-agent de proxy de Gmail
    # 3. user-agent detectado como bot
    if remitente.lower() == destinatario.lower():
        logging.info(f"Apertura ignorada: remitente = destinatario -> {remitente}")
    elif "googleimageproxy" in ua.lower() or "ggpht" in ua.lower():
        logging.info(f"Apertura ignorada por Google Proxy: UA = {ua}")
    elif not es_apertura_real(ua):
        logging.info(f"Apertura descartada por user_agent sospechoso: {ua}")
    else:
        registrar_apertura(remitente, destinatario, enviado, abierto, demora, ip, ua)

    return response

def clasificar_dispositivos(agents: list[str]) -> str:
    tipos = set()
    for ua in agents:
        ua = ua.lower()
        if "iphone" in ua or "ipad" in ua or "ios" in ua:
            tipos.add("iOS")
        elif "android" in ua:
            tipos.add("Android")
        elif "windows" in ua:
            tipos.add("Windows")
        elif "macintosh" in ua or "mac os" in ua:
            tipos.add("Mac")
        elif "linux" in ua:
            tipos.add("Linux")
        elif "mobile" in ua:
            tipos.add("Móvil")
        else:
            tipos.add("Otro")
    return ", ".join(tipos)

def ver_aperturas():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                remitente,
                destinatario,
                MIN(enviado) AS primer_enviado,
                MIN(abierto) AS primer_abierto,
                ARRAY_AGG(user_agent) AS all_agents
            FROM aperturas
            GROUP BY remitente, destinatario
            ORDER BY primer_abierto DESC
            LIMIT 100
        """)
        filas = cur.fetchall()
        cur.close()
        conn.close()

        santiago = timezone("America/Santiago")

        html = "<h2>Tasa de Apertura</h2><table border='1' cellpadding='6'><tr>"
        html += "<th>Remitente</th><th>Destinatario</th><th>Enviado</th><th>Abierto</th><th>Aperturas reales</th><th>Dispositivos</th></tr>"

        for remitente, destinatario, enviado, abierto, all_agents in filas:
            agentes_reales = [ua for ua in all_agents if es_apertura_real(ua)]
            count = len(agentes_reales)
            dispositivos = clasificar_dispositivos(agentes_reales)
            enviado_str = enviado.replace(tzinfo=UTC).astimezone(santiago).strftime("%d/%m/%Y %H:%M")
            abierto_str = abierto.replace(tzinfo=UTC).astimezone(santiago).strftime("%d/%m/%Y %H:%M")

            html += f"<tr><td>{remitente}</td><td>{destinatario}</td><td>{enviado_str}</td><td>{abierto_str}</td><td>{count}</td><td>{dispositivos}</td></tr>"

        html += "</table>"
        return html

    except Exception as e:
        return f"<p>Error al consultar la tabla: {str(e)}</p>"

def es_apertura_real(user_agent: str) -> bool:
    ua = user_agent.lower()
    bots = [
        "googleimageproxy", "outlook", "fetch", "bot", "scanner", "proxy",
        "curl", "python", "requests", "prefetch", "defender", "antivirus"
        "ms-office", "office", "msoffice", "libwww", "word"
    ]
    return not any(b in ua for b in bots)

@app.route("/")
def index():
    return ver_aperturas()

if __name__ == "__main__":
    crear_tabla_aperturas()
    port = int(os.environ.get("PORT", 5000))
    print(">>> Flask app iniciado")
    app.run(host="0.0.0.0", port=port)