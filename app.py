import os
import logging
import hashlib
import requests
import psycopg2
import dns.resolver
from datetime import datetime
from pytz import timezone, UTC
from flask import Flask, request, redirect

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está definido como variable de entorno")

# Extrae navegador y sistema operativo del user-agent
def extraer_navegador_so(user_agent: str) -> tuple[str, str]:
    ua = user_agent.lower()
    navegador = "Desconocido"
    so = "Desconocido"

    if "chrome" in ua and "edg" not in ua:
        navegador = "Chrome"
    elif "firefox" in ua:
        navegador = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        navegador = "Safari"
    elif "edg" in ua:
        navegador = "Edge"
    elif "opera" in ua:
        navegador = "Opera"

    if "windows" in ua:
        so = "Windows"
    elif "android" in ua:
        so = "Android"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        so = "iOS"
    elif "macintosh" in ua or "mac os" in ua:
        so = "Mac"
    elif "linux" in ua:
        so = "Linux"

    return navegador, so

# Consulta externa para obtener país desde IP
def obtener_pais_desde_ip(ip: str) -> str:
    try:
        r = requests.get(f"https://ipapi.co/{ip}/country_name/", timeout=3)
        if r.status_code == 200:
            return r.text.strip()
    except:
        pass
    return "Desconocido"

# Formatea fechas en zona Santiago
def formatear_fecha_santiago(fecha_utc: datetime) -> str:
    tz_scl = timezone("America/Santiago")
    fecha_local = fecha_utc.replace(tzinfo=UTC).astimezone(tz_scl)
    return fecha_local.strftime("%d/%m/%Y %H:%M")

# Genera token SHA256
def generar_token(remitente: str, destinatario: str, url: str, secreto: str = "clave-secreta") -> str:
    base = f"{remitente}-{destinatario}-{url}-{secreto}"
    return hashlib.sha256(base.encode()).hexdigest()

@app.route("/click")
def redirigir_click():
    remitente = request.args.get("from")
    destinatario = request.args.get("to")
    url_destino = request.args.get("url")
    token_recibido = request.args.get("token")

    if not all([remitente, destinatario, url_destino, token_recibido]):
        return "<h3>Faltan parámetros requeridos</h3>", 400

    # Validar token
    token_esperado = generar_token(remitente, destinatario, url_destino)
    if token_recibido != token_esperado:
        return "<h3>Token inválido</h3>", 403

    # Datos del clic
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0").split(",")[0].strip()
    ua = request.headers.get("User-Agent", "Desconocido")
    navegador, so = extraer_navegador_so(ua)
    pais = obtener_pais_desde_ip(ip)
    tz_scl = timezone("America/Santiago")
    click_apertura = datetime.now(tz_scl)

    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                # Buscar si ya existe un envío con ese remitente + destinatario + token
                cur.execute("""
                    SELECT id FROM clicks
                    WHERE remitente = %s AND destinatario = %s AND token = %s
                """, (remitente, destinatario, token_recibido))
                existente = cur.fetchone()

                if existente:
                    # Actualizar la fila existente con datos del clic
                    cur.execute("""
                        UPDATE clicks SET
                            click_apertura = %s,
                            url_destino = %s,
                            navegador = %s,
                            so = %s,
                            pais = %s,
                            ip_public = %s,
                            user_agent = %s
                        WHERE id = %s
                    """, (
                        click_apertura, url_destino, navegador, so,
                        pais, ip, ua, existente[0]
                    ))
                    logging.info(f"Click actualizado: {remitente} → {destinatario} ({click_apertura})")
                else:
                    # Insertar nuevo registro como fallback
                    cur.execute("""
                        INSERT INTO clicks (
                            remitente, fecha_envio, tipo_envio, destinatario,
                            dominio_destinatario, servidor_correo, click_apertura,
                            url_destino, navegador, so, pais,
                            ip_public, token, user_agent
                        ) VALUES (%s, NULL, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        remitente, destinatario,
                        destinatario.split("@")[-1].lower(),
                        "desconocido",  # no se puede resolver desde clic
                        click_apertura,
                        url_destino, navegador, so, pais,
                        ip, token_recibido, ua
                    ))
                    logging.warning(f"Click insertado sin envío previo: {remitente} → {destinatario}")

    except Exception:
        logging.exception("Error al registrar clic")

    return redirect(url_destino)

def obtener_servidor_correo(dominio: str) -> str:
    try:
        respuestas = dns.resolver.resolve(dominio, 'MX')
        servidor = sorted(respuestas, key=lambda r: r.preference)[0].exchange.to_text()
        return servidor.lower()
    except Exception:
        return "desconocido"

# Visualiza los clics registrados
@app.route("/clics")
def ver_clics():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT remitente, destinatario, click_apertura,
                           ip_public, navegador, so, pais, url_destino
                    FROM clicks
                    ORDER BY click_apertura DESC
                    LIMIT 100
                """)
                rows = cur.fetchall()

        html = "<h2>Últimos clics registrados</h2><table border='1' cellpadding='6'>"
        html += "<tr><th>Remitente</th><th>Destinatario</th><th>Fecha clic</th>"
        html += "<th>IP</th><th>Navegador</th><th>SO</th><th>País</th><th>Destino</th></tr>"

        for row in rows:
            remitente, destinatario, click_apertura, ip_public, navegador, so, pais, url = row
            html += f"<tr><td>{remitente}</td><td>{destinatario}</td>"
            html += f"<td>{formatear_fecha_santiago(click_apertura)}</td>"
            html += f"<td>{ip_public}</td><td>{navegador}</td><td>{so}</td><td>{pais}</td><td>{url}</td></tr>"

        html += "</table>"
        return html

    except Exception as e:
        logging.exception("Error al consultar clics")
        return f"<p>Error al consultar clics: {str(e)}</p>"

# Ruta principal
@app.route("/")
def index():
    return "<h2>Tracking por clic activo</h2><p>Visita <code>/clics</code> para ver los registros recientes.</p>"

# Health check
@app.route("/status")
def status():
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}, 200
    except:
        return {"status": "error"}, 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(">>> Flask app iniciado")
    app.run(host="0.0.0.0", port=port)