FROM python:3.10-slim

# 1. Instalamos dependencias básicas
# Usamos --no-install-recommends para que sea más ligero
RUN apt-get update && apt-get install -y \
    wget \
    xvfb \
    unzip \
    gnupg \
    ca-certificates \
    --no-install-recommends

# 2. Descargamos Google Chrome (.deb) directamente
# Esto evita el error de 'apt-key' y repositorios en Debian 12
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# 3. Instalamos el paquete .deb (apt se encarga de las dependencias que faltan)
RUN apt-get install -y ./google-chrome-stable_current_amd64.deb

# 4. Limpieza para que la imagen ocupe menos
RUN rm google-chrome-stable_current_amd64.deb && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# CMD para correr sin buffer (-u) y ver los logs en tiempo real
CMD ["python", "-u", "main.py"]