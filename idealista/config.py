"""
Configuración centralizada para el bot de Idealista
"""
import os
from pathlib import Path
from typing import Optional

# --- RUTAS ---
APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "pisos.db"
LOG_PATH = DATA_DIR / "logs.log"

# Crear directorios si no existen
DATA_DIR.mkdir(exist_ok=True)

# --- CREDENCIALES API IDEALISTA ---
IDEALISTA_API_KEY = os.getenv('IDEALISTA_API_KEY', '')
IDEALISTA_SECRET = os.getenv('IDEALISTA_SECRET', '')

# --- CREDENCIALES TELEGRAM ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# --- PARÁMETROS DE BÚSQUEDA ---
SEARCH_LATITUDE = float(os.getenv('SEARCH_LAT', 37.1729))
SEARCH_LONGITUDE = float(os.getenv('SEARCH_LNG', -3.5995))
SEARCH_RADIUS = int(os.getenv('SEARCH_RADIUS', 6000))  # metros

SEARCH_BEDROOMS = os.getenv('SEARCH_BEDROOMS', '2,3,4').split(',')
SEARCH_BATHROOMS = os.getenv('SEARCH_BATHROOMS', '1,2,3').split(',')

# --- ESTRATEGIA DE CONSUMO ---
MAX_PAGES_PER_DAY = int(os.getenv('MAX_PAGES_PER_DAY', 5))
ITEMS_PER_PAGE = int(os.getenv('ITEMS_PER_PAGE', 50))

# --- TIEMPOS Y REINTENTOS ---
LOOP_INTERVAL = int(os.getenv('LOOP_INTERVAL', 86400))  # 24 horas en segundos
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 15))  # segundos
PAGE_WAIT_TIME = float(os.getenv('PAGE_WAIT_TIME', 1.5))  # segundos entre páginas
TELEGRAM_TIMEOUT = int(os.getenv('TELEGRAM_TIMEOUT', 10))

# --- REINTENTOS ---
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', 5))  # segundos

# --- LOGGING ---
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', 5242880))  # 5MB
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))

# --- FEATURES ---
ENABLE_TELEGRAM = TELEGRAM_TOKEN and TELEGRAM_CHAT_ID
ENABLE_BACKUPS = os.getenv('ENABLE_BACKUPS', 'true').lower() == 'true'
BACKUP_DIR = DATA_DIR / "backups"

if ENABLE_BACKUPS:
    BACKUP_DIR.mkdir(exist_ok=True)

# --- URLS API ---
IDEALISTA_API_URL = "https://api.idealista.com/3.5/es/search"
IDEALISTA_TOKEN_URL = "https://api.idealista.com/oauth/token"


def validate_config() -> tuple[bool, Optional[str]]:
    """
    Valida que la configuración sea válida.
    Retorna (válido, mensaje_error)
    """
    if not IDEALISTA_API_KEY:
        return False, "IDEALISTA_API_KEY no configurada"
    if not IDEALISTA_SECRET:
        return False, "IDEALISTA_SECRET no configurada"
    if ENABLE_TELEGRAM and not TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_CHAT_ID no configurada"
    return True, None
