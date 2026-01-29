#!/bin/bash

# Scripts útiles para gestionar Home Intelligence en Proxmox
# Uso: source utils.sh
# Luego: start_all, stop_all, logs_idealista, etc.

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
PROJECT_DIR="/opt/home-intelligence"  # Cambiar según tu instalación
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

# ====================================
# FUNCIONES PRINCIPALES
# ====================================

start_all() {
    echo -e "${BLUE}📡 Iniciando todos los servicios...${NC}"
    cd "$PROJECT_DIR"
    docker-compose up -d
    sleep 3
    status_all
}

stop_all() {
    echo -e "${YELLOW}⛔ Deteniendo todos los servicios...${NC}"
    cd "$PROJECT_DIR"
    docker-compose down
    echo -e "${GREEN}✅ Detenido${NC}"
}

restart_all() {
    echo -e "${YELLOW}🔄 Reiniciando todos los servicios...${NC}"
    stop_all
    sleep 2
    start_all
}

status_all() {
    echo -e "${BLUE}📊 Estado de servicios:${NC}"
    docker ps -a --filter "label=monitoring=enabled" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# ====================================
# IDEALISTA BOT
# ====================================

logs_idealista() {
    local lines=${1:-50}
    echo -e "${BLUE}📋 Últimas $lines líneas de logs:${NC}"
    docker logs --tail "$lines" -f intel_idealista
}

restart_idealista() {
    echo -e "${YELLOW}🔄 Reiniciando Idealista bot...${NC}"
    docker restart intel_idealista
    echo -e "${GREEN}✅ Reiniciado${NC}"
    sleep 2
    logs_idealista 10
}

shell_idealista() {
    echo -e "${BLUE}🔧 Entrando en shell del contenedor...${NC}"
    docker exec -it intel_idealista /bin/bash
}

stats_idealista() {
    echo -e "${BLUE}📊 Estadísticas de contenedor:${NC}"
    docker stats intel_idealista --no-stream
}

# ====================================
# METABASE
# ====================================

logs_metabase() {
    local lines=${1:-50}
    echo -e "${BLUE}📋 Logs de Metabase:${NC}"
    docker logs --tail "$lines" -f intel_dashboard
}

open_metabase() {
    echo -e "${GREEN}🌐 Abriendo Metabase en http://localhost:3000${NC}"
    # Para Linux
    which xdg-open &>/dev/null && xdg-open "http://localhost:3000"
    # Para macOS
    which open &>/dev/null && open "http://localhost:3000"
    # Para Windows (si estás en WSL)
    which powershell.exe &>/dev/null && powershell.exe Start http://localhost:3000
}

# ====================================
# BASE DE DATOS
# ====================================

backup_db() {
    echo -e "${YELLOW}💾 Realizando backup manual...${NC}"
    cd "$PROJECT_DIR"
    timestamp=$(date +%Y%m%d_%H%M%S)
    cp idealista/data/pisos.db idealista/data/backups/pisos_backup_manual_$timestamp.db
    echo -e "${GREEN}✅ Backup realizado: pisos_backup_manual_$timestamp.db${NC}"
}

restore_db() {
    local backup_file=$1
    if [ -z "$backup_file" ]; then
        echo -e "${RED}❌ Uso: restore_db <backup_file>${NC}"
        echo "Backups disponibles:"
        ls -lh "$PROJECT_DIR/idealista/data/backups/"
        return 1
    fi
    
    echo -e "${YELLOW}⚠️  Restaurando desde $backup_file...${NC}"
    read -p "¿Estás seguro? (s/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        cd "$PROJECT_DIR"
        docker-compose down
        cp "idealista/data/backups/$backup_file" idealista/data/pisos.db
        docker-compose up -d
        echo -e "${GREEN}✅ BD restaurada${NC}"
    else
        echo "Cancelado"
    fi
}

query_db() {
    local sql=$1
    if [ -z "$sql" ]; then
        sql="SELECT COUNT(*) as total_pisos FROM pisos;"
    fi
    echo -e "${BLUE}📊 Ejecutando query:${NC}"
    echo "$sql"
    docker exec intel_idealista sqlite3 /app/data/pisos.db "$sql"
}

list_backups() {
    echo -e "${BLUE}💾 Backups disponibles:${NC}"
    ls -lh "$PROJECT_DIR/idealista/data/backups/" | tail -10
}

# ====================================
# MONITOREO
# ====================================

health_check() {
    echo -e "${BLUE}🏥 Health Check:${NC}"
    echo ""
    
    # Idealista
    echo -ne "  Idealista: "
    if docker exec intel_idealista python -c "import sqlite3; sqlite3.connect('/app/data/pisos.db').execute('SELECT 1')" 2>/dev/null; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ FAIL${NC}"
    fi
    
    # Metabase
    echo -ne "  Metabase: "
    if curl -s http://localhost:3000/api/health | grep -q '"status":"ok"' 2>/dev/null; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ FAIL${NC}"
    fi
    
    # Docker daemon
    echo -ne "  Docker: "
    if docker ps &>/dev/null; then
        echo -e "${GREEN}✅ OK${NC}"
    else
        echo -e "${RED}❌ FAIL${NC}"
    fi
}

monitor_pisos() {
    echo -e "${BLUE}📊 Monitoreo de pisos:${NC}"
    while true; do
        clear
        echo "=== Home Intelligence Monitor ==="
        echo "$(date)"
        echo ""
        
        # Total pisos
        total=$(docker exec intel_idealista sqlite3 /app/data/pisos.db "SELECT COUNT(*) FROM pisos;" 2>/dev/null)
        echo "📍 Total pisos: $total"
        
        # Últimos 24h
        last_24=$(docker exec intel_idealista sqlite3 /app/data/pisos.db "SELECT COUNT(*) FROM pisos WHERE fecha_registro > datetime('now', '-1 day');" 2>/dev/null)
        echo "🆕 Últimas 24h: $last_24"
        
        # Precio promedio
        avg_price=$(docker exec intel_idealista sqlite3 /app/data/pisos.db "SELECT ROUND(AVG(precio), 0) FROM pisos;" 2>/dev/null)
        echo "💰 Precio promedio: ${avg_price}€"
        
        # Pisos con mejor relación precio/m2
        echo ""
        echo "🏆 Top 5 mejores m2:"
        docker exec intel_idealista sqlite3 /app/data/pisos.db "SELECT titulo, precio_m2, precio FROM pisos ORDER BY precio_m2 ASC LIMIT 5;" 2>/dev/null | column -t -s'|'
        
        echo ""
        echo "Actualizando en 10s (Ctrl+C para salir)..."
        sleep 10
    done
}

# ====================================
# LOGS Y DEBUG
# ====================================

show_errors() {
    echo -e "${BLUE}❌ Errores recientes:${NC}"
    docker logs intel_idealista 2>&1 | grep -i "error" | tail -20
}

show_warnings() {
    echo -e "${YELLOW}⚠️  Advertencias recientes:${NC}"
    docker logs intel_idealista 2>&1 | grep -i "warning" | tail -20
}

show_events() {
    echo -e "${BLUE}📋 Eventos recientes:${NC}"
    docker logs intel_idealista 2>&1 | grep -i "\[" | tail -30
}

# ====================================
# MANTENIMIENTO
# ====================================

cleanup_old_logs() {
    echo -e "${YELLOW}🗑️  Limpiando logs antiguos...${NC}"
    find "$PROJECT_DIR/idealista/data" -name "logs.log.*" -mtime +30 -delete
    echo -e "${GREEN}✅ Limpieza completada${NC}"
}

rebuild_containers() {
    echo -e "${YELLOW}🔨 Reconstruyendo contenedores...${NC}"
    cd "$PROJECT_DIR"
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    echo -e "${GREEN}✅ Contenedores reconstruidos${NC}"
}

disk_usage() {
    echo -e "${BLUE}💾 Uso de disco:${NC}"
    du -sh "$PROJECT_DIR"/*
    echo ""
    echo "Data directory:"
    du -sh "$PROJECT_DIR/idealista/data"/*
}

# ====================================
# AYUDA
# ====================================

help_menu() {
    cat << EOF
${BLUE}Home Intelligence - Utilidades para Proxmox${NC}

${GREEN}Servicios:${NC}
  start_all           Inicia todos los servicios
  stop_all            Detiene todos los servicios
  restart_all         Reinicia todos los servicios
  status_all          Muestra estado de servicios
  health_check        Ejecuta health check completo

${GREEN}Idealista Bot:${NC}
  logs_idealista      Muestra logs (ej: logs_idealista 100)
  restart_idealista   Reinicia el bot
  shell_idealista     Accede al shell del contenedor
  stats_idealista     Muestra estadísticas

${GREEN}Metabase:${NC}
  logs_metabase       Muestra logs de Metabase
  open_metabase       Abre Metabase en navegador

${GREEN}Base de Datos:${NC}
  query_db            Ejecuta query SQL (ej: query_db "SELECT * FROM pisos LIMIT 5")
  backup_db           Realiza backup manual
  restore_db          Restaura desde backup (ej: restore_db <file>)
  list_backups        Lista backups disponibles

${GREEN}Monitoreo:${NC}
  monitor_pisos       Monitor en tiempo real
  show_errors         Muestra errores recientes
  show_warnings       Muestra advertencias recientes
  show_events         Muestra eventos recientes

${GREEN}Mantenimiento:${NC}
  cleanup_old_logs    Limpia logs antiguos
  rebuild_containers  Reconstruye contenedores
  disk_usage          Muestra uso de disco

${GREEN}Ayuda:${NC}
  help_menu           Muestra este menú

${YELLOW}Ejemplos:${NC}
  logs_idealista 50
  query_db "SELECT COUNT(*) FROM pisos"
  restore_db pisos_backup_20260129_100000.db
  monitor_pisos

EOF
}

# Mostrar ayuda si no hay argumentos
if [ $# -eq 0 ]; then
    help_menu
fi
