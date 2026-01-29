# 🏠 Home Intelligence - Rastreador de Pisos

Sistema inteligente de rastreo de anuncios de alquiler en Idealista con análisis de precios en tiempo real usando SQLite + Metabase.

## 📋 Características

### ✨ Funcionalidades Principales
- **Rastreo en Tiempo Real**: Búsqueda continua de pisos cada 24h
- **Detección de Cambios**: Notificaciones de nuevos pisos y bajadas de precio
- **Histórico de Precios**: Registro de cambios para análisis temporal
- **Alertas por Telegram**: Notificaciones instantáneas de oportunidades
- **Dashboard Metabase**: Visualización y análisis de datos

### 🔧 Mejoras Técnicas
- **Logging Estructurado**: Logs en JSON para mejor análisis
- **Sistema de Reintentos**: Recuperación automática de fallos
- **Health Checks**: Verificación de estado del servicio
- **Backups Automáticos**: Copias de seguridad diarias de BD
- **Configuración Centralizada**: Variables de entorno y config.py
- **Type Hints**: Código tipado para mejor mantenibilidad
- **Rotación de Logs**: Gestión automática de archivos de logs
- **Índices en BD**: Optimización de consultas SQLite

## 🚀 Instalación

### Requisitos
- Docker y Docker Compose
- Credenciales de Idealista API
- Token de Telegram Bot
- Proxmox con volúmenes persistentes (opcional)

### Pasos

1. **Clonar o descargar el proyecto**
```bash
cd home-intelligence
```

2. **Configurar variables de entorno**
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

3. **Iniciar los servicios**
```bash
docker-compose up -d
```

4. **Verificar logs**
```bash
docker logs -f intel_idealista
```

## 📁 Estructura del Proyecto

```
home-intelligence/
├── idealista/
│   ├── main.py              # Script principal mejorado
│   ├── config.py            # Configuración centralizada (NUEVO)
│   ├── utils.py             # Utilidades de logging (NUEVO)
│   ├── requirements.txt      # Dependencias Python
│   ├── Dockerfile           # Imagen Docker mejorada
│   ├── data/
│   │   ├── pisos.db         # Base de datos SQLite
│   │   ├── logs.log         # Logs rotados (NUEVO)
│   │   └── backups/         # Backups automáticos (NUEVO)
│   └── ...
├── vuelos/                  # Otro servicio
├── docker-compose.yml       # Orquestación mejorada
├── prometheus.yml           # Monitoreo (NUEVO)
├── .env.example             # Plantilla de config (NUEVO)
└── README.md               # Este archivo
```

## ⚙️ Configuración

### Variables de Entorno Principales

```env
# API Idealista
IDEALISTA_API_KEY=xxx
IDEALISTA_SECRET=xxx

# Telegram
TELEGRAM_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# Búsqueda
SEARCH_LAT=37.1729         # Latitud
SEARCH_LNG=-3.5995         # Longitud
SEARCH_RADIUS=6000         # Radio en metros
SEARCH_BEDROOMS=2,3,4      # Dormitorios
SEARCH_BATHROOMS=1,2,3     # Baños

# Estrategia
MAX_PAGES_PER_DAY=5        # Máximo de páginas por ciclo
LOOP_INTERVAL=86400        # Intervalo entre búsquedas (segundos)

# Logging
LOG_LEVEL=INFO             # DEBUG, INFO, WARNING, ERROR, CRITICAL
ENABLE_BACKUPS=true        # Habilitar backups automáticos
```

## 📊 Metabase - Visualización de Datos

Accede a Metabase en: `http://localhost:3000`

### Consultas Útiles

**Pisos Disponibles**
```sql
SELECT * FROM pisos 
WHERE fecha_actualizacion > datetime('now', '-7 days')
ORDER BY precio ASC;
```

**Análisis de Precios**
```sql
SELECT 
    p.id, 
    p.titulo,
    p.precio,
    AVG(h.precio) as precio_promedio,
    MIN(h.precio) as precio_minimo,
    MAX(h.precio) as precio_maximo
FROM pisos p
LEFT JOIN historial_precios h ON p.id = h.id_piso
GROUP BY p.id
ORDER BY precio_promedio DESC;
```

**Historial de Ejecuciones**
```sql
SELECT * FROM ejecuciones 
ORDER BY fecha_inicio DESC 
LIMIT 10;
```

## 🛠️ Mantenimiento

### Backups

Los backups se crean automáticamente cada 24h:
```bash
# Ver backups
ls -la idealista/data/backups/

# Restaurar from backup
cp idealista/data/backups/pisos_backup_YYYYMMDD_HHMMSS.db idealista/data/pisos.db
docker restart intel_idealista
```

### Logs

Los logs se rotan automáticamente cuando alcanzan 5MB:
```bash
# Ver logs en tiempo real
docker logs -f intel_idealista

# Ver logs históricos
cat idealista/data/logs.log
```

### Health Check

```bash
# Verificar estado del servicio
docker ps --filter "name=intel_idealista" --format "{{.Names}}: {{.Status}}"
```

## 📈 Monitoreo

### Prometheus
Accede a Prometheus en: `http://localhost:9090`

### Métricas Disponibles
- Estado de ejecuciones
- Pisos nuevos detectados
- Bajadas de precio
- Tasa de errores

## 🐛 Troubleshooting

### Error: "No se puede obtener token"
- Verificar credenciales de API en .env
- Verificar conexión a internet
- Revisar límites de API de Idealista

### Error: "BD bloqueada"
- Esperar 10-30 segundos
- Si persiste: `docker restart intel_idealista`

### Logs en vacío
- Verificar: `docker logs intel_idealista`
- Aumentar LOG_LEVEL=DEBUG

### Notificaciones de Telegram no llegan
- Verificar TELEGRAM_TOKEN y TELEGRAM_CHAT_ID
- Probar con curl: 
```bash
curl -X POST https://api.telegram.org/botTOKEN/sendMessage \
  -d chat_id=CHAT_ID -d text="Test"
```

## 🔐 Seguridad

- Nunca hacer commit de `.env` con credenciales reales
- Las credenciales se pasan como variables de entorno
- Los logs no contienen credenciales sensibles
- BD SQLite con permisos restrictivos
- Backups encriptados recomendado en producción

## 📚 Dependencias

- **requests**: HTTP client
- **python-dotenv**: Gestión de variables de entorno
- **sqlite3**: BD (built-in)
- **logging**: Logging (built-in)

## 🚀 Despliegue en Proxmox

### 1. LXC Container con Docker
```bash
# Instalar Docker en el contenedor LXC
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

### 2. Volúmenes Persistentes
```bash
# Montar volumen para datos
/var/lib/lxc/container-id/rootfs/app/data
```

### 3. Límites de Recursos
```yaml
# docker-compose.yml
services:
  bot_idealista:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

## 📝 Logs y Debugging

### Estructura de Logs JSON
```json
{
  "timestamp": "2026-01-29T10:30:45.123456",
  "level": "INFO",
  "message": "[NEW_PROPERTY] {...}",
  "module": "main",
  "function": "procesar_lote",
  "line": 42
}
```

## 🤝 Contribuciones

Las mejoras son bienvenidas. Algunos areas de mejora:
- [ ] Tests unitarios
- [ ] API REST para consultas
- [ ] Webhooks en lugar de polling
- [ ] Soporte para múltiples ubicaciones
- [ ] ML para predicción de precios
- [ ] Alertas por email

## 📄 Licencia

MIT License

## 📞 Soporte

Para reportar bugs o solicitar features, crear un issue en el repositorio.

---

**Última actualización**: Enero 29, 2026
**Versión**: 2.0.0 (Major Refactor)
