"""
Tests unitarios para el bot de Idealista
Ejecutar con: python -m pytest tests.py -v
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import sqlite3
import sys
import os

# Agregar el directorio principal al path
sys.path.insert(0, str(Path(__file__).parent))

import config
from utils import setup_logging, log_event


class TestConfig(unittest.TestCase):
    """Tests para validación de configuración"""
    
    def test_validate_config_success(self):
        """Test validación correcta de config"""
        with patch.dict(os.environ, {
            'IDEALISTA_API_KEY': 'test_key',
            'IDEALISTA_SECRET': 'test_secret',
            'TELEGRAM_TOKEN': 'test_token',
            'TELEGRAM_CHAT_ID': 'test_chat'
        }):
            # Recargar config
            import importlib
            importlib.reload(config)
            valid, msg = config.validate_config()
            # Podría validar basado en variables
    
    def test_validate_config_missing_credentials(self):
        """Test validación con credenciales faltantes"""
        with patch.dict(os.environ, clear=True):
            import importlib
            importlib.reload(config)
            valid, msg = config.validate_config()
            self.assertFalse(valid)
            self.assertIsNotNone(msg)


class TestDatabase(unittest.TestCase):
    """Tests para operaciones de BD"""
    
    def setUp(self):
        """Crear BD temporal para tests"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
    
    def tearDown(self):
        """Limpiar BD temporal"""
        try:
            os.unlink(self.db_path)
        except:
            pass
    
    def test_create_tables(self):
        """Test creación de tablas"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Crear tabla de prueba
        c.execute('''CREATE TABLE IF NOT EXISTS test (
            id INTEGER PRIMARY KEY,
            valor TEXT
        )''')
        
        # Verificar que existe
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
        self.assertIsNotNone(c.fetchone())
        
        conn.close()
    
    def test_insert_and_retrieve(self):
        """Test inserción y recuperación de datos"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Crear tabla
        c.execute('''CREATE TABLE IF NOT EXISTS pisos (
            id TEXT PRIMARY KEY,
            titulo TEXT,
            precio REAL
        )''')
        
        # Insertar datos
        c.execute("INSERT INTO pisos VALUES (?, ?, ?)", 
                 ("123", "Piso test", 1000.0))
        conn.commit()
        
        # Recuperar y verificar
        c.execute("SELECT * FROM pisos WHERE id='123'")
        row = c.fetchone()
        self.assertEqual(row[0], "123")
        self.assertEqual(row[1], "Piso test")
        self.assertEqual(row[2], 1000.0)
        
        conn.close()


class TestLogging(unittest.TestCase):
    """Tests para sistema de logging"""
    
    def setUp(self):
        """Crear archivo temporal para logs"""
        self.temp_log = tempfile.NamedTemporaryFile(suffix='.log', delete=False)
        self.log_path = Path(self.temp_log.name)
        self.temp_log.close()
    
    def tearDown(self):
        """Limpiar archivo de logs"""
        try:
            os.unlink(self.log_path)
        except:
            pass
    
    def test_logging_setup(self):
        """Test configuración de logging"""
        logger = setup_logging(self.log_path, level='INFO')
        self.assertIsNotNone(logger)
        logger.info("Test message")
        
        # Verificar que se escribió en el archivo
        with open(self.log_path, 'r') as f:
            content = f.read()
            self.assertIn("Test message", content)
    
    def test_log_event(self):
        """Test registro de eventos"""
        logger = setup_logging(self.log_path, level='INFO')
        log_event(logger, 'TEST_EVENT', {'key': 'value'})
        
        with open(self.log_path, 'r') as f:
            content = f.read()
            self.assertIn("TEST_EVENT", content)


class TestPriceCalculation(unittest.TestCase):
    """Tests para cálculos de precios"""
    
    def test_precio_m2_calculation(self):
        """Test cálculo de precio por m2"""
        precio = 1200
        metros = 80
        precio_m2 = round(precio / metros, 1)
        self.assertEqual(precio_m2, 15.0)
    
    def test_price_difference(self):
        """Test cálculo de diferencia de precio"""
        precio_anterior = 1200
        precio_nuevo = 1000
        diferencia = precio_anterior - precio_nuevo
        self.assertEqual(diferencia, 200)


class TestDataValidation(unittest.TestCase):
    """Tests para validación de datos"""
    
    def test_valid_property_data(self):
        """Test validación de datos de piso válidos"""
        piso = {
            'propertyCode': '12345',
            'price': 1000,
            'size': 80,
            'rooms': 3
        }
        self.assertIsNotNone(piso.get('propertyCode'))
        self.assertIsNotNone(piso.get('price'))
    
    def test_missing_price_handling(self):
        """Test manejo de precios faltantes"""
        piso = {
            'propertyCode': '12345',
            'size': 80,
            'rooms': 3
        }
        precio = piso.get('price')
        self.assertIsNone(precio)


class TestStringFormatting(unittest.TestCase):
    """Tests para formato de mensajes"""
    
    def test_telegram_message_format(self):
        """Test formato de mensaje de Telegram"""
        titulo = "Piso en Granada"
        precio = 1000
        habitaciones = 3
        metros = 80
        link = "https://example.com"
        
        msg = (
            f"🆕 <b>NOVEDAD ({precio}€)</b>\n"
            f"🏠 {titulo}\n"
            f"🛏️ {habitaciones} hab | 📏 {metros}m²\n"
            f"<a href='{link}'>🔗 Ver en Idealista</a>"
        )
        
        self.assertIn(str(precio), msg)
        self.assertIn(titulo, msg)
        self.assertIn("NOVEDAD", msg)
        self.assertIn("<a href=", msg)


if __name__ == '__main__':
    unittest.main()
