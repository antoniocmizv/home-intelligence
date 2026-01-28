FROM python:3.10-slim
WORKDIR /app

# Configurar zona horaria para que los logs salgan con hora de España
RUN apt-get update && apt-get install -y tzdata && \
    ln -fs /usr/share/zoneinfo/Europe/Madrid /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Ejecutamos con -u para ver logs al instante
CMD ["python", "-u", "main.py"]