# ⚠️ CONTROL DE QUOTA API - 100 PETICIONES/MES

## 🚨 CRÍTICO: Entendiendo las limitaciones

Idealista API tiene un **límite de 100 peticiones mensuales**. El código ha sido modificado para:

1. **Rastrear cada petición** en la BD
2. **Verificar quota antes de buscar**
3. **Espaciar búsquedas automáticamente**
4. **Pausar cuando se alcance el límite**

---

## 📊 MATEMÁTICAS DE LA QUOTA

### Scenario Original (INSOSTENIBLE ❌)
```
- Búsquedas: 1 por día
- Páginas por búsqueda: 5
- Peticiones/día: 5 (token + 4 búsquedas)
- Peticiones/mes: 150+ (EXCEDE LÍMITE DE 100)
```

### Scenario Optimizado (SOSTENIBLE ✅)
```
- Búsquedas: 1 cada 3 días (DEFAULT)
- Páginas por búsqueda: 5
- Peticiones/búsqueda: 5-6 (token + búsquedas)
- Peticiones/mes: ~50 (DENTRO DEL LÍMITE)
- MARGEN DE SEGURIDAD: 50%
```

---

## ⭐ NUEVAS CARACTERÍSTICAS

### 1. **Tracking de Peticiones en BD**
```sql
CREATE TABLE api_requests (
    id INTEGER PRIMARY KEY,
    fecha DATETIME,
    endpoint TEXT,
    tipo TEXT,           -- 'token', 'search'
    exitoso BOOLEAN,
    mes_ano TEXT         -- '2026-01' para agrupar
)

CREATE TABLE api_quota (
    mes_ano TEXT PRIMARY KEY,
    limite INTEGER,      -- 100
    usado INTEGER,       -- Actualizado en tiempo real
    fecha_inicio DATETIME,
    fecha_fin DATETIME
)
```

### 2. **Variables de Control**
En `.env`:
```env
# Idealista API - 100 peticiones/mes
MONTHLY_REQUEST_LIMIT=100
SEARCH_INTERVAL_HOURS=72          # 3 días entre búsquedas
QUOTA_WARNING_THRESHOLD=0.8       # Alerta al 80%
PAUSE_AT_QUOTA=true              # Pausar si alcanza 100%
```

### 3. **Funciones de Validación**

#### `check_api_quota()` → (puede_continuar, usado, limite)
```python
# Verifica estado actual:
# - ✅ OK: Menos del 80%
# - ⚠️ ADVERTENCIA: 80-99%
# - ❌ AGOTADO: 100%+
```

#### `should_search_now()` → bool
```python
# Retorna True si:
# 1. Quota disponible (< 100)
# 2. Tiempo suficiente desde última búsqueda (72h default)
```

#### `track_api_request(exitoso, tipo)`
```python
# Se llama automáticamente tras cada petición
# Actualiza contador en BD
```

---

## 📈 WORKFLOW CON QUOTA

```
INICIO DEL BOT
    ↓
[CADA 3 DÍAS]
    ↓
should_search_now()?
    ├─ ❌ Quota agotada (100/100)
    │   └─→ PAUSA hasta próximo mes
    │
    ├─ ❌ Tiempo insuficiente (< 72h)
    │   └─→ Dormir, reintentar después
    │
    └─ ✅ OK
        └─→ obtener_token()
            ├─→ track_api_request()  (1/5 peticiones)
            └─→ FOR página in 1..5:
                ├─→ requests.post()
                ├─→ track_api_request()  (+1 petición)
                └─→ check_api_quota()  (¿100?)
                    ├─ ❌ SÍ → BREAK
                    └─ ✅ CONTINUE
        
        Resumen → Telegram
        ↓
        Dormir 72 horas
```

---

## 💾 MONITOREO DE QUOTA

### Ver Estado Actual
```bash
# Opción 1: Desde utils.sh
source utils.sh
query_db "SELECT * FROM api_quota WHERE mes_ano = strftime('%Y-%m', 'now')"

# Opción 2: Directo con sqlite3
sqlite3 idealista/data/pisos.db "SELECT mes_ano, usado, limite FROM api_quota"
```

### Ver Historial de Peticiones
```bash
sqlite3 idealista/data/pisos.db "
SELECT 
    mes_ano,
    tipo,
    COUNT(*) as total,
    SUM(CASE WHEN exitoso=1 THEN 1 ELSE 0 END) as exitosas
FROM api_requests
GROUP BY mes_ano, tipo
ORDER BY mes_ano DESC
"
```

### Queries para Metabase
```sql
-- Dashboard: Quota Usage
SELECT 
    mes_ano,
    usado,
    limite,
    ROUND((usado::float/limite)*100, 1) as porcentaje,
    (limite - usado) as disponibles
FROM api_quota
ORDER BY mes_ano DESC

-- Timeline: Peticiones por día
SELECT 
    DATE(fecha) as fecha,
    COUNT(*) as peticiones,
    SUM(CASE WHEN exitoso=1 THEN 1 ELSE 0 END) as exitosas
FROM api_requests
WHERE mes_ano = strftime('%Y-%m', 'now')
GROUP BY DATE(fecha)
ORDER BY fecha DESC
```

---

## 🎛️ AJUSTAR ESTRATEGIA

### Scenario 1: Quiero MÁS búsquedas

**Opción A:** Reducir intervalo
```env
# Cada 2 días en lugar de 3
SEARCH_INTERVAL_HOURS=48
```

⚠️ **Consecuencia:**
```
100 requests / (6 requests/búsqueda * 15 búsquedas/mes) = margen muy ajustado
```

**Opción B:** Reducir páginas
```
Modificar MAX_PAGES_PER_DAY de 5 a 3
```

### Scenario 2: Quiero MENOS búsquedas (conservador)

```env
# Cada 5 días = ~20 búsquedas/mes = 120 requests
# PERO con márgenes extras para reintentos
SEARCH_INTERVAL_HOURS=120
MAX_PAGES_PER_DAY=3
```

### Scenario 3: Control manual

```env
# Desactivar pausas automáticas y controlar manualmente
PAUSE_AT_QUOTA=false
QUOTA_WARNING_THRESHOLD=0.5  # Alerta más temprano
```

---

## 🔔 ALERTAS AUTOMÁTICAS

El bot envía alertas a Telegram en estos momentos:

### 1. **Cada búsqueda (si está OK)**
```
✅ QUOTA OK
45/100 peticiones (45% usado)
Búsquedas cada 72h
```

### 2. **Advertencia al 80%**
```
⚠️ QUOTA AL 80%
80/100 peticiones
Búsquedas espaciadas: cada 72h
```

### 3. **CRÍTICO al 100%**
```
🚨 QUOTA AGOTADA
100/100 peticiones
Proxima búsqueda: próximo mes
```

---

## 🧪 TESTING DE QUOTA

### Test 1: Verificar tracking
```bash
# Hacer 1 búsqueda manual
docker exec intel_idealista python -c "
import sqlite3
from main import buscar_pisos
buscar_pisos()
"

# Verificar que se registró
sqlite3 idealista/data/pisos.db "SELECT COUNT(*) FROM api_requests"
```

### Test 2: Simular quota llena
```bash
sqlite3 idealista/data/pisos.db "
INSERT INTO api_quota VALUES ('2026-01', 100, 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
INSERT INTO api_requests SELECT * FROM api_requests WHERE 1=0 LIMIT 100;
"
```

Luego verificar que `should_search_now()` retorna False

---

## 📋 RECOMENDACIONES

| Parámetro | Recomendado | Conservador | Agresivo |
|-----------|-------------|-------------|----------|
| SEARCH_INTERVAL_HOURS | 72 | 120 | 48 |
| MAX_PAGES_PER_DAY | 5 | 3 | 7 |
| Búsquedas/mes | ~20 | ~10 | ~30 |
| Peticiones/mes | ~100 | ~50 | ~150⚠️ |

**⭐ Recomendación FINAL:** Mantener defaults (72h, 5 páginas) = 50 peticiones/mes

---

## 🚀 IMPLEMENTACIÓN

El código ya está optimizado. Solo tienes que:

1. **Copiar archivos** → main.py, config.py actualizado
2. **Editar .env** → Ajustar variables si necesario
3. **Deploy** → `./deploy.sh`
4. **Monitorear** → Ver quota en Metabase

---

## ⚠️ IMPORTANTE

Si ANTES hacías búsquedas cada 24h:
- **AHORA**: Automáticamente se espacian a cada 72h
- **RAZÓN**: Economizar quota (50 requests/mes en lugar de 150)
- **RESULTADO**: Búsquedas menos frecuentes pero SOSTENIBLES

---

**Última actualización:** Enero 29, 2026  
**Status:** ✅ Implementado y testeado
