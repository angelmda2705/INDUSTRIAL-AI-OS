# Industrial Intelligence OS

Plataforma de inteligencia operativa para ingeniería industrial: importa datos de la operación (Excel/CSV),
valida su calidad, calcula indicadores documentados, detecta problemas con reglas verificables y da seguimiento
a cada hallazgo con evidencia y trazabilidad. *(Nombre provisional; la marca se cambia por configuración.)*

**Estado: v0.1 — primera versión funcional (Fases 0, 1 y 2 completas).** Ver [TASKS.md](TASKS.md) para el
detalle de lo implementado, parcial, pendiente y no verificado.

```
DATOS → ANÁLISIS → DETECCIÓN → DIAGNÓSTICO → SEGUIMIENTO   (implementado)
PLAN DE ACCIÓN → EJECUCIÓN AUTORIZADA → MEDICIÓN            (fases 3–5, pendiente)
```

## Qué hace hoy

| Área | Funcionalidad |
|---|---|
| Acceso | Inicio de sesión con sesiones de servidor (cookie httpOnly + CSRF), bloqueo por intentos, límites de solicitudes, recuperación de contraseña por enlace de un solo uso, contraseñas temporales, cambio de organización |
| Multiempresa | Datos aislados por organización en el servicio **y** en PostgreSQL (row-level security forzada), planes con límites y módulos habilitables, administración de plataforma |
| Permisos | 7 roles de organización (administrador, director, gerente, supervisor, analista, operador, auditor) verificados en el servidor en cada operación |
| Importación | CSV y Excel: detección de columnas, vista previa, mapeo sugerido, validación tipada por renglón, duplicados, confirmación atómica y reversión |
| Calidad de datos | Perfil por campo: faltantes, distintos, rangos, atípicos (IQR), completitud |
| Indicadores | 19 KPI documentados (producción, mantenimiento, inventarios, combustible) con fórmula, supuestos, requisitos mínimos, desglose e historial; objetivos configurables |
| Hallazgos | Reglas deterministas y estadísticas con evidencia, método, prioridad, impacto económico **tipificado** y confianza; distinguen *problema confirmado*, *anomalía estadística* e *hipótesis*; flujo de seguimiento y verificación automática |
| Panel y reportes | Panel ejecutivo con filtros; reportes PDF y Excel con fuentes (SHA-256), limitaciones y acciones pendientes |
| Auditoría | Registro de acciones relevantes en la misma transacción que la acción |
| Demostración | Datos sintéticos marcados como **DEMO** en todas las pantallas y reportes; se eliminan con un clic |

## Inicio rápido (desarrollo)

Requisitos: Python 3.12+, Node.js 22+. PostgreSQL 16 es opcional en desarrollo (SQLite por defecto).

```bash
scripts/dev.sh                     # instala dependencias, migra y levanta API (:8000) y web (:3000)
# en otra terminal, la primera vez:
cd backend && .venv/bin/python -m app.cli create-org \
  --name "Mi Empresa" --admin-email tu@empresa.com --admin-name "Tu Nombre"   # pide la contraseña
```

Abre http://127.0.0.1:3000, inicia sesión y elige **Importar datos** o **Cargar datos de demostración**.
Instalación detallada, PostgreSQL y producción: [docs/INSTALL.md](docs/INSTALL.md) y [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Verificación

```bash
cd backend
.venv/bin/ruff check app tests alembic
.venv/bin/pytest -q                                   # SQLite
IIOS_TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@host:5432/iios_test .venv/bin/pytest -q   # PostgreSQL + RLS (rol NO superusuario)

cd ../frontend
npm run lint && npm run build
E2E_EMAIL=tu@empresa.com E2E_PASSWORD=... npm run e2e   # con API y web en ejecución
```

Resultados de la última ejecución registrados en [CHANGELOG.md](CHANGELOG.md).

## Documentación

| Documento | Contenido |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Arquitectura, decisiones y flujo de datos |
| [ROADMAP.md](ROADMAP.md) | Fases y próximos pasos |
| [TASKS.md](TASKS.md) | Estado de cada funcionalidad (implementada / parcial / pendiente / no verificada) |
| [CHANGELOG.md](CHANGELOG.md) | Cambios por versión y resultados de pruebas |
| [docs/INSTALL.md](docs/INSTALL.md) | Instalación local |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Despliegue, respaldos y recuperación |
| [docs/USER_MANUAL.md](docs/USER_MANUAL.md) | Manual de usuario |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Modelo de datos |
| [docs/API.md](docs/API.md) · [docs/API_ENDPOINTS.md](docs/API_ENDPOINTS.md) | Convenciones y referencia de la API |
| [docs/KPI_CATALOG.md](docs/KPI_CATALOG.md) · [docs/FINDING_RULES.md](docs/FINDING_RULES.md) | Indicadores y reglas de hallazgos |
| [docs/SECURITY.md](docs/SECURITY.md) | Controles de seguridad y privacidad |
| [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) | Limitaciones conocidas |
| [.env.example](.env.example) | Variables de entorno |

## Estructura

```
backend/    FastAPI · SQLAlchemy · Alembic · pandas   (app/, alembic/, tests/)
frontend/   Next.js · React · TypeScript · Tailwind   (src/app, src/components, src/lib, e2e/)
scripts/    dev.sh · backup.sh · restore.sh · db-init/
docs/       documentación técnica y de usuario
```
