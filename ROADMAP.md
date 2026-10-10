# Hoja de ruta

| Fase | Alcance | Estado |
|---|---|---|
| 0 | Auditoría del entorno, arquitectura, modelo de datos, plan | ✅ Completa |
| 1 | Núcleo: autenticación, organizaciones, usuarios, roles, base de datos, navegación, panel, auditoría, configuración | ✅ Completa |
| 2 | Importación Excel/CSV, validación, mapeo, catálogo de indicadores, análisis inicial, hallazgos, reportes | ✅ Completa |
| 3 | Módulos operativos: inventarios (movimientos), mantenimiento (OT), costos, tareas, automatizaciones | ⏳ Siguiente |
| 4 | Motor de inteligencia: reglas configurables, diagnósticos, planes de acción, verificación de resultados | 🟡 Base lista (reglas, seguimiento y verificación por re-análisis) |
| 5 | IA: asistente, consultas autorizadas, agentes especializados con herramientas controladas | ⬜ Pendiente |
| 6 | Producción (programación), logística, calidad, seguridad industrial, gestión del trabajo | ⬜ Pendiente |
| 7 | Preparación comercial: facturación, monitoreo, pruebas de seguridad, manuales completos | 🟡 Parcial (multiempresa, planes, límites, respaldos) |

## Próxima fase (3) — orden propuesto

1. **Inventarios transaccionales.** Catálogo de productos, almacenes/ubicaciones, unidades; movimientos
   (entrada, salida, transferencia, ajuste autorizado) como libro mayor inmutable; existencias derivadas con bloqueo
   de fila (`SELECT … FOR UPDATE`) y prueba de movimientos concurrentes; conteos físicos y diferencias; propuestas de
   compra a partir del ROP ya implementado. Importación de existencias iniciales desde la plantilla actual.
2. **Mantenimiento.** Equipos/vehículos, planes preventivos y calendario, órdenes de trabajo con refacciones
   (salidas de inventario reales), mano de obra y costos; los KPI MTBF/MTTR ya implementados se alimentarán de las OT.
3. **Costos.** Conceptos, presupuestos, costos por orden/equipo/producto; estados de ahorro *potencial → estimado →
   aprobado → observado* con regla de que solo "observado" se mide contra datos posteriores.
4. **Tareas y automatizaciones.** Motor CUANDO/ENTONCES con permisos, idempotencia (clave de deduplicación),
   reintentos acotados, registro de ejecuciones y desactivación; primeras acciones: crear tarea desde hallazgo,
   recordatorio por vencimiento, notificación. Requiere planificador (APScheduler o cola) y canal de notificación.

## Fase 5 — criterios antes de empezar

* Capa de proveedor de IA abstracta con límites de uso por organización y registro de llamadas.
* Las herramientas del agente serán los mismos servicios del backend con `RequestContext` del usuario: el modelo
  nunca evita permisos ni RLS. Acciones con efecto (crear tarea, preparar solicitud) requerirán aprobación según el
  nivel de autonomía configurado (1: asistencia, 2: automatización autorizada, 3: coordinación).
* Requiere credenciales de un proveedor de modelos (no disponibles en esta sesión).

## Deuda técnica conocida

Ver [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).
