# Arquitectura

## Visión general

```
Navegador ──HTTPS──▶ Next.js (web, :3000) ──/api/* proxy──▶ FastAPI (api, :8000) ──▶ PostgreSQL 16
   cookie httpOnly        páginas React                     servicios por dominio       RLS forzada
   + cabecera CSRF        React Query                       motor de análisis            por organización
                                                            almacenamiento de archivos ──▶ disco (por organización)
```

* **Mismo origen.** El navegador solo habla con el servidor web; Next.js reenvía `/api/*` al backend. Así la cookie
  de sesión puede ser `httpOnly` + `SameSite=Lax`, no se expone la URL interna del backend y no se requiere CORS.
* **Backend monolítico modular.** Una sola aplicación FastAPI organizada por dominio (`app/services/*`), con
  interfaces claras para separar servicios cuando la carga lo justifique. Sin colas ni microservicios por ahora:
  el volumen de la v0.1 no los requiere (ver ROADMAP).

## Backend (`backend/app`)

| Capa | Ubicación | Responsabilidad |
|---|---|---|
| Configuración | `core/config.py` | Variables `IIOS_*` (pydantic-settings); validación de configuración insegura en producción (`main.check_production_settings`) |
| Base de datos | `core/db.py`, `models/` | SQLAlchemy 2; tipo JSON→JSONB en PostgreSQL; `set_tenant()` y evento `after_begin` que fija `app.current_org_id` en cada transacción |
| Seguridad | `core/security.py`, `core/permissions.py`, `api/deps.py` | bcrypt (con pre-hash SHA-256), tokens opacos con hash, política de contraseñas, matriz rol→permisos, dependencia `require(perm, module=)` |
| Errores y registros | `core/errors.py`, `core/logging.py` | Respuestas de error uniformes con `request_id`, sin trazas internas; logs JSON con redacción de secretos |
| API | `api/routes/*` | Rutas REST `/api/v1` (documentadas en OpenAPI) |
| Servicios | `services/*` | Lógica de negocio: autenticación, organizaciones, importación, análisis, hallazgos, KPI, panel, reportes, demo, auditoría |
| Análisis | `services/analytics/*` | Cálculos puros y reproducibles con pandas; reglas de hallazgos; motor que persiste resultados |

### Aislamiento multiempresa (dos capas)

1. **Servicio:** toda tabla de cliente tiene `organization_id`. Las consultas filtran por la organización del
   contexto y `services/tenancy.get_owned()` devuelve *404* (no *403*) para registros de otra organización.
2. **Base de datos (PostgreSQL):** la migración `0001` activa `ENABLE` + `FORCE ROW LEVEL SECURITY` con la política
   `organization_id = iios_current_org()` en las 11 tablas de cliente. La aplicación se conecta con un rol **no
   superusuario y sin BYPASSRLS**; si un filtro faltara en el código, la base de datos sigue sin devolver filas de
   otra organización. Sin organización fijada, las consultas devuelven 0 filas (falla cerrada). Probado en
   `tests/test_database.py::TestRowLevelSecurity`.

Consecuencias operativas documentadas: los respaldos/restauraciones y las migraciones de datos necesitan un rol con
`BYPASSRLS` o levantar `FORCE` temporalmente (ver migración `0002`).

### Autenticación y sesiones

* Sesiones de servidor (`auth_sessions`), token aleatorio de 256 bits; en la base solo se guarda su SHA-256.
* Expiración por inactividad (120 min) y absoluta (24 h), revocación en logout, cambio y recuperación de contraseña.
* CSRF *double submit*: la cookie `iios_csrf` (legible) debe repetirse en la cabecera `X-CSRF-Token` en toda
  petición no-GET autenticada por cookie; se compara contra el hash guardado en la sesión.
* Token *Bearer* opcional (para integraciones/scripts); no requiere CSRF porque el navegador no lo envía solo.
* La membresía y el rol se verifican en **cada** petición: un cambio de rol o desactivación aplica de inmediato.

### Flujo de importación

```
upload ──▶ ImportJob(parsed) ──preview──▶ mapping + validate ──▶ ImportJob(validated, resumen)
       └ archivo guardado con nombre aleatorio + SHA-256                      │
commit ──▶ re-lee y re-valida el archivo ──▶ inserta DatasetRecords (1 transacción) ──▶ análisis
revert ──▶ elimina exactamente los registros de esa importación ──▶ re-análisis
```

* La confirmación usa *compare-and-set* (`UPDATE … WHERE status='validated'`) para que dos confirmaciones
  simultáneas no dupliquen datos (probado con hilos concurrentes en SQLite y PostgreSQL).
* Los registros guardan el renglón de origen y la importación que los creó → toda cifra se rastrea al archivo.

### Motor de análisis

`engine.run_analysis(dataset)`:

1. Carga registros → DataFrame tipado (`frames.py`) → preparación por dominio (`domain/*.py`: intervalos entre
   fallas, rendimiento tanque a tanque, ROP/ABC, etc.).
2. Perfil de calidad (`profiling.py`).
3. KPI del catálogo (`kpis.py`): total, por dimensión y mensual; si faltan datos → `insufficient_data` sin valor.
4. Reglas (`rules.py`) → `FindingDraft` con naturaleza, evidencia, método, prioridad, impacto tipificado y confianza.
5. *Upsert* de hallazgos por huella (`sha256(dataset|regla|clave)`): no duplica, actualiza, **reabre** si se marcó
   resuelto y persiste, y marca `condition_active=false` cuando ya no se detecta (verificación de resultados).
6. Guarda `AnalysisRun` (perfil, resumen) y `KpiValue` (con entradas de la fórmula) → historial reproducible.

Determinista: mismos datos + parámetros + objetivos ⇒ mismos resultados. Ningún modelo de lenguaje interviene en
cálculos ni modifica registros.

### Impacto económico

Cada monto lleva un `impact_kind`: `recorded_cost` (costo ya registrado), `estimated_excess_cost` (sobrecosto
estimado) o `capital_tied` (valor de inventario expuesto). Los tipos **no se suman entre sí** en ningún panel o
reporte. La distinción ahorro potencial/estimado/aprobado/observado pertenece al módulo de costos (Fase 3).

## Frontend (`frontend/src`)

* Next.js 15 (App Router), React 19, TypeScript estricto, Tailwind 4, React Query, react-hook-form + zod, Recharts.
* `lib/api.ts`: cliente único (CSRF, errores tipados con `request_id`, redirección a login/cambio de contraseña).
* `middleware.ts`: redirección temprana a `/login` si no hay cookie (conveniencia; el backend es quien valida).
* Los permisos en la interfaz solo ocultan acciones; la autorización real está en el backend.
* Marca blanca: `lib/brand.ts` + `NEXT_PUBLIC_BRAND_*` + `public/brand/logo.svg`; color primario como variable CSS.

## Decisiones relevantes

| Decisión | Motivo |
|---|---|
| Sesiones de servidor en lugar de JWT | Revocación inmediata, sin secretos de firma que rotar, cookie httpOnly |
| JSON por registro (`dataset_records.data`) en vez de tablas por plantilla | Permite importar cualquier fuente desde la Fase 2 y revertir por importación; los módulos operativos (Fase 3) tendrán tablas propias con integridad referencial |
| RLS forzada + rol no superusuario | Defensa en profundidad contra errores de filtrado |
| Cálculos con pandas en el proceso de la API | Suficiente para ≤200 000 renglones por importación; migrar a tareas en segundo plano cuando se requiera |
| Fecha de referencia de obsolescencia = último movimiento del conjunto | Resultados reproducibles (no dependen de "hoy") |
| Estadística sin dependencias (Mann-Kendall, z robusto) | Métodos simples, auditables y verificables a mano |
