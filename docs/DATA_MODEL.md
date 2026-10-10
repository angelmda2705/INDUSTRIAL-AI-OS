# Modelo de datos

Definido en `backend/app/models/` y versionado con Alembic (`backend/alembic/versions/`). PostgreSQL usa `JSONB` para
columnas JSON y `timestamptz` para fechas (todas en UTC).

## Diagrama

```
plans 1─* organizations 1─* memberships *─1 users 1─* auth_sessions
                 │                                 └─* password_reset_tokens
                 │ (organization_id en todas las tablas de cliente; RLS en PostgreSQL)
                 ├─* import_jobs ──────────────┐
                 ├─* datasets 1─* dataset_records (import_job_id → import_jobs)
                 │      ├─* analysis_runs 1─* kpi_values
                 │      └─* findings 1─* finding_events
                 ├─* kpi_targets
                 ├─* reports
                 ├─* org_counters
                 └─* audit_logs  (organization_id NULL = evento de plataforma)
```

## Tablas globales (sin RLS)

| Tabla | Propósito | Campos clave |
|---|---|---|
| `plans` | Plan comercial: límites y módulos | `code` único, `limits` (JSON), `modules` (JSON) |
| `organizations` | Empresa cliente | `slug` único, `plan_id`, `enabled_modules` (anula los del plan), `settings` (JSON: moneda, zona horaria, parámetros de análisis), `is_active` |
| `users` | Identidad global (solo correo y nombre) | `email` único, `password_hash` (bcrypt), `is_platform_admin`, `must_change_password`, `failed_login_count`, `locked_until` |
| `memberships` | Usuario ↔ organización con rol | único (`user_id`, `organization_id`), `role`, `is_active` |
| `auth_sessions` | Sesiones de servidor | `token_hash` (SHA-256) único, `csrf_hash`, `organization_id` activa, `expires_at`, `last_seen_at`, `revoked_at` |
| `password_reset_tokens` | Recuperación de acceso | `token_hash` único, `expires_at`, `used_at` |

## Tablas de cliente (con `organization_id` y RLS)

| Tabla | Propósito | Notas |
|---|---|---|
| `import_jobs` | Cada archivo cargado y su ciclo | `file_sha256`, `stored_filename` aleatorio, `status` (parsed → validated → committed → reverted), `column_mapping`, `parse_options`, `validation_summary` |
| `datasets` | Conjunto de registros de una plantilla | único (`organization_id`, `name`), `template_code`, `is_demo`, `row_count`, `analysis_stale` |
| `dataset_records` | Renglones validados | `data` (JSON normalizado por campo de plantilla), `source_row`, `import_job_id`, `fingerprint` (duplicados); índices por (`dataset_id`, `fingerprint`) e `import_job_id` |
| `analysis_runs` | Cada ejecución del motor | `trigger`, `status`, `record_count`, periodo, `data_profile`, `summary`, `error_message` |
| `kpi_values` | Valores calculados | `granularity` (total/month), `dimension`/`dimension_value`, `value` (NULL si datos insuficientes), `status`, `sample_size`, `inputs` (entradas de la fórmula), `message` |
| `kpi_targets` | Objetivos definidos por la organización | único (`organization_id`, `kpi_code`), `target_value`, `tolerance`, `owner_label` |
| `findings` | Hallazgos | `code` (HAL-000001), `fingerprint` único por organización, `area`, `category`, `nature`, `evidence` (JSON), `rule_code`, `method`, `priority`, `impact_amount` + `impact_kind` + `impact_basis`, `confidence` + `confidence_basis`, `status`, `owner_user_id`, `due_date`, `condition_active`, `is_demo` |
| `finding_events` | Historial de cada hallazgo | `event_type`, transición de estado, `note`, `actor_label` |
| `reports` | Reportes generados | `report_type`, `file_format`, `file_sha256`, `parameters` |
| `org_counters` | Secuencias por organización (códigos legibles) | se incrementa con bloqueo de fila |
| `audit_logs` | Auditoría (solo inserción) | `action`, `entity_type`/`entity_id`, `details`, `ip_address`, `request_id`; sin `RETURNING` para permitir eventos de plataforma bajo RLS |

## Plantillas de importación (estructura de `dataset_records.data`)

Definidas en `backend/app/services/imports/templates.py`; los campos obligatorios se marcan con *.

| Plantilla | Campos | Clave de duplicados |
|---|---|---|
| `production_records` | date*, work_center*, product, shift, order_ref, planned_qty, produced_qty*, scrap_qty, planned_time_min, run_time_min, downtime_min, std_time_per_unit_min | date, work_center, product, shift, order_ref |
| `maintenance_events` | asset_code*, event_type* (falla/correctivo/preventivo/inspeccion), event_start*, event_end, scheduled_date, cause, work_order_ref, labor_hours, parts_cost, labor_cost, other_cost | asset_code, event_type, event_start |
| `inventory_items` | sku*, description, category, unit, warehouse, on_hand_qty*, unit_cost, avg_daily_demand, demand_std_daily, lead_time_days, min_qty, max_qty, last_movement_date | sku, warehouse |
| `fuel_logs` | vehicle_code*, date*, odometer_km*, liters*, total_cost, driver_code, route, full_tank | vehicle_code, date, odometer_km |
| `generic` | columnas del archivo tal cual | renglón completo |

La clave usa solo los campos clave que el usuario mapeó. Los datos personales se limitan a códigos internos
(conductor, operador); no se requieren nombres.

## Archivos

`IIOS_STORAGE_DIR/org_<id>/imports/<uuid>.<ext>` y `…/reports/<uuid>.<ext>`. Los nombres originales nunca se usan
como rutas; cada lectura verifica que la ruta resuelta permanezca en el directorio de la organización.
