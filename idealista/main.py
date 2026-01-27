import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import sqlite3
import requests
import time
import os
import re
import random
import shutil

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
DB_PATH = "/app/data/pisos.db"

# Lista de agentes de usuario para rotar y parecer diferentes personas
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
]

def init_db():
    print("📁 Verificando base de datos...", flush=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pisos
                 (id TEXT PRIMARY KEY, titulo TEXT, precio REAL, link TEXT, fecha DATETIME)''')
    conn.commit()
    conn.close()

def alerta(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=10)
    except Exception as e:
        print(f"❌ Error enviando Telegram: {e}", flush=True)

def guardar_evidencia(driver, motivo):
    """Guarda captura y HTML para depurar"""
    print(f"📸 Guardando evidencia por: {motivo}...", flush=True)
    try:
        driver.save_screenshot(f"/app/data/debug_{motivo}.png")
        with open(f"/app/data/debug_{motivo}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("✅ Evidencia guardada en /app/data/", flush=True)
    except Exception as e:
        print(f"⚠️ No se pudo guardar evidencia: {e}", flush=True)

def escanear():
    print("🏠 --- INICIANDO ESCANEO ---", flush=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    options = uc.ChromeOptions()
    # No usamos headless=new a veces ayuda a pasar desapercibido si usamos xvfb (que ya instalamos)
    # Pero en Docker puro suele ser necesario. Probamos configuración agresiva:
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')
    options.add_argument('--disable-blink-features=AutomationControlled') # Oculta que es un bot
    
    driver = None
    try:
        driver = uc.Chrome(options=options, version_main=None)
        
        # 1. Vamos a Google primero para coger cookies "buenas"
        driver.get("https://www.google.com")
        time.sleep(2)

        # 2. Vamos a Idealista
        url = "https://www.idealista.com/alquiler-viviendas/granada-granada/"
        print(f"🌍 Navegando a: {url}", flush=True)
        driver.get(url)
        
        print("⏳ Esperando carga...", flush=True)
        time.sleep(random.uniform(10, 15))
        
        titulo = driver.title
        print(f"📑 Título de la página: {titulo}", flush=True)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Si nos sale el Captcha de "Just a moment..." o Access Denied
        if "idealista" not in titulo.lower() and "alquiler" not in titulo.lower():
             print("⚠️ ALERTA: Posible bloqueo detectado por el título.", flush=True)
             guardar_evidencia(driver, "bloqueo_titulo")

        items = soup.find_all('article', class_='item')
        print(f"📊 Encontrados {len(items)} anuncios potenciales.", flush=True)

        if len(items) == 0:
            guardar_evidencia(driver, "cero_items")
        
        nuevos = 0
        for item in items:
            try:
                link_tag = item.find('a', class_='item-link')
                price_tag = item.find('span', class_='item-price')
                if not link_tag or not price_tag: continue
                
                link = "https://www.idealista.com" + link_tag['href']
                try:
                    pid = re.search(r'/(\d+)/', link).group(1)
                except:
                    pid = str(hash(link))
                    
                precio = float(price_tag.text.replace('.', '').replace('€', '').strip())
                titulo_piso = link_tag.text.strip()

                c.execute("SELECT precio FROM pisos WHERE id=?", (pid,))
                row = c.fetchone()

                if not row:
                    c.execute("INSERT INTO pisos VALUES (?, ?, ?, ?, datetime('now'))", (pid, titulo_piso, precio, link))
                    alerta(f"🆕 <b>NUEVO: {precio}€</b>\n{titulo_piso}\n<a href='{link}'>Ver</a>")
                    nuevos += 1
                elif precio < row[0]:
                    c.execute("UPDATE pisos SET precio=? WHERE id=?", (precio, pid))
                    alerta(f"📉 <b>BAJADA: {precio}€</b> (Antes {row[0]}€)\n{titulo_piso}\n<a href='{link}'>Ver</a>")
                    nuevos += 1
            except:
                continue
                
        conn.commit()
        print(f"🏁 Escaneo terminado. Enviados: {nuevos}", flush=True)

    except Exception as e:
        print(f"❌ ERROR: {e}", flush=True)
        if driver:
            guardar_evidencia(driver, "error_crash")
        try:
            shutil.rmtree(driver.user_data_dir, ignore_errors=True)
        except:
            pass
    finally:
        if driver:
            driver.quit()
        conn.close()

if __name__ == "__main__":
    init_db()
    while True:
        escanear()
        espera = 14400 + random.randint(0, 600)
        print(f"💤 Durmiendo {espera/3600:.1f} horas...", flush=True)
        time.sleep(espera)