# Seguridad y privacidad

## Controles implementados

| Control | Implementación | Prueba |
|---|---|---|
| Contraseñas | bcrypt (12 rondas) sobre SHA-256 de la contraseña (evita el límite de 72 bytes); política de longitud, letras+números, lista de comunes, sin usuario de correo | `test_security_unit.py` |
| Comparación en tiempo similar | verificación ficticia cuando el usuario no existe | — |
| Sesiones | token aleatorio de 256 bits; en BD solo SHA-256; expiración por inactividad y absoluta; revocación en logout, cambio y recuperación de contraseña | `test_auth_api.py` |
| CSRF | double submit (cookie `iios_csrf` + cabecera `X-CSRF-Token`, comparada contra hash en la sesión) | `test_csrf_required…` |
| Bloqueo y límites | 5 intentos → 15 min de bloqueo; límites por IP y por correo en login, por usuario en la API, en recuperación de acceso | `test_lockout…`, `test_login_rate_limit` |
| Enumeración de cuentas | mismo mensaje para usuario inexistente y contraseña incorrecta; recuperación siempre responde igual | `test_wrong_password…` |
| Recuperación de acceso | enlace de un solo uso, 60 min, token en el fragmento de la URL (no llega a servidores ni logs), invalida tokens previos y sesiones | `test_password_reset_flow` |
| Autorización | matriz rol→permisos en el servidor; verificación de membresía activa en cada petición; solo un administrador otorga el rol de administrador; siempre queda un administrador | `test_tenancy_permissions.py` |
| Aislamiento multiempresa | filtro por organización en servicios + RLS forzada en PostgreSQL con rol sin privilegios; 404 para recursos ajenos | `TestRowLevelSecurity`, `test_other_org_resources_are_not_found` |
| Validación de entradas | Pydantic en todas las rutas; validación tipada de cada celda importada | — |
| Archivos | extensión + firma (xlsx = ZIP), sin `.xls`/`.xlsm`, límite de tamaño, límite de descompresión (zip bomb), nombres aleatorios, rutas verificadas dentro del directorio de la organización, descarga solo con permiso y de la propia organización | `test_import_parsing.py`, `test_upload_validation` |
| Inyección de fórmulas | celdas de texto que inician con `= + - @` se neutralizan en exportaciones Excel | `test_spreadsheet_formula_injection…` |
| SQL | consultas parametrizadas (SQLAlchemy); también en migraciones de datos | — |
| Errores | sin trazas al cliente; `request_id` para soporte | — |
| Registros | JSON con redacción de contraseñas, tokens, cookies y claves | `test_redaction…` |
| Auditoría | acciones relevantes registradas en la misma transacción; sin endpoints de edición o borrado | — |
| Cabeceras HTTP | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, CSP restrictiva en la API, HSTS en producción | — |
| Configuración segura | la API no inicia en producción con SQLite, cookie no segura o debug; documentación interactiva desactivada en producción | — |
| Secretos | solo por variables de entorno; `.env` excluido de git; contraseñas de CLI nunca como argumentos | — |

## Privacidad

* Usuarios: solo correo y nombre para mostrar.
* Plantillas: conductores y operadores se identifican con códigos internos; no se solicitan nombres ni datos
  personales. La plataforma no evalúa automáticamente el desempeño individual de trabajadores.
* Los administradores de plataforma no tienen acceso a los datos operativos de los clientes salvo que sean miembros.

## Pendiente / recomendaciones

* Límites de solicitudes en memoria del proceso: usar un almacén compartido (Redis) con varias réplicas.
* Verificación de contraseñas filtradas (k-anonimato) y autenticación de dos factores.
* Escaneo antivirus de archivos cargados si se aceptan archivos de terceros.
* Prueba de penetración externa antes de la comercialización.
* Cifrado de respaldos y del volumen de archivos en reposo (depende de la infraestructura).
* Política de retención configurable para auditoría, archivos e importaciones (hoy solo sesiones/tokens).

## Reporte de vulnerabilidades

Mientras no exista un canal formal, reporta vulnerabilidades de forma privada al responsable del repositorio; no
abras incidencias públicas con detalles explotables.
