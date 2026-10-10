# Despliegue, respaldos y recuperación

## Topología recomendada (un servidor)

```
Internet ─▶ proxy TLS (Caddy/Nginx, HTTPS obligatorio) ─▶ web :3000 ─▶ api :8000 (red interna) ─▶ PostgreSQL 16
                                                                         └─▶ volumen de archivos
```

`docker-compose.yml` describe esta topología (PostgreSQL + API + web). **No se pudo construir ni ejecutar en el
entorno de desarrollo (sin demonio Docker)**: valídalo en un entorno de prueba antes de usarlo.

```bash
cp .env.example .env      # reemplaza TODOS los valores CHANGE_ME
docker compose up -d --build
docker compose exec api python -m app.cli create-org --name "Cliente" --admin-email ... --admin-name ...
```

## Lista de verificación de producción

- [ ] `IIOS_ENVIRONMENT=production` (la API se niega a iniciar con SQLite, cookie no segura o modo debug; la
      documentación interactiva `/api/v1/docs` se desactiva).
- [ ] HTTPS de extremo a extremo en el proxy; `IIOS_COOKIE_SECURE=true`.
- [ ] Rol de base de datos de la aplicación **sin** `SUPERUSER` ni `BYPASSRLS` (`scripts/db-init/01-app-role.sh`).
- [ ] `FORWARDED_ALLOW_IPS` = solo la dirección del proxy/web (si la API no está expuesta, ver compose).
- [ ] SMTP configurado (`IIOS_SMTP_*`) para recuperación de acceso; sin SMTP en producción la solicitud se registra
      como error y **no** se envía nada.
- [ ] `IIOS_ALLOW_SELF_SIGNUP=false` salvo que se quiera registro abierto.
- [ ] Respaldos automáticos programados y una restauración de prueba documentada.
- [ ] Un solo proceso de API **o** un almacén compartido para límites de solicitudes (ver KNOWN_LIMITATIONS).
- [ ] Rotación de logs y retención acordada; los logs no contienen contraseñas ni tokens (redacción automática).

## Migraciones

```bash
python -m app.cli migrate          # idempotente; el contenedor de la API lo ejecuta al iniciar
```

Reglas para nuevas migraciones:

1. Generarlas con `alembic revision --autogenerate` contra PostgreSQL y revisarlas a mano.
2. Toda tabla nueva de cliente debe tener `organization_id`, `TenantMixin` y su política RLS (agregarla a la
   migración y a la lista que verifica `tests/test_database.py`).
3. Las migraciones de **datos** sobre tablas con RLS deben levantar `FORCE ROW LEVEL SECURITY` dentro de la misma
   transacción y restablecerlo al final (ejemplo: `alembic/versions/0002_finding_impact_kind.py`).
4. Respaldar antes de migrar en producción; toda migración debe tener `downgrade`.

## Respaldos

Por diseño, el rol de la aplicación **no puede** leer los datos de todas las organizaciones, así que `pg_dump` con
ese rol falla. Usa un rol administrativo con `BYPASSRLS` (o superusuario) solo para respaldos:

```sql
CREATE ROLE iios_backup LOGIN PASSWORD '...' BYPASSRLS;
GRANT CONNECT ON DATABASE iios TO iios_backup;
GRANT USAGE ON SCHEMA public TO iios_backup;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO iios_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO iios_backup;
-- para tablas que creen migraciones futuras:
ALTER DEFAULT PRIVILEGES FOR ROLE iios_app IN SCHEMA public GRANT SELECT ON TABLES TO iios_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE iios_app IN SCHEMA public GRANT SELECT ON SEQUENCES TO iios_backup;
```

(Las cuatro primeras sentencias se verificaron en desarrollo: `pg_dump` con este rol completa el respaldo, mientras
que con el rol de la aplicación falla por RLS.)

```bash
IIOS_BACKUP_DATABASE_URL=postgresql://iios_backup:...@host:5432/iios \
IIOS_STORAGE_DIR=/var/lib/iios/storage \
scripts/backup.sh /ruta/respaldos
```

Genera `database.dump` (formato *custom*), `storage.tar.gz` (archivos importados y reportes) y `SHA256SUMS`.
Guarda los respaldos cifrados y fuera del servidor; contienen datos de todos los clientes.

## Restauración

1. Detén la API.
2. Crea una base vacía cuyo dueño sea el rol de la aplicación (que debe existir con el mismo nombre).
3. Ejecuta con un superusuario (o rol con `BYPASSRLS`, necesario para cargar tablas con RLS forzada):

```bash
IIOS_RESTORE_DATABASE_URL=postgresql://postgres:...@host:5432/iios_restaurada \
IIOS_STORAGE_DIR=/var/lib/iios/storage \
scripts/restore.sh /ruta/respaldos/20250101T000000Z
```

4. Verifica: `python -m app.cli migrate` (sin cambios pendientes), `GET /api/v1/system/health`, conteos de tablas.

**Verificado en desarrollo** (PostgreSQL 16): respaldo y restauración en una base nueva con conteos idénticos en
todas las tablas, archivos idénticos por SHA-256, dueño y `FORCE RLS` preservados, y el rol de aplicación sigue
viendo 0 filas sin organización y solo las de su organización con ella.

## Recuperación ante incidentes

| Escenario | Procedimiento |
|---|---|
| Importación incorrecta | Revertirla desde la interfaz (*Importaciones → Revertir*); queda auditado |
| Conjunto de datos dañado | Eliminarlo y reimportar los archivos originales (se conservan con su SHA-256) |
| Pérdida de base de datos | Restaurar el último respaldo; reimportar archivos posteriores |
| Credencial comprometida | Desactivar el usuario (efecto inmediato), restablecer contraseña (revoca todas sus sesiones) |
| Fuga de la base de datos | Las sesiones y tokens de recuperación están guardados como hash; aun así, revocar sesiones (`DELETE FROM auth_sessions`) y forzar cambio de contraseñas |
