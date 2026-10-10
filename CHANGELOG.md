# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico.

## [0.1.0] — 2026-10-10 · Primera versión funcional

### Agregado

- **Núcleo (Fase 1):** API FastAPI con sesiones de servidor (cookie httpOnly + CSRF, Bearer opcional), bloqueo por
  intentos, límites de solicitudes, recuperación de acceso, contraseñas temporales; organizaciones, membresías y
  7 roles con permisos verificados en servidor; planes con límites y módulos; administración de plataforma;
  auditoría transaccional; logs JSON con redacción de secretos; marca blanca.
- **Aislamiento multiempresa** en servicios y en PostgreSQL (row-level security forzada, rol sin privilegios).
- **Importación (Fase 2):** CSV/XLSX con vista previa, mapeo sugerido, validación tipada, duplicados, confirmación
  atómica resistente a concurrencia y reversión; 5 plantillas (producción, mantenimiento, inventario, combustible,
  genérica).
- **Análisis:** perfil de calidad, catálogo de 19 KPI documentados con objetivos por organización, series mensuales y
  desgloses; reglas de hallazgos (deterministas, Mann-Kendall, z robusto) con evidencia, naturaleza, prioridad,
  impacto tipificado y confianza; seguimiento, reapertura y verificación automática.
- **Interfaz web** (Next.js): panel ejecutivo, asistente de importación, conjuntos de datos, indicadores, hallazgos,
  reportes, auditoría, usuarios, organización, plataforma, páginas de acceso.
- **Reportes** PDF y Excel con fuentes (SHA-256), limitaciones y acciones pendientes; exportaciones protegidas contra
  inyección de fórmulas.
- **Datos de demostración** sintéticos, marcados y removibles.
- **Operación:** migraciones Alembic `0001`–`0002`, CLI administrativa, scripts de respaldo/restauración, script de
  rol de BD, Dockerfiles y docker-compose, CI de GitHub Actions, documentación generada desde el código.

### Corregido durante la sesión

- Los registros de auditoría de plataforma (sin organización) eran rechazados por RLS en PostgreSQL al usar
  `INSERT … RETURNING`; se desactivó `RETURNING` para esa tabla.
- La redacción de logs dejaba visible el token en `Authorization: Bearer <token>`.
- El panel y los reportes sumaban montos de naturaleza distinta (costos registrados, sobrecosto estimado y capital
  inmovilizado) en un solo "impacto estimado"; ahora se tipifican y no se suman (migración `0002`).

### Pruebas ejecutadas (resultados reales)

| Suite | Entorno | Resultado |
|---|---|---|
| `ruff check app tests alembic` | Python 3.13 | sin errores |
| `pytest` (backend) | SQLite | **97 aprobadas, 6 omitidas** (las 6 omitidas son exclusivas de PostgreSQL/RLS) |
| `pytest` (backend) | PostgreSQL 16.15, rol `NOSUPERUSER NOBYPASSRLS` | **103 aprobadas** |
| `eslint` + `tsc --noEmit` + `next build` | Node 22 | sin errores |
| Playwright E2E (login → demo → hallazgo → importación → reporte → logout) | Chromium, API sobre PostgreSQL | aprobada (3 ejecuciones consecutivas) |
| Respaldo y restauración (`scripts/backup.sh`/`restore.sh`) | PostgreSQL 16 | conteos idénticos, archivos idénticos (SHA-256), RLS preservada |
| CI de GitHub Actions (lint, `pytest` en SQLite y en PostgreSQL 16 con RLS, lint y build del frontend) | runners de GitHub (`ubuntu-latest`) | **4 ejecuciones exitosas**: 2 en la rama de trabajo, 1 en el PR #1 y 1 en `main` tras la integración |

### No verificado

- Construcción/ejecución de imágenes Docker (sin demonio Docker en el entorno).
- Envío real por SMTP.
