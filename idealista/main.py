import requests
import base64
import sqlite3
import time
import os
import sys
from datetime import datetime

# --- CONFIGURACIÓN ---
API_KEY = os.getenv('IDEALISTA_API_KEY')
API_SECRET = os.getenv('IDEALISTA_SECRET')
TOKEN_TELEGRAM = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
DB_PATH = "/app/data/pisos.db"

# Ubicación y Radio
LAT = 37.1729
LNG = -3.5995
DISTANCIA = 6000  # 6 km a la redonda

# --- ESTRATEGIA DE CONSUMO DE API ---
# Si maxItems=50, cada página gasta 1 petición.
# Tienes 100 al mes. 
# Recomendación: MAX_PAGINAS_DIA = 3 (150 pisos/día) o desactivar límite si es ejecución única.
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
    headers = {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        r = requests.post(url, headers=headers, data={"grant_type": "client_credentials", "scope": "read"}, timeout=10)
        if r.status_code == 200:
            return r.json().get('access_token')
        print(f"❌ Error Token: {r.text}", flush=True)
        return None
    except Exception as e:
        print(f"❌ Error Conexión: {e}", flush=True)
        return None

def buscar_pisos():
    print("🚀 --- INICIANDO BÚSQUEDA MASIVA ---", flush=True) 
    token = obtener_token()
    if not token: return

    url = "https://api.idealista.com/3.5/es/search"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Bucle de paginación
    num_pagina = 1
    total_pisos_procesados = 0
    
    while num_pagina <= MAX_PAGINAS_DIA:
        print(f"📄 Solicitando página {num_pagina}...", flush=True)
        
        # PARÁMETROS SEGÚN TU DOCUMENTACIÓN
        params = {
            "country": "es",
            "operation": "rent",
            "propertyType": "homes",
            "center": f"{LAT},{LNG}",
            "distance": DISTANCIA,
            "sort": "date",
            "maxItems": 50,         # Máximo permitido por la API 
            "numPage": num_pagina,  # Paginación [cite: 22]
            
            # FILTROS PERSONALIZADOS 
            # Habitaciones: "2,3,4" incluye 2, 3 y "4 o más". Esto maximiza resultados.
            "bedrooms": "2,3,4",
            
            # Baños: "1,2,3" incluye 1, 2 y "3 o más" (Excluye 0).
            "bathrooms": "1,2,3",
            
            # Opcional: Usar 'sinceDate'='W' (semana) o 'M' (mes) si quieres limitar antigüedad
            # "sinceDate": "M" 
        }

        try:
            r = requests.post(url, headers=headers, data=params, timeout=10)
            if r.status_code != 200:
                print(f"❌ Error API: {r.text}", flush=True)
                break

            data = r.json()
            pisos = data.get('elementList', [])
            total_disponible = data.get('total', 0)
            total_paginas = data.get('totalPages', 1) # [cite: 111]
            
            print(f"📊 Página {num_pagina}/{total_paginas}. Recibidos: {len(pisos)} pisos (Total mercado: {total_disponible})", flush=True)
            
            if not pisos:
                print("🏁 No hay más pisos en esta página.", flush=True)
                break

            # Procesar pisos
            procesar_lote(pisos)
            total_pisos_procesados += len(pisos)

            # Control de paginación
            if num_pagina >= total_paginas:
                print("✅ Se han descargado TODAS las páginas disponibles.", flush=True)
                break
            
            num_pagina += 1
            time.sleep(2) # Pequeña pausa de cortesía

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
            planta = p.get('floor', 'Bajo/Sin datos')
            link = p.get('url')
            
            # Verificar existencia
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
        
        except Exception as e:
            continue

    conn.commit()
    conn.close()
    if nuevos > 0: print(f"✨ {nuevos} pisos nuevos guardados en este lote.", flush=True)

if __name__ == "__main__":
    init_db()
    while True:
        print(f"🔍 DEBUG CLAVES: Key='{API_KEY[:5]}...' | Secret='{API_SECRET[:5]}...'", flush=True)
        buscar_pisos()
        # Cada 24 horas para no gastar paginación excesiva
        print("💤 Durmiendo 24 horas...", flush=True)
        time.sleep(86400)