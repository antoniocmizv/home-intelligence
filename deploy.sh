#!/bin/bash

# Script de deploy de Home Intelligence en Proxmox
# Uso: ./deploy.sh

set -e

echo "🚀 Home Intelligence - Deploy Script"
echo "======================================"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funciones
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Verificar Docker
info "Verificando Docker..."
if ! command -v docker &> /dev/null; then
    error "Docker no está instalado"
fi
docker --version

# Verificar Docker Compose
info "Verificando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose no está instalado"
fi
docker-compose --version

# Verificar .env
if [ ! -f .env ]; then
    warning "Archivo .env no encontrado"
    info "Creando .env desde .env.example..."
    cp .env.example .env
    warning "Por favor, edita .env con tus credenciales antes de continuar"
    exit 1
fi

# Validar variables críticas
info "Validando configuración..."
if ! grep -q "IDEALISTA_API_KEY" .env; then
    error "IDEALISTA_API_KEY no configurada en .env"
fi
if ! grep -q "TELEGRAM_TOKEN" .env; then
    error "TELEGRAM_TOKEN no configurada en .env"
fi

# Crear directorios
info "Creando directorios necesarios..."
mkdir -p idealista/data/backups
mkdir -p metabase-data
mkdir -p prometheus-data

# Build images
info "Compilando imágenes Docker..."
docker-compose build

# Iniciar servicios
info "Iniciando servicios..."
docker-compose up -d

# Esperar a que estén listos
info "Esperando a que los servicios estén listos..."
sleep 5

# Health checks
info "Ejecutando health checks..."

# Idealista
if docker ps | grep -q "intel_idealista"; then
    info "✅ intel_idealista está corriendo"
else
    error "intel_idealista no está corriendo"
fi

# Metabase
if docker ps | grep -q "intel_dashboard"; then
    info "✅ intel_dashboard está corriendo"
else
    error "intel_dashboard no está corriendo"
fi

# Ver logs
info "Mostrando logs de Idealista..."
docker logs --tail 20 intel_idealista

# Resumen
echo ""
echo "======================================"
echo -e "${GREEN}✅ Deploy completado exitosamente${NC}"
echo "======================================"
echo ""
echo "📊 Servicios disponibles:"
echo "  - Metabase Dashboard: http://localhost:3000"
echo "  - Prometheus: http://localhost:9090"
echo ""
echo "📋 Próximos pasos:"
echo "  1. Configurar Metabase en http://localhost:3000"
echo "  2. Conectar la BD SQLite en Metabase"
echo "  3. Crear dashboards y alertas"
echo ""
echo "📖 Para más información, ver README.md"
echo ""
