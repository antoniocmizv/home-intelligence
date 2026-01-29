# 🎯 CAMBIOS IMPLEMENTADOS PARA QUOTA API

## Problema Identificado ⚠️

**Idealista API tiene límite de 100 peticiones/mes**

El código original hacía:
- 1 búsqueda por día
- 5-6 peticiones por búsqueda
- **150+ peticiones/mes ❌ EXCEDE LÍMITE**

---

## Solución Implementada ✅

### 1. **Sistema de Tracking en BD**

Nuevas tablas:
```sql
CREATE TABLE api_requests (
    id, fecha, endpoint, tipo, exitoso, mes_ano
)

CREATE TABLE api_quota (
    mes_ano, limite=100, usado, fecha_inicio, fecha_fin
)
```

Cada petición se registra automáticamente.

### 2. **Control Inteligente de Búsquedas**

Nuevas funciones en `main.py`:
- `check_api_quota()` → Verifica estado (usado/límite)
- `should_search_now()` → Decide si buscar (quota + tiempo)
- `track_api_request()` → Registra cada petición
- `get_quota_status_message()` → Mensaje para Telegram

### 3. **Espaciamiento Automático de Búsquedas**

**Antes:**
```
Búsquedas: cada 24h → 30 búsquedas/mes → ~150 requests ❌
```

**Ahora (DEFAULT):**
```
Búsquedas: cada 72h → 10 búsquedas/mes → ~50 requests ✅
Margen de seguridad: 50%
```

### 4. **Alertas Automáticas en Telegram**

- ✅ **OK**: Status en cada búsqueda (quota %)
- ⚠️ **ADVERTENCIA**: Al 80% (80/100)
- 🚨 **CRÍTICO**: Al 100% (pausada automáticamente)

---

## Configuración Nueva

En `.env`:
```env
# Límite API (nunca cambiar)
MONTHLY_REQUEST_LIMIT=100

# Espaciamiento entre búsquedas (AJUSTABLE)
SEARCH_INTERVAL_HOURS=72    # 3 días (default)
# Alternativas:
# 120 = 5 días = ~20 búsquedas/mes = ~100 requests
# 48 = 2 días = ~30 búsquedas/mes = ~150 requests ⚠️

# Alertas de quota
QUOTA_WARNING_THRESHOLD=0.8 # Alerta al 80%
PAUSE_AT_QUOTA=true        # Pausar al 100%
```

---

## Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `config.py` | +20 nuevas variables de quota |
| `main.py` | +300 líneas de control de quota |
| `.env.example` | +30 líneas de documentación |
| API_QUOTA.md | ✨ NUEVO - Guía completa |

---

## Monitoreo

### Ver quota actual
```bash
source utils.sh
query_db "SELECT mes_ano, usado, limite FROM api_quota"
```

### En Metabase
```sql
SELECT 
    mes_ano,
    usado,
    limite,
    ROUND((usado/limite)*100,1) as porcentaje_usado
FROM api_quota
```

---

## Ejemplos de Uso

### Scenario 1: Mantener defaults (RECOMENDADO)
```env
SEARCH_INTERVAL_HOURS=72
MAX_PAGES_PER_DAY=5
# Resultado: ~50 requests/mes (SOSTENIBLE)
```

### Scenario 2: Búsquedas más conservadoras
```env
SEARCH_INTERVAL_HOURS=120
MAX_PAGES_PER_DAY=3
# Resultado: ~25 requests/mes (MUY SEGURO)
```

### Scenario 3: Riesgo calculado
```env
SEARCH_INTERVAL_HOURS=48
MAX_PAGES_PER_DAY=5
# Resultado: ~150 requests/mes ⚠️ (RIESGO)
```

---

## Próximos Pasos

1. **Usar el código actualizado**
   - Reemplazar main.py con versión con quota
   - Usar config.py actualizado

2. **Actualizar .env**
   - Usar .env.example.new como template
   - Validar parámetros

3. **Monitorear primera semana**
   - Ver logs: `docker logs -f intel_idealista`
   - Verificar quota en Metabase
   - Ajustar si es necesario

4. **Documentar decisiones**
   - Ver API_QUOTA.md para entender opciones

---

**¡Ahora tu API será SOSTENIBLE! 🎉**
