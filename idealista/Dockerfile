FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema e configurar zona horaria
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    sqlite3 \
    && ln -fs /usr/share/zoneinfo/Europe/Madrid /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crear directorio de datos
RUN mkdir -p /app/data /app/data/backups && chmod 777 /app/data /app/data/backups

# Copiar código de la aplicación
COPY config.py .
COPY utils.py .
COPY main.py .

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/app/data/pisos.db').cursor().execute('SELECT 1'); print('OK')" || exit 1

# Ejecutar con -u para logs en tiempo real
CMD ["python", "-u", "main.py"]