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

def registrar_apertura_segura(
    remitente: str,
    destinatario: str,
    enviado: datetime,
    abierto: datetime,
    demora: int,
    ip: str,
    user_agent: str,
    condiciones: dict[str, bool]
) -> None:
    try:
        etiqueta = "Válida" if not any(condiciones.values()) else "Sospechosa: " + ", ".join([k for k, v in condiciones.items() if v])
        user_agent_marcado = f"{user_agent} | {etiqueta}"

        query = """
        INSERT INTO aperturas (remitente, destinatario, enviado, abierto, demora_segundos, ip_address, user_agent)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (remitente, destinatario, enviado, abierto, demora, ip, user_agent_marcado))
        logging.info(f"Apertura registrada ({etiqueta}): {remitente} -> {destinatario} en {demora}s")

    except Exception:
        logging.exception("Error al registrar apertura segura")

def es_apertura_confiable(user_agent: str) -> bool:
    condiciones = es_apertura_sospechosa("x", "y", 10, user_agent)
    return not (condiciones["ua_invalido"] or condiciones["ua_blacklist"] or condiciones["ua_vacio"])


def es_apertura_sospechosa(remitente: str, destinatario: str, demora: int, user_agent: str) -> dict[str, bool]:
    ua = user_agent.lower() if user_agent else ""

    # Blacklist: bots, antivirus, proxys, librerías
    blacklist = [
        "bot", "scanner", "proxy", "fetch", "curl", "python", "requests",
        "defender", "antivirus", "googleimageproxy", "ggpht",
        "msoffice", "ms-office", "word", "libwww"
    ]

    condiciones = {
        "mismo_remitente": remitente.lower() == destinatario.lower(),
        "gmail_proxy": "googleimageproxy" in ua or "ggpht" in ua,
        "ua_invalido": not any(w in ua for w in [
            "chrome", "safari", "firefox", "edge", "android", "iphone", "ios", "applewebkit", "mozilla"
        ]),
        "ua_blacklist": any(b in ua for b in blacklist),
        "demora_sospechosa": demora < 2,  # Puedes ajustar este umbral según comportamiento real
        "navegador_viejo": "chrome/42" in ua or "edge/12" in ua,
        "ua_vacio": not user_agent
    }

    return condiciones

@app.route("/pixel")
def pixel():
    remitente = request.args.get("from")
    destinatario = request.args.get("to")
    enviado_str = request.args.get("sent")

    response = send_from_directory(PIXEL_PATH, PIXEL_NAME, mimetype="image/png")
    response.headers.update({
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

    if not remitente or not destinatario or not enviado_str:
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

    condiciones = {
        "mismo_remitente": remitente.lower() == destinatario.lower(),
        "gmail_proxy": "googleimageproxy" in ua or "ggpht" in ua,
        "ua_invalido": not es_apertura_confiable(ua),
        "demora_sospechosa": demora < 2
    }

    registrar_apertura_segura(
        remitente,
        destinatario,
        enviado,
        abierto,
        demora,
        ip,
        ua,
        condiciones
    )

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
            agentes_reales = [ua for ua in all_agents if es_apertura_confiable(ua)]
            count = len(agentes_reales)
            dispositivos = clasificar_dispositivos(agentes_reales)
            enviado_str = enviado.replace(tzinfo=UTC).astimezone(santiago).strftime("%d/%m/%Y %H:%M")
            abierto_str = abierto.replace(tzinfo=UTC).astimezone(santiago).strftime("%d/%m/%Y %H:%M")

            html += f"<tr><td>{remitente}</td><td>{destinatario}</td><td>{enviado_str}</td><td>{abierto_str}</td><td>{count}</td><td>{dispositivos}</td></tr>"

        html += "</table>"
        return html

    except Exception as e:
        return f"<p>Error al consultar la tabla: {str(e)}</p>"

@app.route("/metricas")
def metricas():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT remitente, COUNT(DISTINCT destinatario), COUNT(*) 
            FROM aperturas
            GROUP BY remitente
            ORDER BY COUNT(*) DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        html = "<h2>Métricas por Remitente</h2><table border='1' cellpadding='6'>"
        html += "<tr><th>Remitente</th><th>Destinatarios únicos</th><th>Total aperturas</th></tr>"

        for remitente, destinatarios, total in rows:
            html += f"<tr><td>{remitente}</td><td>{destinatarios}</td><td>{total}</td></tr>"

        html += "</table>"
        return html
    except Exception as e:
        logging.exception("Error al obtener métricas")
        return f"<p>Error al obtener métricas: {str(e)}</p>"

@app.route("/")
def index():
    return ver_aperturas()

if __name__ == "__main__":
    crear_tabla_aperturas()
    port = int(os.environ.get("PORT", 5000))
    print(">>> Flask app iniciado")
    app.run(host="0.0.0.0", port=port)