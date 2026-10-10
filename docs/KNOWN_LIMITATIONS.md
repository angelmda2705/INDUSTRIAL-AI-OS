# Limitaciones conocidas (v0.1)

## No verificado en el entorno de desarrollo

| Elemento | Situación |
|---|---|
| Imágenes Docker y `docker-compose.yml` | Escritos pero **no construidos ni ejecutados**: el entorno no tenía demonio Docker. Se verificaron por separado el script de inicialización del rol de BD y las migraciones con ese rol. |
| Envío de correo (SMTP) | Implementado con `smtplib` y STARTTLS, **no probado** contra un servidor real. En desarrollo/pruebas el mensaje se captura localmente. |
| GitHub Actions | Flujo escrito; se ejecutará al primer push que lo active. |
| Navegadores distintos de Chromium y tabletas físicas | La interfaz es adaptable, pero la prueba E2E solo corre en Chromium de escritorio. |

## Limitaciones funcionales

* **Solo archivos.** No hay conexiones directas a bases de datos, ERP, GPS ni telemetría; cualquier integración
  futura requerirá credenciales y una interfaz específica.
* **Registros como JSON por plantilla.** Adecuado para diagnóstico; los módulos operativos (inventarios con
  movimientos, órdenes de trabajo) de la Fase 3 usarán tablas propias con integridad referencial.
* **Análisis síncrono.** Se ejecuta dentro de la petición. Con el límite de 200 000 renglones por importación es
  viable, pero conjuntos grandes pueden tardar decenas de segundos; falta mover el análisis a tareas en segundo plano.
* **Periodo de análisis.** Cada análisis cubre todo el conjunto (con desglose mensual); no hay selección de periodo
  arbitrario en el panel.
* **MTBF en tiempo calendario.** Sobrestima el tiempo de operación de equipos que no trabajan 24/7 (documentado en el
  catálogo). Se corregirá cuando existan horas de operación por equipo.
* **Puntualidad del preventivo** solo evalúa preventivos ejecutados; los no realizados no existen en la plantilla.
* **Rendimiento de combustible** asume cargas a tanque lleno cuando no se indica lo contrario.
* **Stock de seguridad** solo modela variabilidad de la demanda (no del tiempo de reposición).
* **Pruebas de tendencia** (Mann-Kendall) no corrigen autocorrelación.
* **Ahorros.** No existe todavía el ciclo potencial → estimado → aprobado → observado (módulo de costos, Fase 3); los
  montos actuales están tipificados y nunca se presentan como ahorro.
* **Sin automatizaciones, tareas, IA ni agentes** (Fases 3–5).

## Limitaciones técnicas

* Límites de solicitudes en memoria del proceso: con varias réplicas de la API no se comparten.
* Archivos en disco local: con varias réplicas se requiere almacenamiento compartido u objeto (S3 o similar).
* Respaldos y restauraciones requieren un rol con `BYPASSRLS` (consecuencia deliberada de forzar RLS).
* Los eventos de auditoría de plataforma (p. ej. intento de acceso con correo inexistente) no son visibles para
  ninguna organización y solo pueden consultarse con un rol administrativo de base de datos.
* Retención configurable solo para sesiones y tokens.
* Sin métricas/alertas (Prometheus, etc.); solo verificación de salud y logs estructurados.
* Fechas y horas importadas se guardan sin zona horaria y se interpretan en la zona de la organización.
