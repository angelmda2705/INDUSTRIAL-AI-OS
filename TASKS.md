# Estado de tareas

Leyenda: ✅ implementado y probado · 🟡 parcial · ⬜ pendiente · ⚠️ implementado pero **no verificado** en este entorno

## Núcleo de la plataforma (Fase 1)

| Funcionalidad | Estado | Evidencia / nota |
|---|---|---|
| Inicio/cierre de sesión, sesiones de servidor, expiración por inactividad y absoluta | ✅ | `tests/test_auth_api.py`, E2E |
| CSRF (double submit) y token Bearer para integraciones | ✅ | `test_csrf_required…`, `test_bearer_token…` |
| Bloqueo por intentos fallidos, límite de solicitudes por IP/correo/usuario | ✅ | `test_lockout…`, `test_login_rate_limit` |
| Recuperación de contraseña por enlace de un solo uso | ✅ (flujo) / ⚠️ (envío SMTP) | Probado con buzón de desarrollo; SMTP real no probado |
| Contraseñas temporales con cambio obligatorio | ✅ | `test_temporary_password_must_be_changed` |
| Organizaciones, membresías, cambio de organización activa | ✅ | `test_multi_org_user_switches_organization` |
| Roles (7) y permisos verificados en servidor | ✅ | `tests/test_tenancy_permissions.py` |
| Aislamiento multiempresa en servicios | ✅ | 404 para recursos ajenos, listados filtrados |
| Aislamiento en base de datos (RLS forzada, PostgreSQL) | ✅ | `TestRowLevelSecurity` (6 pruebas) |
| Planes, límites de usuarios/importaciones/renglones, módulos habilitables | ✅ | `test_plan_user_limit`, `test_disabled_module…` |
| Administración de plataforma (organizaciones, planes, suspensión) | 🟡 | API + pantalla; sin pruebas E2E de esta pantalla |
| Registro de auditoría | ✅ | Escrito en la misma transacción; vista con filtros |
| Registro de solicitudes con `request_id`, redacción de secretos | ✅ | `test_redaction_of_secrets_in_logs` |
| Marca blanca (nombre, color, logotipo por configuración) | ✅ | Variables `IIOS_BRAND_*` / `NEXT_PUBLIC_BRAND_*` |
| Registro autoservicio de organizaciones (opcional, desactivado por defecto) | ✅ | `test_signup_creates_isolated_org` |
| Política de retención configurable | 🟡 | Solo depuración de sesiones/tokens (`cli cleanup-sessions`) |

## Importación y análisis (Fase 2)

| Funcionalidad | Estado | Evidencia / nota |
|---|---|---|
| Carga CSV (UTF-8/Windows-1252, delimitador automático) y XLSX (hojas, límite de descompresión) | ✅ | `tests/test_import_parsing.py` |
| Vista previa, tipos detectados, mapeo sugerido por sinónimos | ✅ | `test_full_import_workflow`, E2E |
| Validación tipada por renglón con mensajes de corrección | ✅ | decimales con separador configurable, fechas día/mes o mes/día, enumeraciones, booleanos |
| Duplicados en archivo y contra el conjunto destino | ✅ | huella de campos clave |
| Confirmación atómica y segura ante concurrencia | ✅ | `test_concurrent_commits_import_rows_only_once` |
| Reversión de importaciones | ✅ | `test_revert_removes_exactly_the_imported_rows` |
| Plantillas: producción, mantenimiento, inventario, combustible, genérica | ✅ | |
| Conexión directa a bases de datos externas | ⬜ | Solo archivos por ahora |
| Perfil de calidad de datos | ✅ | |
| Catálogo de 19 KPI con fórmula/supuestos/requisitos | ✅ | `tests/test_kpis_calculations.py` (valores calculados a mano) |
| Objetivos por organización, evaluación y desviaciones | ✅ | `test_target_deviation_requires_configured_target` |
| Series mensuales, desglose por dimensión, historial | ✅ | `test_kpi_detail_series_and_history` |
| Detección de tendencias (Mann-Kendall) y atípicos (z robusto) | ✅ | |
| Hallazgos con evidencia, método, naturaleza, prioridad, impacto tipificado, confianza | ✅ | `tests/test_findings_engine.py` |
| Seguimiento de hallazgos (estados, responsable, fecha, comentarios, historial) | ✅ | |
| Verificación automática (condición ya no detectada / reapertura) | ✅ | |
| Panel ejecutivo con filtros y estados vacíos | ✅ | E2E + captura |
| Reportes PDF/Excel (diagnóstico, ejecutivo, por área) con fuentes y limitaciones | ✅ | `tests/test_reports_demo.py` |
| Exportaciones Excel (registros, hallazgos) con protección contra inyección de fórmulas | ✅ | |
| Datos de demostración identificados y removibles | ✅ | |
| Reportes de calidad, seguridad y costos | ⬜ | Requieren módulos de Fase 3/6 |

## Infraestructura

| Funcionalidad | Estado | Nota |
|---|---|---|
| Migraciones versionadas (Alembic) | ✅ | `0001`, `0002`; verificadas en SQLite y PostgreSQL |
| Respaldo y restauración | ✅ | `scripts/backup.sh` / `restore.sh` verificados contra PostgreSQL 16 |
| Docker / docker-compose | ⚠️ | Escritos, **no construidos** (sin demonio Docker en el entorno) |
| CI (GitHub Actions) | ⚠️ | Escrito, no ejecutado aún en GitHub |
| Monitoreo | 🟡 | `/api/v1/system/health` y logs JSON; sin métricas ni alertas |

## Pendiente (fases siguientes)

- ⬜ Inventarios transaccionales, almacenes, movimientos, conteos físicos, propuestas de compra (Fase 3)
- ⬜ Mantenimiento con equipos, planes y órdenes de trabajo (Fase 3)
- ⬜ Costos, presupuestos y estados de ahorro (Fase 3)
- ⬜ Gestión de tareas y motor de automatizaciones con reintentos e idempotencia (Fase 3)
- ⬜ Capa de IA, asistente y agentes (Fase 5)
- ⬜ Producción (programación), logística, calidad, seguridad industrial, personal (Fase 6)
- ⬜ Integraciones externas (ERP, GPS, n8n) — solo se documentarán como interfaces hasta tener credenciales
- ⬜ Facturación
