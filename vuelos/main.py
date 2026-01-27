import requests
import datetime
import time
import os

# --- CONFIGURACIÓN ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
CLIENT_ID = os.getenv('AMADEUS_CLIENT_ID')
CLIENT_SECRET = os.getenv('AMADEUS_CLIENT_SECRET')

# Endpoint de pruebas de Amadeus
BASE_URL = "https://test.api.amadeus.com"

def obtener_token():
    """Autenticación OAuth2 para obtener token de acceso"""
    url = f"{BASE_URL}/v1/security/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print(f"❌ Error obteniendo token Amadeus: {e}")
        return None

def buscar_vuelos():
    print("✈️ Iniciando búsqueda con Amadeus...")
    token = obtener_token()
    if not token:
        return

    hoy = datetime.date.today()
    # Buscamos vuelos para dentro de 1 mes (puedes ajustar esto)
    fecha_ida = (hoy + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Amadeus Flight Offers Search
    endpoint = f"{BASE_URL}/v2/shopping/flight-offers"
    headers = {"Authorization": f"Bearer {token}"}
    
    # Búsqueda: De Málaga (AGP) a Londres (LON) como ejemplo
    # Nota: La API gratuita tiene límites de aeropuertos, prueba con grandes hubs
    params = {
        "originLocationCode": "AGP",
        "destinationLocationCode": "LON", # Puedes cambiar a "PAR" (París), "ROM", etc.
        "departureDate": fecha_ida,
        "adults": 1,
        "max": 5, # Máximo 5 resultados
        "currencyCode": "EUR"
    }

    try:
        response = requests.get(endpoint, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error API: {response.text}")
            return

        data = response.json()
        
        if 'data' in data and data['data']:
            mensaje = f"<b>✈️ VUELOS DESDE MÁLAGA ({fecha_ida})</b>\n\n"
            hay_chollos = False

            for vuelo in data['data']:
                precio = vuelo['price']['total']
                aerolinea = vuelo['validatingAirlineCodes'][0]
                
                # Solo avisar si cuesta menos de 100€
                if float(precio) < 100.0:
                    mensaje += f"💰 <b>{precio}€</b> - {aerolinea}\n"
                    hay_chollos = True
            
            if hay_chollos:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                            data={'chat_id': CHAT_ID, 'text': mensaje, 'parse_mode': 'HTML'})
                print("✅ Notificación enviada.")
            else:
                print("Info: Vuelos encontrados pero caros.")
        else:
            print("No se encontraron vuelos disponibles.")

    except Exception as e:
        print(f"❌ Error buscando vuelos: {e}")

if __name__ == "__main__":
    while True:
        buscar_vuelos()
        # Buscar cada 12 horas (43200 segundos) para no gastar la cuota gratis
        print("💤 Durmiendo 12 horas...")
        time.sleep(43200)