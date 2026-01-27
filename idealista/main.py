import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import sqlite3
import requests
import time
import os
import re
import random

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
DB_PATH = "/app/data/pisos.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pisos
                 (id TEXT PRIMARY KEY, titulo TEXT, precio REAL, link TEXT, fecha DATETIME)''')
    conn.commit()
    conn.close()

def alerta(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                  data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'})

def escanear():
    print("🏠 Escaneando Idealista...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    
    driver = uc.Chrome(options=options)
    try:
        driver.get("https://www.idealista.com/alquiler-viviendas/granada-granada/")
        time.sleep(random.uniform(5, 10))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.find_all('article', class_='item')

        for item in items:
            try:
                link_tag = item.find('a', class_='item-link')
                price_tag = item.find('span', class_='item-price')
                if not link_tag or not price_tag: continue
                
                link = "https://www.idealista.com" + link_tag['href']
                pid = re.search(r'/(\d+)/', link).group(1)
                precio = float(price_tag.text.replace('.', '').replace('€', '').strip())
                titulo = link_tag.text.strip()

                c.execute("SELECT precio FROM pisos WHERE id=?", (pid,))
                row = c.fetchone()

                if not row:
                    c.execute("INSERT INTO pisos VALUES (?, ?, ?, ?, datetime('now'))", (pid, titulo, precio, link))
                    alerta(f"🆕 <b>NUEVO: {precio}€</b>\n{titulo}\n<a href='{link}'>Ver</a>")
                elif precio < row[0]:
                    c.execute("UPDATE pisos SET precio=? WHERE id=?", (precio, pid))
                    alerta(f"📉 <b>BAJADA: {precio}€</b> (Antes {row[0]}€)\n{titulo}\n<a href='{link}'>Ver</a>")
            except:
                continue
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        driver.quit()
        conn.close()

if __name__ == "__main__":
    init_db()
    while True:
        escanear()
        time.sleep(14400 + random.randint(0, 600)) # 4 horas aprox