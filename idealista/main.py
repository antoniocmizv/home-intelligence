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

def init_db():
    print("📁 Verificando base de datos...", flush=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pisos
                 (id TEXT PRIMARY KEY, titulo TEXT, precio REAL, link TEXT, fecha DATETIME)''')
    conn.commit()
    conn.close()
    print("✅ Base de datos lista.", flush=True)

def alerta(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=10)
    except Exception as e:
        print(f"❌ Error enviando Telegram: {e}", flush=True)

def buscar_ruta_chrome():
    # Intenta encontrar dónde está instalado Chrome en el Docker
    rutas = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/bin/google-chrome"]
    for r in rutas:
        if os.path.exists(r):
            return r
    return None

def escanear():
    print("🏠 --- INICIANDO ESCANEO ---", flush=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # CONFIGURACIÓN BLINDADA PARA DOCKER
    print("⚙️ Configurando Chrome...", flush=True)
    options = uc.ChromeOptions()
    options.add_argument('--headless=new') # Modo sin cabeza moderno
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--disable-dev-shm-usage') # Vital para Docker
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        binario_chrome = buscar_ruta_chrome()
        if binario_chrome:
            options.binary_location = binario_chrome
            
        print(f"🚀 Lanzando navegador (Binario: {binario_chrome})...", flush=True)
        # version_main=None fuerza a que UC detecte la versión automáticamente
        driver = uc.Chrome(options=options, version_main=None) 
        print("✅ Navegador arrancado correctamente.", flush=True)
        
        url = "https://www.idealista.com/alquiler-viviendas/granada-granada/"
        print(f"🌍 Navegando a: {url}", flush=True)
        
        driver.get(url)
        print("⏳ Esperando carga de página...", flush=True)
        time.sleep(random.uniform(8, 12))
        
        print("🔍 Analizando HTML...", flush=True)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.find_all('article', class_='item')
        
        print(f"📊 Encontrados {len(items)} anuncios potenciales.", flush=True)

        nuevos = 0
        for item in items:
            try:
                link_tag = item.find('a', class_='item-link')
                price_tag = item.find('span', class_='item-price')
                if not link_tag or not price_tag: continue
                
                link = "https://www.idealista.com" + link_tag['href']
                # Intentar sacar ID del link o generar uno hash
                try:
                    pid = re.search(r'/(\d+)/', link).group(1)
                except:
                    pid = str(hash(link))
                    
                precio = float(price_tag.text.replace('.', '').replace('€', '').strip())
                titulo = link_tag.text.strip()

                c.execute("SELECT precio FROM pisos WHERE id=?", (pid,))
                row = c.fetchone()

                if not row:
                    c.execute("INSERT INTO pisos VALUES (?, ?, ?, ?, datetime('now'))", (pid, titulo, precio, link))
                    alerta(f"🆕 <b>NUEVO: {precio}€</b>\n{titulo}\n<a href='{link}'>Ver</a>")
                    nuevos += 1
                elif precio < row[0]:
                    c.execute("UPDATE pisos SET precio=? WHERE id=?", (precio, pid))
                    alerta(f"📉 <b>BAJADA: {precio}€</b> (Antes {row[0]}€)\n{titulo}\n<a href='{link}'>Ver</a>")
                    nuevos += 1
            except Exception as e:
                print(f"⚠️ Error procesando un anuncio: {e}", flush=True)
                continue
                
        conn.commit()
        print(f"🏁 Escaneo terminado. Novedades enviadas: {nuevos}", flush=True)

    except Exception as e:
        print(f"❌ ERROR FATAL EN CHROME: {e}", flush=True)
        # Si falla, borramos la carpeta de sesión por si se corrompió
        try:
            shutil.rmtree(driver.user_data_dir, ignore_errors=True)
        except:
            pass
    finally:
        if driver:
            print("🛑 Cerrando navegador...", flush=True)
            driver.quit()
        conn.close()

if __name__ == "__main__":
    init_db()
    while True:
        escanear()
        espera = 14400 + random.randint(0, 600)
        print(f"💤 Durmiendo {espera/3600:.1f} horas...", flush=True)
        time.sleep(espera)