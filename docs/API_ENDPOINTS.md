# Referencia de endpoints

> Documento generado desde la especificación OpenAPI (`docs/openapi.json`) con `python -m app.cli export-docs`.
> Convenciones (autenticación, CSRF, errores, paginación, aislamiento): ver [API.md](API.md).

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/system/health` | Estado del servicio y de la base de datos |
| GET | `/api/v1/system/branding` | Marca configurable (nombre, colores) |
| POST | `/api/v1/auth/login` | Iniciar sesión |
| POST | `/api/v1/auth/logout` | Cerrar sesión |
| GET | `/api/v1/auth/me` | Usuario y organización actuales |
| POST | `/api/v1/auth/switch-organization` | Cambiar de organización activa |
| POST | `/api/v1/auth/change-password` | Cambiar contraseña |
| POST | `/api/v1/auth/password-reset/request` | Solicitar recuperación de acceso |
| POST | `/api/v1/auth/password-reset/confirm` | Restablecer contraseña con enlace |
| POST | `/api/v1/auth/signup` | Registrar una organización (si está habilitado) |
| GET | `/api/v1/organization` | Datos y configuración de la organización activa |
| PATCH | `/api/v1/organization` | Actualizar nombre y parámetros de la organización |
| GET | `/api/v1/organization/roles` | Roles disponibles y sus permisos |
| GET | `/api/v1/organization/members` | Usuarios de la organización |
| POST | `/api/v1/organization/members` | Agregar usuario |
| PATCH | `/api/v1/organization/members/{membership_id}` | Cambiar rol o desactivar usuario |
| GET | `/api/v1/audit` | Registro de auditoría de la organización |
| GET | `/api/v1/platform/organizations` | Listar organizaciones (administrador de plataforma) |
| POST | `/api/v1/platform/organizations` | Crear organización con su administrador |
| GET | `/api/v1/platform/plans` | Planes comerciales |
| PATCH | `/api/v1/platform/organizations/{org_id}` | Cambiar plan, módulos o estado de una organización |
| GET | `/api/v1/imports/templates` | Plantillas de importación disponibles |
| GET | `/api/v1/imports` | Historial de importaciones |
| POST | `/api/v1/imports` | Cargar archivo CSV o Excel |
| GET | `/api/v1/imports/{job_id}` | Detalle de una importación |
| DELETE | `/api/v1/imports/{job_id}` | Descartar una importación no confirmada |
| GET | `/api/v1/imports/{job_id}/preview` | Columnas detectadas, vista previa y mapeo sugerido |
| POST | `/api/v1/imports/{job_id}/validate` | Mapear columnas y validar todos los renglones |
| POST | `/api/v1/imports/{job_id}/commit` | Confirmar la importación (y analizar) |
| POST | `/api/v1/imports/{job_id}/revert` | Revertir una importación confirmada |
| GET | `/api/v1/datasets` | Conjuntos de datos |
| GET | `/api/v1/datasets/{dataset_id}` | Conjunto de datos con su último perfil de calidad |
| DELETE | `/api/v1/datasets/{dataset_id}` | Eliminar conjunto de datos y sus resultados |
| GET | `/api/v1/datasets/{dataset_id}/records` | Registros (paginados) |
| GET | `/api/v1/datasets/{dataset_id}/runs` | Historial de análisis |
| POST | `/api/v1/datasets/{dataset_id}/analyze` | Ejecutar análisis |
| GET | `/api/v1/datasets/{dataset_id}/inventory-analysis` | Análisis por artículo (ABC, ROP, cobertura) |
| GET | `/api/v1/datasets/{dataset_id}/export` | Exportar registros a Excel |
| POST | `/api/v1/demo` | Cargar datos de demostración (identificados como DEMO) |
| DELETE | `/api/v1/demo` | Eliminar todos los datos de demostración |
| GET | `/api/v1/dashboard` | Panel ejecutivo |
| GET | `/api/v1/kpis/catalog` | Catálogo de indicadores con objetivos de la organización |
| GET | `/api/v1/kpis/values` | Valores más recientes de cada indicador por conjunto de datos |
| GET | `/api/v1/kpis/{kpi_code}` | Detalle de un indicador: desglose, serie mensual e historial |
| PUT | `/api/v1/kpis/{kpi_code}/target` | Definir objetivo del indicador |
| DELETE | `/api/v1/kpis/{kpi_code}/target` | Eliminar objetivo del indicador |
| GET | `/api/v1/findings` | Hallazgos |
| GET | `/api/v1/findings/export` | Exportar hallazgos a Excel |
| GET | `/api/v1/findings/{finding_id}` | Detalle del hallazgo con evidencia e historial |
| PATCH | `/api/v1/findings/{finding_id}` | Cambiar estado, responsable o fecha límite |
| POST | `/api/v1/findings/{finding_id}/comments` | Agregar comentario |
| GET | `/api/v1/reports/types` | Tipos de reporte disponibles |
| GET | `/api/v1/reports` | Reportes generados |
| POST | `/api/v1/reports` | Generar reporte PDF o Excel |
| GET | `/api/v1/reports/{report_id}/download` | Descargar reporte |
