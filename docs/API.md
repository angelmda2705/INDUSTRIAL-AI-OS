# API

* Base: `/api/v1`. Especificación OpenAPI: [`openapi.json`](openapi.json); listado: [API_ENDPOINTS.md](API_ENDPOINTS.md).
* Documentación interactiva en desarrollo: `http://127.0.0.1:8000/api/v1/docs` (desactivada en producción).

## Autenticación

**Navegador:** `POST /auth/login` con `{"email", "password"}` establece dos cookies:

| Cookie | Atributos | Uso |
|---|---|---|
| `iios_session` | httpOnly, SameSite=Lax, Secure (producción) | Sesión de servidor |
| `iios_csrf` | legible por JavaScript | Debe enviarse en la cabecera `X-CSRF-Token` en toda petición POST/PUT/PATCH/DELETE |

**Integraciones/scripts:** `POST /auth/login` con `"issue_bearer_token": true` devuelve `access_token`; envíalo como
`Authorization: Bearer <token>`. No requiere CSRF. Tiene la misma duración y revocación que una sesión.

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"tu@empresa.com","password":"...","issue_bearer_token":true}' | jq -r .access_token)
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/kpis/values
curl -s -H "Authorization: Bearer $TOKEN" -F file=@produccion.csv http://127.0.0.1:8000/api/v1/imports
```

## Autorización y aislamiento

* Cada ruta declara el permiso requerido (`require(Perm.X)`); sin permiso → `403 permission_denied` con
  `details.missing_permissions`.
* Todos los datos se limitan a la organización activa de la sesión. Un identificador de otra organización responde
  `404` (no `403`), para no confirmar su existencia.
* Módulo deshabilitado por plan → `403 module_disabled`; límite del plan → `402 plan_limit_exceeded`.
* Contraseña temporal pendiente → `403 password_change_required` (excepto `/auth/me`, `/auth/change-password`,
  `/auth/logout`).

## Errores

Formato uniforme, sin trazas internas:

```json
{"error": {"code": "validation_failed", "message": "Los datos enviados no son válidos.",
           "details": [{"field": "dataset_name", "message": "Mínimo 3 caracteres."}],
           "request_id": "6f0c…"}}
```

| HTTP | Códigos habituales |
|---|---|
| 401 | `not_authenticated`, `session_invalid`, `invalid_credentials`, `account_locked` |
| 403 | `permission_denied`, `csrf_failed`, `organization_required`, `module_disabled`, `password_change_required` |
| 404 | `not_found` |
| 409 | `conflict` (p. ej. importación ya confirmada) |
| 422 | `validation_failed`, `rows_with_errors`, `nothing_to_import`, `unsupported_file`, `invalid_reset_token` |
| 429 | `limit_exceeded` (`details.retry_after_seconds`) |
| 402 | `plan_limit_exceeded` |

Toda respuesta incluye la cabecera `X-Request-ID` (se puede enviar una propia de hasta 64 caracteres alfanuméricos).

## Paginación

Listados paginados responden `{"items": [...], "total": n, "page": p, "page_size": s}` con parámetros `page` y
`page_size`.

## Flujo de importación por API

1. `POST /imports` (multipart `file`) → `ImportJob` (`status: parsed`).
2. `GET /imports/{id}/preview[?sheet=]` → columnas, primeros renglones, `suggested_mappings` por plantilla.
3. `POST /imports/{id}/validate` con `template_code`, `mapping` (`campo → columna`), `dataset_name` **o**
   `dataset_id`, y opcionalmente `decimal_separator`, `date_format`, `sheet_name` → resumen de validación.
4. `POST /imports/{id}/commit` con `skip_invalid`, `skip_duplicates`, `run_analysis` → importación + análisis.
5. `POST /imports/{id}/revert` → elimina los registros de esa importación y vuelve a analizar.

Las plantillas y sus campos están en `GET /imports/templates`.
