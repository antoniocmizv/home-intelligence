import requests
import base64
import sqlite3
import time
import os
from datetime import datetime

# --- CONFIGURACIÓN ---
API_KEY = os.getenv('IDEALISTA_API_KEY')
API_SECRET = os.getenv('IDEALISTA_SECRET')
TOKEN_TELEGRAM = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
DB_PATH = "/app/data/pisos.db"

# Ubicación y Radio (Granada)
LAT = 37.1729
LNG = -3.5995
DISTANCIA = 6000  # 6 km a la redonda

# Límite de seguridad
MAX_PAGINAS_DIA = 5 

def init_db():
    print("📁 Inicializando base de datos...", flush=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pisos (
        id TEXT PRIMARY KEY,
        titulo TEXT,
        precio REAL,
        precio_m2 REAL,
        metros INTEGER,
        habitaciones INTEGER,
        planta TEXT,
        exterior BOOLEAN,
        estado TEXT,
        link TEXT,
        fecha_registro DATETIME,
        fecha_actualizacion DATETIME
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS historial_precios (
        id_piso TEXT, precio REAL, fecha DATETIME
    )''')
    conn.commit()
    conn.close()

def enviar_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", 
                      data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=10)
    except Exception as e:
        print(f"❌ Error Telegram: {e}", flush=True)

def obtener_token():
    url = "https://api.idealista.com/oauth/token"
    credenciales = f"{API_KEY}:{API_SECRET}"
    auth_b64 = base64.b64encode(credenciales.encode()).decode()
    
    # OAuth usa formato formulario siempre
    headers = {
        "Authorization": f"Basic {auth_b64}", 
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        r = requests.post(url, headers=headers, data={"grant_type": "client_credentials", "scope": "read"}, timeout=10)
        if r.status_code == 200:
            return r.json().get('access_token')
        print(f"❌ Error Token ({r.status_code}): {r.text}", flush=True)
        return None
    except Exception as e:
        print(f"❌ Error Conexión Auth: {e}", flush=True)
        return None

def buscar_pisos():
    print("🚀 --- INICIANDO BÚSQUEDA ---", flush=True)
    token = obtener_token()
    if not token: return

    # OJO: La URL lleva el país en la ruta
    url = "https://api.idealista.com/3.5/es/search"
    
    # CORRECCIÓN IMPORTANTE: Quitamos 'Content-Type: application/json'
    # Requests pondrá automáticamente 'application/x-www-form-urlencoded'
    headers = {"Authorization": f"Bearer {token}"}
    
    num_pagina = 1
    total_pisos_procesados = 0
    
    while num_pagina <= MAX_PAGINAS_DIA:
        print(f"📄 Solicitando página {num_pagina}...", flush=True)
        
        params = {
            "country": "es",            # Obligatorio [cite: 21]
            "operation": "rent",        # Obligatorio [cite: 21]
            "propertyType": "homes",    # Obligatorio [cite: 21]
            "center": f"{LAT},{LNG}",   # Coordenadas [cite: 21]
            "distance": DISTANCIA,      # Radio en metros [cite: 21]
            "order": "publicationDate", # Ordenar por fecha (más nuevos primero) 
            "sort": "desc",             # Descendente 
            "maxItems": 50,             # Máximo permitido [cite: 21]
            "numPage": num_pagina,      # Paginación 
            
            # FILTROS
            "bedrooms": "2,3,4",        # 2, 3 y 4+ habitaciones [cite: 73]
            "bathrooms": "1,2,3",       # 1, 2 y 3+ baños [cite: 73]
            "hasMultimedia": "true"     # Solo pisos con fotos 
        }

        try:
            # data=params envía formato formulario (Correcto)
            r = requests.post(url, headers=headers, data=params, timeout=10)
            
            if r.status_code != 200:
                print(f"❌ Error API ({r.status_code}): {r.text}", flush=True)
                break

            data = r.json()
            pisos = data.get('elementList', [])
            total_disponible = data.get('total', 0)
            total_paginas = data.get('totalPages', 1)
            
            print(f"📊 Recibidos: {len(pisos)} pisos (Total mercado: {total_disponible})", flush=True)
            
            if not pisos:
                print("🏁 No hay más pisos.", flush=True)
                break

            procesar_lote(pisos)
            total_pisos_procesados += len(pisos)

            if num_pagina >= total_paginas:
                print("✅ Fin de resultados disponibles.", flush=True)
                break
            
            num_pagina += 1
            time.sleep(1.5)

        except Exception as e:
            print(f"❌ Error en bucle: {e}", flush=True)
            break
    
    print(f"💤 Fin del ciclo. Total procesados hoy: {total_pisos_procesados}", flush=True)

def procesar_lote(pisos):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    nuevos = 0
    
    for p in pisos:
        try:
            pid = str(p.get('propertyCode'))
            titulo = p.get('suggestedTexts', {}).get('title', 'Piso en Granada')
            precio = p.get('price')
            metros = p.get('size')
            habitaciones = p.get('rooms')
            planta = p.get('floor', 'Bajo')
            link = p.get('url')
            
            c.execute("SELECT precio FROM pisos WHERE id=?", (pid,))
            row = c.fetchone()
            
            if not row:
                c.execute("""INSERT INTO pisos 
                             (id, titulo, precio, metros, habitaciones, planta, link, fecha_registro, fecha_actualizacion) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                          (pid, titulo, precio, metros, habitaciones, planta, link))
                c.execute("INSERT INTO historial_precios VALUES (?, ?, datetime('now'))", (pid, precio))
                
                msg = (f"🆕 <b>NOVEDAD ({precio}€)</b>\n"
                       f"🏠 {titulo}\n"
                       f"🛏️ {habitaciones} hab | 📏 {metros}m²\n"
                       f"<a href='{link}'>🔗 Ver en Idealista</a>")
                enviar_telegram(msg)
                nuevos += 1
                
            elif precio < row[0]:
                diff = row[0] - precio
                c.execute("UPDATE pisos SET precio=?, fecha_actualizacion=datetime('now') WHERE id=?", (precio, pid))
                msg = (f"📉 <b>BAJADA (-{diff}€)</b>\nAntes: {row[0]}€ ➡️ {precio}€\n<a href='{link}'>🔗 Ver piso</a>")
                enviar_telegram(msg)
        
        except Exception:
            continue

    conn.commit()
    conn.close()
    if nuevos > 0: print(f"✨ {nuevos} pisos nuevos guardados.", flush=True)

if __name__ == "__main__":
    init_db()
    while True:
        buscar_pisos()
        print("💤 Durmiendo 24 horas...", flush=True)
        time.sleep(86400)