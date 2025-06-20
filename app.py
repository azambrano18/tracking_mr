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
    ua = request.headers.get("User-Agent", "Desconocido").lower()

    # Lógica final de exclusión
    if remitente.lower() == destinatario.lower():
        logging.info(f"[IGNORADO] Remitente = destinatario: {remitente}")
    elif "googleimageproxy" in ua or "ggpht" in ua:
        logging.info(f"[IGNORADO] Proxy de Gmail: UA = {ua}")
    elif not es_apertura_real(ua):
        logging.info(f"[IGNORADO] User-Agent no confiable: {ua}")
    elif demora < 5:
        logging.info(f"[IGNORADO] Demora sospechosa (<5s): {demora}s desde el envío")
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
    if not user_agent:
        return False
    ua = user_agent.lower()

    # Agentes conocidos de bots, antivirus, proxys o precargas automáticas
    blacklist = [
        "bot", "scanner", "proxy", "fetch", "curl", "python", "requests",
        "defender", "antivirus", "googleimageproxy", "ggpht",
        "msoffice", "ms-office", "word", "libwww"
    ]

    # Firmas específicas de navegadores sospechosos usados por proxies
    if "chrome/42" in ua or "edge/12" in ua:
        return False

    if any(b in ua for b in blacklist):
        return False

    # Agentes típicos de navegadores reales
    whitelist = ["chrome", "safari", "firefox", "edge", "android", "iphone", "ios", "applewebkit"]
    return any(w in ua for w in whitelist)

@app.route("/")
def index():
    return ver_aperturas()

if __name__ == "__main__":
    crear_tabla_aperturas()
    port = int(os.environ.get("PORT", 5000))
    print(">>> Flask app iniciado")
    app.run(host="0.0.0.0", port=port)