# Instalación local

## Requisitos

| Componente | Versión probada |
|---|---|
| Python | 3.13 (mínimo 3.12) |
| Node.js / npm | 22 / 10 |
| PostgreSQL | 16 (opcional en desarrollo; obligatorio en producción) |

## Opción rápida

```bash
scripts/dev.sh
```

Crea `backend/.venv`, instala dependencias, aplica migraciones sobre SQLite (`backend/data/iios.db`), instala
dependencias web y levanta API (http://127.0.0.1:8000/api/v1/docs) y web (http://127.0.0.1:3000).

Crea la primera organización (la contraseña se solicita de forma interactiva o se toma de `IIOS_BOOTSTRAP_PASSWORD`;
nunca como argumento):

```bash
cd backend
.venv/bin/python -m app.cli create-org --name "Mi Empresa" --admin-email tu@empresa.com --admin-name "Tu Nombre"
```

## Paso a paso

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
export IIOS_ENVIRONMENT=development IIOS_COOKIE_SECURE=false   # HTTP local
.venv/bin/python -m app.cli migrate
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm ci
IIOS_BACKEND_URL=http://127.0.0.1:8000 npm run dev         # o: npm run build && npm start
```

### PostgreSQL local (recomendado para probar el aislamiento en base de datos)

El rol de la aplicación **no** debe ser superusuario ni tener `BYPASSRLS`; de lo contrario PostgreSQL omite las
políticas de seguridad por fila.

```sql
CREATE ROLE iios LOGIN PASSWORD 'cambia-esta-clave' NOSUPERUSER NOBYPASSRLS NOCREATEROLE;
CREATE DATABASE iios_dev OWNER iios;
CREATE DATABASE iios_test OWNER iios;   -- para pruebas
```

```bash
export IIOS_DATABASE_URL=postgresql+psycopg://iios:cambia-esta-clave@127.0.0.1:5432/iios_dev
.venv/bin/python -m app.cli migrate
```

## Pruebas

```bash
cd backend
.venv/bin/ruff check app tests alembic
.venv/bin/pytest -q
IIOS_TEST_DATABASE_URL=postgresql+psycopg://iios:cambia-esta-clave@127.0.0.1:5432/iios_test .venv/bin/pytest -q
```

La suite en PostgreSQL elimina y recrea el esquema `public` de la base de pruebas: no la apuntes a datos reales.

Prueba de extremo a extremo (requiere API y web en ejecución y un administrador existente; usa Chromium de
Playwright 1.56):

```bash
cd frontend
E2E_EMAIL=tu@empresa.com E2E_PASSWORD='...' npm run e2e
```

## Comandos administrativos

| Comando | Uso |
|---|---|
| `python -m app.cli migrate` | Aplica migraciones pendientes |
| `python -m app.cli create-org --name … --admin-email … --admin-name … [--plan starter\|professional\|enterprise]` | Crea organización y administrador |
| `python -m app.cli create-platform-admin --email … --name …` | Crea o promueve administrador de plataforma |
| `python -m app.cli cleanup-sessions` | Depura sesiones y tokens vencidos hace más de 30 días |
| `python -m app.cli export-docs` | Regenera `docs/KPI_CATALOG.md`, `docs/API_ENDPOINTS.md` y `docs/openapi.json` |

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| El inicio de sesión funciona pero las páginas regresan a `/login` | La cookie es `Secure` y estás en HTTP: usa `IIOS_COOKIE_SECURE=false` solo en desarrollo local |
| "Solicitud rechazada por protección CSRF" | La página se abrió con otra sesión; recarga o vuelve a iniciar sesión |
| La API no inicia en producción | `check_production_settings` exige PostgreSQL, cookie segura y `IIOS_DEBUG=false` |
| `pg_dump` falla con "row-level security" | Usa un rol con `BYPASSRLS` para respaldos (ver DEPLOYMENT.md) |
