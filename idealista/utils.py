"""
Sistema de logging y utilidades
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
import json

class JSONFormatter(logging.Formatter):
    """Formatea logs en JSON para mejor análisis en Metabase"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(log_path: Path, level: str = 'INFO', 
                  max_bytes: int = 5242880, backup_count: int = 5) -> logging.Logger:
    """
    Configura logging con rotación de archivos y salida a consola
    
    Args:
        log_path: Ruta del archivo de logs
        level: Nivel de logging (INFO, DEBUG, WARNING, ERROR)
        max_bytes: Tamaño máximo del archivo antes de rotar
        backup_count: Número de backups a mantener
    """
    logger = logging.getLogger('idealista')
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Eliminar handlers anteriores si existen
    logger.handlers.clear()
    
    # Handler para archivo con rotación
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = JSONFormatter()
    file_handler.setFormatter(file_formatter)
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def log_event(logger: logging.Logger, event_type: str, data: dict, level: str = 'INFO'):
    """
    Registra un evento estructurado
    
    Args:
        logger: Logger instance
        event_type: Tipo de evento (e.g., 'NEW_PROPERTY', 'PRICE_DROP')
        data: Diccionario con datos del evento
        level: Nivel de logging
    """
    message = f"[{event_type}] {json.dumps(data, ensure_ascii=False)}"
    getattr(logger, level.lower())(message)
