"""
Bot de rastreo de pisos en Idealista - CON CONTROL DE QUOTA API
Desplegado en Docker + SQLite + Metabase
⭐ CRÍTICO: API limitado a 100 peticiones/mes
"""
import requests
import base64
import sqlite3
import time
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from functools import wraps

import config
from utils import setup_logging, log_event

# Configurar logging
logger = setup_logging(
    config.LOG_PATH,
    level=config.LOG_LEVEL,
    max_bytes=config.LOG_MAX_BYTES,
    backup_count=config.LOG_BACKUP_COUNT
)


def track_api_request(exitoso: bool = True, tipo: str = 'search'):
    """
    ⭐ CRÍTICO: Registra una petición API en la BD para tracking de quota
    
    Args:
        exitoso: Si la petición fue exitosa
        tipo: Tipo de petición (search, token, etc)
    """
    try:
        mes_ano = datetime.now().strftime("%Y-%m")
        
        conn = sqlite3.connect(str(config.DB_PATH))
        c = conn.cursor()
        
        # Registrar petición
        c.execute("""INSERT INTO api_requests (endpoint, tipo, exitoso, mes_ano)
                     VALUES (?, ?, ?, ?)""",
                  ('https://api.idealista.com', tipo, exitoso, mes_ano))
        
        # Actualizar quota
        c.execute("SELECT COUNT(*) FROM api_requests WHERE mes_ano=? AND exitoso=1", 
                 (mes_ano,))
        total_usado = c.fetchone()[0]
        
        c.execute("""INSERT OR REPLACE INTO api_quota 
                     (mes_ano, usado, fecha_inicio, fecha_fin)
                     VALUES (?, ?, datetime('now'), datetime('now', '+1 month'))""",
                  (mes_ano, total_usado))
        
        conn.commit()
        conn.close()
        
        log_event(logger, 'API_REQUEST_TRACKED', {
            'mes': mes_ano,
            'total_usado': total_usado,
            'limite': config.MONTHLY_REQUEST_LIMIT,
            'porcentaje': round((total_usado / config.MONTHLY_REQUEST_LIMIT) * 100, 1)
        })
        
    except Exception as e:
        logger.warning(f"Error registrando petición API: {e}")


def check_api_quota() -> Tuple[bool, int, int]:
    """
    ⭐ CRÍTICO: Verifica la quota disponible de API (100 peticiones/mes)
    
    Returns:
        (puede_continuar, usado, limite)
    """
    try:
        mes_ano = datetime.now().strftime("%Y-%m")
        
        conn = sqlite3.connect(str(config.DB_PATH))
        c = conn.cursor()
        
        c.execute("SELECT usado FROM api_quota WHERE mes_ano=?", (mes_ano,))
        row = c.fetchone()
        usado = row[0] if row else 0
        
        conn.close()
        
        puede_continuar = usado < config.MONTHLY_REQUEST_LIMIT
        
        # Logging de estado
        porcentaje = (usado / config.MONTHLY_REQUEST_LIMIT) * 100
        if porcentaje >= 100:
            logger.critical(f"❌ QUOTA AGOTADA: {usado}/{config.MONTHLY_REQUEST_LIMIT} peticiones")
            if config.PAUSE_AT_QUOTA:
                logger.warning("⏸️  Búsquedas pausadas hasta fin de mes")
        elif porcentaje >= (config.QUOTA_WARNING_THRESHOLD * 100):
            logger.warning(f"⚠️  QUOTA AL {porcentaje:.1f}%: {usado}/{config.MONTHLY_REQUEST_LIMIT} peticiones")
        else:
            logger.debug(f"✅ Quota OK: {usado}/{config.MONTHLY_REQUEST_LIMIT} ({porcentaje:.1f}%)")
        
        return puede_continuar, usado, config.MONTHLY_REQUEST_LIMIT
        
    except Exception as e:
        logger.error(f"Error verificando quota: {e}")
        return True, 0, config.MONTHLY_REQUEST_LIMIT


def should_search_now() -> bool:
    """
    ⭐ CRÍTICO: Determina si se debe hacer búsqueda ahora considerando:
    1. Quota disponible
    2. Última búsqueda (espaciadas para economizar quota)
    
    Returns:
        True si se debe buscar, False si no
    """
    puede, usado, limite = check_api_quota()
    
    if not puede:
        logger.warning(f"Búsqueda saltada: quota agotada ({usado}/{limite})")
        return False
    
    # Verificar si es tiempo de buscar (basado en SEARCH_INTERVAL_HOURS)
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        c = conn.cursor()
        
        c.execute("""SELECT fecha_fin FROM ejecuciones 
                     WHERE status='success' 
                     ORDER BY fecha_inicio DESC LIMIT 1""")
        row = c.fetchone()
        conn.close()
        
        if row:
            ultima_busqueda = datetime.fromisoformat(row[0])
            tiempo_desde = datetime.now() - ultima_busqueda
            
            if tiempo_desde < timedelta(hours=config.SEARCH_INTERVAL_HOURS):
                horas_restantes = config.SEARCH_INTERVAL_HOURS - (tiempo_desde.total_seconds() / 3600)
                logger.info(f"⏳ Próxima búsqueda en {horas_restantes:.1f} horas (economizando quota)")
                return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Error verificando última búsqueda: {e}")
        return True


def get_quota_status_message() -> str:
    """⭐ Retorna mensaje de estado de quota para Telegram"""
    puede, usado, limite = check_api_quota()
    porcentaje = (usado / limite) * 100
    
    if porcentaje >= 100:
        return f"🚨 QUOTA AGOTADA\n{usado}/{limite} peticiones\nProxima búsqueda: próximo mes"
    elif porcentaje >= 80:
        return f"⚠️ QUOTA AL {porcentaje:.0f}%\n{usado}/{limite} peticiones\nBúsquedas espaciadas: cada {config.SEARCH_INTERVAL_HOURS}h"
    else:
        return f"✅ QUOTA OK\n{usado}/{limite} peticiones ({porcentaje:.0f}% usado)\nBúsquedas cada {config.SEARCH_INTERVAL_HOURS}h"


def retry_on_exception(max_retries: int = config.MAX_RETRIES, 
                       delay: int = config.RETRY_DELAY):
    """Decorador para reintentar funciones que fallen"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(
                        f"Intento {attempt + 1}/{max_retries} falló en {func.__name__}: {e}. "
                        f"Reintentando en {delay}s..."
                    )
                    time.sleep(delay)
        return wrapper
    return decorator


def init_db():
    """
    Inicializa la base de datos SQLite con todas las tablas necesarias
    ⭐ INCLUYE TABLAS DE TRACKING DE API QUOTA
    """
    try:
        logger.info("Inicializando base de datos...")
        conn = sqlite3.connect(str(config.DB_PATH))
        c = conn.cursor()
        
        # Tabla principal de pisos
        c.execute('''CREATE TABLE IF NOT EXISTS pisos (
            id TEXT PRIMARY KEY,
            titulo TEXT NOT NULL,
            precio REAL,
            precio_m2 REAL,
            metros INTEGER,
            habitaciones INTEGER,
            planta TEXT,
            exterior BOOLEAN,
            estado TEXT,
            link TEXT NOT NULL,
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Tabla de historial de precios
        c.execute('''CREATE TABLE IF NOT EXISTS historial_precios (
            id_piso TEXT,
            precio REAL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_piso) REFERENCES pisos(id)
        )''')
        
        # Crear índices para performance
        c.execute('CREATE INDEX IF NOT EXISTS idx_pisos_precio ON pisos(precio)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_pisos_fecha ON pisos(fecha_actualizacion)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_historial_piso ON historial_precios(id_piso)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_historial_fecha ON historial_precios(fecha)')
        
        # Tabla de estadísticas de ejecución
        c.execute('''CREATE TABLE IF NOT EXISTS ejecuciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_fin DATETIME,
            pisos_procesados INTEGER,
            pisos_nuevos INTEGER,
            pisos_modificados INTEGER,
            errores INTEGER,
            status TEXT
        )''')
        
        # ⭐ NUEVA TABLA: Tracking de peticiones API (CRÍTICO)
        c.execute('''CREATE TABLE IF NOT EXISTS api_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            endpoint TEXT,
            tipo TEXT,
            exitoso BOOLEAN,
            mes_ano TEXT,
            FOREIGN KEY (mes_ano) REFERENCES api_quota(mes_ano)
        )''')
        
        # ⭐ NUEVA TABLA: Quota de API por mes (CRÍTICO: 100 requests/mes)
        c.execute('''CREATE TABLE IF NOT EXISTS api_quota (
            mes_ano TEXT PRIMARY KEY,
            limite INTEGER DEFAULT 100,
            usado INTEGER DEFAULT 0,
            fecha_inicio DATETIME,
            fecha_fin DATETIME
        )''')
        
        # Crear índices
        c.execute('CREATE INDEX IF NOT EXISTS idx_api_requests_fecha ON api_requests(fecha)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_api_requests_mes ON api_requests(mes_ano)')
        
        conn.commit()
        conn.close()
        logger.info("✅ Base de datos inicializada correctamente (CON QUOTA TRACKING)")
        
    except Exception as e:
        logger.error(f"Error inicializando BD: {e}", exc_info=True)
        raise


@retry_on_exception(max_retries=config.MAX_RETRIES, delay=config.RETRY_DELAY)
def enviar_telegram(msg: str, notification_type: str = 'info'):
    """Envía mensaje a Telegram con reintentos automáticos"""
    if not config.ENABLE_TELEGRAM:
        logger.debug("Telegram deshabilitado, skip")
        return
    
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': config.TELEGRAM_CHAT_ID,
            'text': msg,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=payload, timeout=config.TELEGRAM_TIMEOUT)
        response.raise_for_status()
        
        log_event(logger, 'TELEGRAM_SENT', {
            'notification_type': notification_type,
            'length': len(msg)
        })
        
    except Exception as e:
        log_event(logger, 'TELEGRAM_ERROR', {
            'error': str(e),
            'message_preview': msg[:100]
        }, level='error')


@retry_on_exception(max_retries=config.MAX_RETRIES, delay=config.RETRY_DELAY)
def obtener_token() -> Optional[str]:
    """Obtiene token OAuth de Idealista - ⭐ REGISTRA PETICIÓN API"""
    try:
        credenciales = f"{config.IDEALISTA_API_KEY}:{config.IDEALISTA_SECRET}"
        auth_b64 = base64.b64encode(credenciales.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        logger.debug("Solicitando token OAuth...")
        response = requests.post(
            config.IDEALISTA_TOKEN_URL,
            headers=headers,
            data={"grant_type": "client_credentials", "scope": "read"},
            timeout=config.REQUEST_TIMEOUT
        )
        
        # ⭐ REGISTRAR PETICIÓN API
        track_api_request(exitoso=(response.status_code == 200), tipo='token')
        
        if response.status_code == 200:
            token = response.json().get('access_token')
            logger.debug("Token obtenido correctamente")
            return token
        
        logger.error(f"Error obteniendo token ({response.status_code}): {response.text}")
        return None
        
    except Exception as e:
        log_event(logger, 'TOKEN_ERROR', {'error': str(e)}, level='error')
        raise


def buscar_pisos() -> Dict:
    """
    ⭐ CRÍTICO: Busca pisos en Idealista con control de quota
    - Verifica quota antes de buscar
    - Registra cada petición
    - Pausa automáticamente si se alcanza límite
    """
    estadisticas = {
        'total_procesados': 0,
        'totales_nuevos': 0,
        'totales_modificados': 0,
        'errores': 0,
        'status': 'success',
        'quota_alcanzada': False
    }
    
    try:
        # ⭐ VERIFICAR QUOTA PRIMERO
        if not should_search_now():
            logger.info("Búsqueda saltada: próxima búsqueda no es ahora")
            return estadisticas
        
        logger.info("=== INICIANDO BÚSQUEDA DE PISOS ===")
        
        token = obtener_token()
        if not token:
            logger.error("No se pudo obtener token")
            estadisticas['status'] = 'error'
            return estadisticas
        
        headers = {"Authorization": f"Bearer {token}"}
        
        for num_pagina in range(1, config.MAX_PAGES_PER_DAY + 1):
            logger.info(f"Solicitando página {num_pagina}...")
            
            params = {
                "country": "es",
                "operation": "rent",
                "propertyType": "homes",
                "center": f"{config.SEARCH_LATITUDE},{config.SEARCH_LONGITUDE}",
                "distance": config.SEARCH_RADIUS,
                "sort": "asc",
                "maxItems": config.ITEMS_PER_PAGE,
                "numPage": num_pagina,
                "bedrooms": ','.join(config.SEARCH_BEDROOMS),
                "bathrooms": ','.join(config.SEARCH_BATHROOMS),
                "hasMultimedia": "true"
            }
            
            try:
                response = requests.post(
                    config.IDEALISTA_API_URL,
                    headers=headers,
                    data=params,
                    timeout=config.REQUEST_TIMEOUT
                )
                
                # ⭐ REGISTRAR PETICIÓN API
                track_api_request(exitoso=(response.status_code == 200), tipo='search')
                
                # ⭐ VERIFICAR QUOTA DESPUÉS DE CADA PETICIÓN
                puede, usado, limite = check_api_quota()
                if not puede:
                    logger.critical(f"❌ QUOTA AGOTADA ({usado}/{limite})")
                    estadisticas['quota_alcanzada'] = True
                    break
                
                if response.status_code != 200:
                    logger.error(f"Error API ({response.status_code}): {response.text}")
                    estadisticas['errores'] += 1
                    break
                
                data = response.json()
                pisos = data.get('elementList', [])
                total_disponible = data.get('total', 0)
                total_paginas = data.get('totalPages', 1)
                
                logger.info(f"Página {num_pagina}: {len(pisos)} pisos (Total: {total_disponible})")
                
                if not pisos:
                    logger.info("No hay más pisos disponibles")
                    break
                
                nuevos, modificados = procesar_lote(pisos)
                estadisticas['total_procesados'] += len(pisos)
                estadisticas['totales_nuevos'] += nuevos
                estadisticas['totales_modificados'] += modificados
                
                if num_pagina >= total_paginas:
                    logger.info("Fin de resultados disponibles")
                    break
                
                time.sleep(config.PAGE_WAIT_TIME)
                
            except Exception as e:
                logger.error(f"Error procesando página {num_pagina}: {e}", exc_info=True)
                estadisticas['errores'] += 1
                break
        
        logger.info(
            f"=== FIN DE BÚSQUEDA === "
            f"Nuevos: {estadisticas['totales_nuevos']}, "
            f"Modificados: {estadisticas['totales_modificados']}"
        )
        
        # ⭐ MOSTRAR STATUS DE QUOTA AL FINAL
        puede, usado, limite = check_api_quota()
        if puede:
            enviar_telegram(get_quota_status_message(), notification_type='info')
        
    except Exception as e:
        logger.error(f"Error crítico en búsqueda: {e}", exc_info=True)
        estadisticas['status'] = 'error'
    
    return estadisticas


def procesar_lote(pisos: List[Dict]) -> Tuple[int, int]:
    """Procesa un lote de pisos y los almacena en BD"""
    nuevos = 0
    modificados = 0
    
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        c = conn.cursor()
        
        for p in pisos:
            try:
                pid = str(p.get('propertyCode'))
                titulo = p.get('suggestedTexts', {}).get('title', 'Sin título')
                precio = p.get('price')
                metros = p.get('size')
                habitaciones = p.get('rooms')
                planta = p.get('floor', 'Bajo')
                exterior = p.get('exterior', False)
                link = p.get('url', '')
                
                precio_m2 = p.get('priceByArea')
                if not precio_m2 and metros and precio:
                    precio_m2 = round(precio / metros, 1)
                
                c.execute("SELECT precio FROM pisos WHERE id=?", (pid,))
                row = c.fetchone()
                
                if not row:
                    c.execute("""INSERT INTO pisos 
                                 (id, titulo, precio, precio_m2, metros, habitaciones, 
                                  planta, exterior, link, fecha_registro, fecha_actualizacion) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                              (pid, titulo, precio, precio_m2, metros, habitaciones, planta, exterior, link))
                    c.execute("INSERT INTO historial_precios VALUES (?, ?, datetime('now'))", (pid, precio))
                    
                    msg = (
                        f"🆕 <b>NOVEDAD ({precio}€)</b>\n"
                        f"🏠 {titulo}\n"
                        f"🛏️ {habitaciones} hab | 📏 {metros}m² | 💰 {precio_m2}€/m²\n"
                        f"<a href='{link}'>🔗 Ver en Idealista</a>"
                    )
                    enviar_telegram(msg, notification_type='new')
                    nuevos += 1
                    
                elif precio and precio < row[0]:
                    diff = row[0] - precio
                    c.execute("UPDATE pisos SET precio=?, precio_m2=?, fecha_actualizacion=datetime('now') WHERE id=?", 
                             (precio, precio_m2, pid))
                    c.execute("INSERT INTO historial_precios VALUES (?, ?, datetime('now'))", (pid, precio))
                    
                    msg = (
                        f"📉 <b>BAJADA DE PRECIO (-{diff}€)</b>\n"
                        f"🏠 {titulo}\n"
                        f"Antes: {row[0]}€ ➡️ {precio}€\n"
                        f"<a href='{link}'>🔗 Ver piso</a>"
                    )
                    enviar_telegram(msg, notification_type='warning')
                    modificados += 1
                
                elif precio and precio > row[0]:
                    c.execute("UPDATE pisos SET precio=?, fecha_actualizacion=datetime('now') WHERE id=?", 
                             (precio, pid))
                    c.execute("INSERT INTO historial_precios VALUES (?, ?, datetime('now'))", (pid, precio))
                    modificados += 1
                    
            except Exception as e:
                logger.warning(f"Error procesando piso {p.get('propertyCode')}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        if nuevos > 0 or modificados > 0:
            logger.info(f"✨ Procesado: {nuevos} nuevos, {modificados} modificados")
        
    except Exception as e:
        logger.error(f"Error procesando lote: {e}", exc_info=True)
    
    return nuevos, modificados


def backup_database():
    """Realiza backup de la base de datos SQLite"""
    if not config.ENABLE_BACKUPS:
        return
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = config.BACKUP_DIR / f"pisos_backup_{timestamp}.db"
        
        shutil.copy2(str(config.DB_PATH), str(backup_path))
        logger.info(f"Backup realizado: {backup_path}")
        
        for backup_file in sorted(config.BACKUP_DIR.glob("pisos_backup_*.db"))[:-7]:
            backup_file.unlink()
            logger.debug(f"Backup antiguo eliminado: {backup_file}")
        
    except Exception as e:
        logger.error(f"Error realizando backup: {e}", exc_info=True)


def registrar_ejecucion(estadisticas: Dict):
    """Registra la ejecución en BD para monitoreo"""
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        c = conn.cursor()
        
        c.execute("""INSERT INTO ejecuciones 
                     (fecha_fin, pisos_procesados, pisos_nuevos, pisos_modificados, errores, status)
                     VALUES (datetime('now'), ?, ?, ?, ?, ?)""",
                  (estadisticas['total_procesados'],
                   estadisticas['totales_nuevos'],
                   estadisticas['totales_modificados'],
                   estadisticas['errores'],
                   estadisticas['status']))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error registrando ejecución: {e}", exc_info=True)


def health_check() -> bool:
    """Verifica que todo esté funcionando correctamente"""
    try:
        if not config.DB_PATH.exists():
            logger.error("BD no existe")
            return False
        
        conn = sqlite3.connect(str(config.DB_PATH))
        c = conn.cursor()
        c.execute("SELECT 1 FROM pisos LIMIT 1")
        c.execute("SELECT 1 FROM api_quota LIMIT 1")
        conn.close()
        
        valid, msg = config.validate_config()
        if not valid:
            logger.error(f"Config inválida: {msg}")
            return False
        
        logger.info("✅ Health check OK")
        return True
        
    except Exception as e:
        logger.error(f"❌ Health check FAILED: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    try:
        valid_config, config_error = config.validate_config()
        if not valid_config:
            logger.error(f"Configuración inválida: {config_error}")
            exit(1)
        
        init_db()
        
        if not health_check():
            logger.error("Health check fallido al iniciar")
            exit(1)
        
        logger.info("🚀 Bot iniciado correctamente (CON CONTROL DE QUOTA)")
        logger.info(f"⭐ Límite API: {config.MONTHLY_REQUEST_LIMIT} peticiones/mes")
        logger.info(f"⭐ Intervalo búsqueda: cada {config.SEARCH_INTERVAL_HOURS} horas")
        
        contador_ciclos = 0
        while True:
            contador_ciclos += 1
            logger.info(f"\n--- CICLO {contador_ciclos} ---")
            
            try:
                estadisticas = buscar_pisos()
                backup_database()
                registrar_ejecucion(estadisticas)
                
                logger.info(
                    f"📊 Resumen: Nuevos={estadisticas['totales_nuevos']}, "
                    f"Modificados={estadisticas['totales_modificados']}, "
                    f"Errores={estadisticas['errores']}"
                )
                
                if estadisticas['quota_alcanzada']:
                    logger.critical("⛔ BÚSQUEDAS PAUSADAS: QUOTA AGOTADA")
                    enviar_telegram("🚨 QUOTA API AGOTADA\nPróximas búsquedas en el próximo mes", 
                                  notification_type='error')
                
            except Exception as e:
                logger.error(f"Error en ciclo {contador_ciclos}: {e}", exc_info=True)
                enviar_telegram(f"❌ Error en búsqueda: {str(e)}", notification_type='error')
            
            # INTERVALO CONFIGURABLE (por defecto cada 3 días para economizar quota)
            logger.info(f"💤 Esperando {config.SEARCH_INTERVAL_HOURS}h hasta próxima búsqueda...")
            time.sleep(config.SEARCH_INTERVAL_HOURS * 3600)
            
    except KeyboardInterrupt:
        logger.info("⏹️ Bot detenido por usuario")
        exit(0)
    except Exception as e:
        logger.critical(f"Error crítico no recuperable: {e}", exc_info=True)
        exit(1)
