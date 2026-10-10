# Manual de usuario

Este manual describe la versión 0.1. Las funciones que aún no existen se indican en [TASKS.md](../TASKS.md).

## 1. Acceso

* **Iniciar sesión:** usa el correo con el que tu administrador te registró. Tras 5 intentos fallidos la cuenta se
  bloquea 15 minutos.
* **Contraseña temporal:** si un administrador te dio de alta, deberás cambiarla al entrar. Requisitos: mínimo 10
  caracteres, letras y números, que no sea común ni contenga tu usuario de correo.
* **Olvidé mi contraseña:** en la pantalla de inicio, *¿Olvidaste tu contraseña?*. Recibirás un enlace válido por
  60 minutos y de un solo uso. Al restablecerla se cierran todas tus sesiones.
* **Varias empresas:** si perteneces a más de una organización, cámbiala con el selector de la barra superior.
* Las sesiones expiran tras 2 horas sin actividad o 24 horas en total.

## 2. Roles

| Rol | Puede |
|---|---|
| Administrador de empresa | Todo dentro de su organización, incluidos usuarios y configuración |
| Director | Consultar todo, definir objetivos, dar seguimiento a hallazgos, reportes, auditoría |
| Gerente | Importar y eliminar datos, analizar, objetivos, hallazgos, reportes, datos de demostración |
| Supervisor | Importar, analizar, dar seguimiento a hallazgos, reportes |
| Analista | Importar y eliminar datos, analizar, hallazgos, reportes, datos de demostración |
| Operador | Capturar/importar datos y consultar panel, indicadores y hallazgos |
| Auditor | Solo lectura, incluida la auditoría |

Si un botón no aparece, tu rol no tiene ese permiso. Aunque alguien intentara la acción por otro medio, el servidor
la rechaza.

## 3. Importar datos

*Datos → Importar datos.*

1. **Cargar archivo:** Excel `.xlsx` (sin macros) o CSV, hasta 20 MB. La primera fila no vacía debe tener los
   encabezados. Si el libro tiene varias hojas, elige la hoja en el siguiente paso.
2. **Revisar:** verás los primeros 20 renglones y el tipo detectado de cada columna. Si el mismo archivo ya se
   importó antes, aparecerá un aviso.
3. **Elegir plantilla:** *Registros de producción*, *Eventos de mantenimiento*, *Existencias de inventario*,
   *Cargas de combustible* o *Tabla genérica* (solo perfil de calidad).
4. **Relacionar columnas:** la plataforma sugiere columnas por nombre; revisa cada campo. Los marcados con * son
   obligatorios. Indica el separador decimal y el formato de fecha del archivo.
5. **Destino:** nuevo conjunto de datos (con nombre único) o agregar a uno existente de la misma plantilla.
6. **Validar:** se revisan **todos** los renglones. Verás cada error con su fila, columna, valor y cómo corregirlo,
   los duplicados (dentro del archivo o ya existentes) y los valores vacíos por campo.
7. **Confirmar:** decide si omitir renglones con error y duplicados. Nada se guarda antes de este paso. Al confirmar
   se ejecuta el análisis automáticamente.

**Revertir:** *Importaciones → (importación) → Revertir importación* elimina exactamente los registros que agregó y
vuelve a analizar el conjunto. El registro de la importación y su archivo se conservan para trazabilidad.

### Formatos aceptados

| Tipo | Ejemplos válidos |
|---|---|
| Número | `1234.5`, `1,234.50` (separador punto), `1.234,50` (separador coma), `$ 99`, `(12.5)` = −12.5 |
| Fecha | `2024-03-31`, `31/03/2024` (día/mes) o `03/31/2024` (mes/día), fechas nativas de Excel |
| Fecha y hora | `2024-03-31 14:30`, `31/03/2024 14:30` |
| Sí/No | `sí`, `si`, `s`, `x`, `true`, `1` / `no`, `n`, `false`, `0` |
| Vacío | celda vacía, `NA`, `N/A`, `null`, `-` |

## 4. Conjuntos de datos

Cada conjunto muestra: perfil de **calidad** (faltantes, rangos, atípicos), **registros** (con la fila y la
importación de origen), **historial de análisis** e **importaciones**. En inventarios, la pestaña *Análisis por
artículo* muestra clase ABC, stock de seguridad, punto de reorden, cobertura y cantidad sugerida (solo propuesta).

*Analizar ahora* recalcula indicadores y hallazgos; úsalo cuando el aviso indique que los datos u objetivos cambiaron.

## 5. Indicadores

*Análisis → Indicadores* muestra el catálogo: fórmula, unidad, requisitos mínimos, tratamiento de faltantes y
supuestos de cada indicador ([detalle](KPI_CATALOG.md)). Si un indicador dice **Datos insuficientes**, la razón
aparece debajo; la plataforma no inventa un valor.

**Objetivos:** *Definir objetivo* (requiere permiso) fija el valor meta y una tolerancia. No hay metas
predeterminadas: cada organización define las suyas. Al guardar, los conjuntos relacionados quedan marcados para un
nuevo análisis, que generará hallazgos de desviación.

El detalle de cada indicador muestra los valores de entrada exactos de la fórmula, la serie mensual, el desglose
(por línea, equipo, vehículo o categoría) y el historial de cálculos.

## 6. Hallazgos

Cada hallazgo indica:

* **Naturaleza:** *Problema confirmado en datos* (verificado con una regla determinista; no dice la causa),
  *Anomalía estadística* (valor inusual; puede ser error de captura) o *Hipótesis a investigar*.
* **Evidencia:** las filas exactas que lo respaldan, con su fila de origen.
* **Método:** la regla aplicada y sus umbrales ([reglas](FINDING_RULES.md)).
* **Impacto económico** con su **tipo**: *Sobrecosto estimado*, *Costo registrado asociado* o *Inventario expuesto o
  inmovilizado*. Los tipos no se suman y ninguno es un ahorro realizado.
* **Confianza** (solo métodos estadísticos), con su justificación.

**Seguimiento:** cambia el estado (*Abierto → En revisión → Acción planificada → Resuelto/Descartado*), asigna
responsable y fecha límite y agrega comentarios. Resolver o descartar exige una nota. Todo queda en el historial.

**Verificación:** si un análisis posterior ya no detecta la condición, el hallazgo indica *ya no detectado*. Si lo
marcaste como resuelto y la condición sigue en los datos, se **reabre** automáticamente.

## 7. Reportes

*Análisis → Reportes*: diagnóstico general, informe ejecutivo o reportes por área, en PDF o Excel. Incluyen
organización, periodo, fecha, fuentes (archivo y SHA-256), indicadores, hallazgos con evidencia y método,
limitaciones, montos por tipo y acciones pendientes con responsable.

## 8. Datos de demostración

En una organización sin datos, *Cargar datos de demostración* crea cuatro conjuntos sintéticos (producción,
mantenimiento, inventario y combustible). Todo lo derivado se marca **DEMO** y los reportes incluyen un aviso.
Elimínalos con *Eliminar datos de demostración* en el panel.

## 9. Administración

* **Usuarios:** agregar (con contraseña temporal), cambiar rol, desactivar (efecto inmediato). Solo un administrador
  puede otorgar el rol de administrador; siempre debe quedar al menos uno activo.
* **Organización:** moneda, zona horaria, formatos predeterminados y parámetros de análisis (nivel de servicio,
  umbrales ABC, días de obsolescencia, umbral de anomalías, tolerancia del preventivo).
* **Auditoría:** quién hizo qué y cuándo, con filtros por acción, usuario y fecha.
