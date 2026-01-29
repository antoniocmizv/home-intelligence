% # 🖥️ GUÍA DE DESPLIEGUE EN PROXMOX

## 1️⃣ PREPARACIÓN DEL CONTENEDOR LXC

### Crear container LXC en Proxmox

```bash
# Opción A: Desde UI de Proxmox
# 1. Ir a Datacenter > Create CT
# 2. Hostname: home-intelligence
# 3. Password: (seguro)
# 4. Template: debian-12-standard
# 5. Disk: 50GB
# 6. CPU: 4 cores
# 7. Memory: 4GB
# 8. Network: bridge (vmbr0)

# Opción B: Desde línea de comandos
pct create 100 local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst \
  --hostname home-intelligence \
  --cores 4 \
  --memory 4096 \
  --rootfs 50 \
  --net0 name=eth0,bridge=vmbr0
```

### Iniciar y acceder al contenedor

```bash
# Iniciar
pct start 100

# Acceder por consola
pct enter 100

# O por SSH (después de configurar red)
ssh root@192.168.x.x
```

---

## 2️⃣ INSTALAR DOCKER EN PROXMOX

```bash
# Actualizar paquetes
apt update && apt upgrade -y

# Instalar dependencias
apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Agregar GPG key de Docker
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Agregar repositorio Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verificar instalación
docker --version
docker run hello-world

# (Opcional) Instalar docker-compose v1
apt install -y docker-compose
```

---

## 3️⃣ CLONAR O DESCARGAR EL PROYECTO

### Opción A: Desde Git

```bash
# Instalar git
apt install -y git

# Clonar (si tienes repo remoto)
cd /opt
git clone https://github.com/usuario/home-intelligence.git

# O si es un zip
cd /opt
unzip home-intelligence.zip
```

### Opción B: Copiar desde local

```bash
# En tu máquina local
scp -r ./home-intelligence root@192.168.x.x:/opt/

# O usando rsync (más eficiente)
rsync -avz ./home-intelligence/ root@192.168.x.x:/opt/home-intelligence/
```

### Opción C: Descargar en Proxmox

```bash
# En el contenedor LXC
cd /opt
apt install -y wget unzip
wget https://github.com/usuario/home-intelligence/archive/main.zip
unzip main.zip
mv home-intelligence-main home-intelligence
cd home-intelligence
```

---

## 4️⃣ CONFIGURAR EL PROYECTO

```bash
cd /opt/home-intelligence

# Copiar plantilla de configuración
cp .env.example .env

# Editar con tus credenciales
nano .env

# Variables críticas a editar:
# IDEALISTA_API_KEY=xxxxx
# IDEALISTA_SECRET=xxxxx
# TELEGRAM_TOKEN=xxxxx
# TELEGRAM_CHAT_ID=xxxxx
```

### Asignar permisos

```bash
# Hacer scripts ejecutables
chmod +x deploy.sh utils.sh

# Crear directorio de datos con permisos
mkdir -p /opt/home-intelligence/idealista/data/{backups,logs}
chmod -R 755 /opt/home-intelligence/idealista/data
```

---

## 5️⃣ DEPLOY

### Opción A: Deploy Automático

```bash
cd /opt/home-intelligence
./deploy.sh
```

### Opción B: Deploy Manual

```bash
cd /opt/home-intelligence

# Build
docker-compose build

# Start
docker-compose up -d

# Verificar
docker ps
```

---

## 6️⃣ CONFIGURAR VOLÚMENES PERSISTENTES (Proxmox)

### En la UI de Proxmox

Si quieres que los datos persistan incluso si el LXC se elimina:

```bash
# Opción A: Mount points desde Proxmox UI
# 1. Seleccionar container 100
# 2. Resources > Add Mount Point
# 3. Storage: local (o tu storage)
# 4. Path: /opt/home-intelligence/idealista/data
# 5. Content: Binaries, Files, etc.

# Opción B: Desde línea de comandos
pct set 100 -mp0 /mnt/pve/local/home-intelligence/data,mp=/opt/home-intelligence/idealista/data
```

### Backup automático en Proxmox

```bash
# Crear cron para backup diario
crontab -e

# Agregar línea:
0 2 * * * pct dump 100 /mnt/pve/local/backups/home-intelligence-$(date +\%Y\%m\%d).tar.zst

# O usar Proxmox Backup Server para backup automático
```

---

## 7️⃣ ACCESO A SERVICIOS

### Metabase
```
URL: http://192.168.x.x:3000
Usuario: admin@metabase.com
Contraseña: (configurar en primer login)
```

### Prometheus
```
URL: http://192.168.x.x:9090
```

### SSH al contenedor
```bash
# Desde tu máquina
ssh root@192.168.x.x

# O desde Proxmox
pct enter 100
```

---

## 8️⃣ VERIFICAR ESTADO

```bash
# Ver status
docker ps

# Ver logs
docker logs -f intel_idealista

# Health check
docker exec intel_idealista python -c "import sqlite3; sqlite3.connect('/app/data/pisos.db').execute('SELECT 1'); print('OK')"

# Query rápida
docker exec intel_idealista sqlite3 /app/data/pisos.db "SELECT COUNT(*) FROM pisos;"
```

---

## 9️⃣ SCRIPTS ÚTILES PARA PROXMOX

```bash
# Sourcing los utils
source /opt/home-intelligence/utils.sh

# Ejemplos de uso
logs_idealista 50
health_check
status_all
monitor_pisos
backup_db
list_backups
disk_usage
```

---

## 🔟 CONFIGURACIÓN DE ALERTAS Y BACKUPS

### Backup automático del proyecto

```bash
# Crear script en /root/backup-home-intel.sh
#!/bin/bash
BACKUP_DIR="/mnt/pve/backups/home-intelligence"
mkdir -p "$BACKUP_DIR"

# Backup de BD
cp /opt/home-intelligence/idealista/data/pisos.db \
   "$BACKUP_DIR/pisos_$(date +%Y%m%d_%H%M%S).db"

# Limpiar backups de más de 30 días
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete

# Agregar a crontab
0 3 * * * /root/backup-home-intel.sh

crontab -e
# Agregar línea anterior
```

### Alertas en Proxmox

```bash
# Si la CPU/RAM es alta, ver logs
docker stats intel_idealista

# Si hay errores
docker logs intel_idealista | grep ERROR

# Reiniciar si falla
docker restart intel_idealista
```

---

## 1️⃣1️⃣ LIMIT DE RECURSOS (Proxmox)

```bash
# Editar límites en Proxmox UI o CLI
pct set 100 -cores 4 -memory 4096 -swap 2048

# O en /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

---

## 1️⃣2️⃣ TROUBLESHOOTING

### BD bloqueada
```bash
# Si dice "database is locked"
docker restart intel_idealista
```

### Sin conexión a API Idealista
```bash
# Verificar credenciales
grep IDEALISTA /opt/home-intelligence/.env

# Probar conexión
curl -X POST https://api.idealista.com/oauth/token
```

### Metabase no se conecta a BD
```bash
# Verificar permisos
ls -la /opt/home-intelligence/idealista/data/pisos.db

# Dar permisos si es necesario
chmod 666 /opt/home-intelligence/idealista/data/pisos.db
```

---

## 1️⃣3️⃣ ACTUALIZAR A NUEVAS VERSIONES

```bash
# Hacer pull de cambios
cd /opt/home-intelligence
git pull origin main

# O descargar zip nuevo
wget https://github.com/usuario/home-intelligence/archive/main.zip
unzip -o main.zip

# Reconstruir contenedores
docker-compose down
docker-compose build
docker-compose up -d
```

---

## 1️⃣4️⃣ MONITOREO RECOMENDADO

### Configurar en Proxmox
- [ ] Monitorar RAM (alert si >3.5GB)
- [ ] Monitorar CPU (alert si >80%)
- [ ] Monitorar disco (alert si >40GB usado)
- [ ] Verificar uptime diario

### Configurar en Prometheus
- [ ] Alertas de errores en Idealista
- [ ] Alertas de BD bloqueada
- [ ] Alertas de Telegram no envío
- [ ] Métricas de pisos procesados

### Verificación manual
```bash
# Cada día
docker logs intel_idealista | tail -50

# Cada semana
docker exec intel_idealista sqlite3 /app/data/pisos.db \
  "SELECT COUNT(*) as total_pisos, 
          COUNT(DISTINCT DATE(fecha_registro)) as dias FROM pisos;"

# Cada mes
# Revisar Metabase para tendencias
```

---

## 1️⃣5️⃣ DOCUMENTACIÓN Y CONTACTO

- **README.md**: Documentación general
- **MEJORAS.md**: Detalle de cambios
- **ESTRUCTURA.md**: Estructura del proyecto
- **Esta guía**: Despliegue en Proxmox

---

**✅ ¡Tu instalación está lista para producción!**

**Próximos pasos:**
1. ✅ Configurar Metabase
2. ✅ Crear dashboards
3. ✅ Probar alertas Telegram
4. ✅ Hacer primer backup manual
5. ✅ Monitorear por 24-48h

**Fecha:** Enero 29, 2026
**Versión:** 2.0.0
