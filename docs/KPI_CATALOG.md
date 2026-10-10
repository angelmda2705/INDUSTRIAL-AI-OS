# Catálogo de indicadores

> Documento generado desde `backend/app/services/analytics/kpis.py` con `python -m app.cli export-docs`. No editar a mano.

Reglas generales:

- Si no se cumplen los requisitos mínimos, el indicador se reporta como **datos insuficientes** y no se muestra ningún valor.
- El tamaño de muestra y los valores de entrada (numerador/denominador) se guardan con cada cálculo para que sea reproducible.
- Los objetivos los define cada organización; la plataforma no asume estándares universales.
- Cada análisis calcula el valor total del conjunto de datos, el desglose por la dimensión indicada y, cuando aplica, la serie mensual.

## Producción

### Cumplimiento de producción (`production_compliance`)

Proporción de la cantidad planeada que se produjo en buen estado.

| Atributo | Valor |
|---|---|
| Fórmula | Σ cantidad buena producida ÷ Σ cantidad planeada × 100 |
| Unidad | % |
| Frecuencia | mensual |
| Fuente | Plantilla `production_records` (Registros de producción) |
| Campos | `produced_qty`, `planned_qty` |
| Requisitos mínimos | Al menos un registro con cantidad planeada > 0. |
| Valores faltantes | Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron. |
| Interpretación | Mayor es mejor |
| Desglose | work_center · serie mensual |

Supuestos:

- La cantidad producida corresponde a unidades conformes.
- Puede superar 100 % si se produce más de lo planeado.

### Porcentaje de desperdicio (`scrap_rate`)

Unidades rechazadas sobre el total de unidades procesadas.

| Atributo | Valor |
|---|---|
| Fórmula | Σ desperdicio ÷ (Σ producidas buenas + Σ desperdicio) × 100 |
| Unidad | % |
| Frecuencia | mensual |
| Fuente | Plantilla `production_records` (Registros de producción) |
| Campos | `scrap_qty`, `produced_qty` |
| Requisitos mínimos | Columna de desperdicio con al menos un valor. |
| Valores faltantes | Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron. |
| Interpretación | Menor es mejor |
| Desglose | work_center · serie mensual |

Supuestos:

- Las unidades de desperdicio y buenas se miden en la misma unidad.

### Utilización de capacidad (`capacity_utilization`)

Tiempo efectivamente produciendo respecto del tiempo programado.

| Atributo | Valor |
|---|---|
| Fórmula | Σ tiempo de operación ÷ Σ tiempo programado × 100 |
| Unidad | % |
| Frecuencia | mensual |
| Fuente | Plantilla `production_records` (Registros de producción) |
| Campos | `run_time_min`, `planned_time_min` |
| Requisitos mínimos | Registros con tiempo programado > 0. |
| Valores faltantes | Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron. |
| Interpretación | Mayor es mejor |
| Desglose | work_center · serie mensual |

Supuestos:

- El tiempo programado excluye paros planeados (comidas, mantenimiento programado).

### Tiempo muerto (`downtime_rate`)

Paros no planeados como proporción del tiempo programado.

| Atributo | Valor |
|---|---|
| Fórmula | Σ tiempo muerto ÷ Σ tiempo programado × 100 |
| Unidad | % |
| Frecuencia | mensual |
| Fuente | Plantilla `production_records` (Registros de producción) |
| Campos | `downtime_min`, `planned_time_min` |
| Requisitos mínimos | Registros con tiempo programado > 0. |
| Valores faltantes | Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron. |
| Interpretación | Menor es mejor |
| Desglose | work_center · serie mensual |

Supuestos:

- El tiempo muerto registrado corresponde a paros no planeados.

### Productividad (unidades por hora) (`productivity_units_per_hour`)

Unidades buenas por hora de operación.

| Atributo | Valor |
|---|---|
| Fórmula | Σ cantidad buena ÷ (Σ tiempo de operación ÷ 60) |
| Unidad | u/h |
| Frecuencia | mensual |
| Fuente | Plantilla `production_records` (Registros de producción) |
| Campos | `produced_qty`, `run_time_min` |
| Requisitos mínimos | Registros con tiempo de operación > 0. |
| Valores faltantes | Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron. |
| Interpretación | Mayor es mejor |
| Desglose | work_center · serie mensual |

Supuestos:

- Solo es comparable entre centros o periodos con mezcla de productos similar.

### Eficiencia de desempeño (`performance_efficiency`)

Minutos estándar ganados respecto del tiempo de operación.

| Atributo | Valor |
|---|---|
| Fórmula | Σ ((buenas + desperdicio) × tiempo estándar por unidad) ÷ Σ tiempo de operación × 100 |
| Unidad | % |
| Frecuencia | mensual |
| Fuente | Plantilla `production_records` (Registros de producción) |
| Campos | `produced_qty`, `run_time_min`, `std_time_per_unit_min` |
| Requisitos mínimos | Tiempo estándar por unidad informado. |
| Valores faltantes | Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron. |
| Interpretación | Mayor es mejor |
| Desglose | work_center · serie mensual |

Supuestos:

- Los tiempos estándar están vigentes y medidos correctamente.

## Mantenimiento

### MTTR — tiempo medio de reparación (`mttr_hours`)

Tiempo promedio desde la falla hasta que el equipo vuelve a estar disponible.

| Atributo | Valor |
|---|---|
| Fórmula | Σ (fin − inicio) de fallas ÷ número de fallas con fin registrado |
| Unidad | h |
| Frecuencia | mensual |
| Fuente | Plantilla `maintenance_events` (Eventos de mantenimiento) |
| Campos | `event_type`, `event_start`, `event_end` |
| Requisitos mínimos | Al menos 3 fallas con fecha de fin. |
| Valores faltantes | Las fallas sin fecha de fin se excluyen y se reportan como problema de calidad de datos. |
| Interpretación | Menor es mejor |
| Desglose | asset_code · serie mensual |

Supuestos:

- Incluye tiempo de espera de refacciones y personal (tiempo total fuera de servicio).

### MTBF — tiempo medio entre fallas (`mtbf_hours`)

Tiempo promedio en servicio entre una reparación y la siguiente falla del mismo equipo.

| Atributo | Valor |
|---|---|
| Fórmula | Σ (inicio falla i+1 − fin falla i) ÷ número de intervalos, por equipo |
| Unidad | h |
| Frecuencia | mensual |
| Fuente | Plantilla `maintenance_events` (Eventos de mantenimiento) |
| Campos | `asset_code`, `event_type`, `event_start`, `event_end` |
| Requisitos mínimos | Al menos 3 intervalos entre fallas consecutivas. |
| Valores faltantes | Intervalos cuyo evento previo no tiene fecha de fin, o que se traslapan, se excluyen. |
| Interpretación | Mayor es mejor |
| Desglose | asset_code · serie mensual |

Supuestos:

- Usa tiempo calendario: asume que el equipo está disponible entre fallas. Para equipos que no operan 24/7 sobreestima el tiempo de operación.
- En el desglose mensual cada intervalo se asigna al mes de la falla que lo cierra.

### Disponibilidad inherente (`availability_inherent`)

Proporción del tiempo en que el equipo está disponible considerando solo fallas y reparaciones.

| Atributo | Valor |
|---|---|
| Fórmula | MTBF ÷ (MTBF + MTTR) × 100 |
| Unidad | % |
| Frecuencia | mensual |
| Fuente | Plantilla `maintenance_events` (Eventos de mantenimiento) |
| Campos | `asset_code`, `event_type`, `event_start`, `event_end` |
| Requisitos mínimos | MTBF y MTTR calculables. |
| Valores faltantes | Hereda las exclusiones de MTBF y MTTR. |
| Interpretación | Mayor es mejor |
| Desglose | asset_code · serie mensual |

Supuestos:

- No incluye paros por mantenimiento preventivo ni falta de material (no es disponibilidad operativa).

### Costo de mantenimiento (`maintenance_cost_total`)

Suma de refacciones, mano de obra y otros costos de los eventos.

| Atributo | Valor |
|---|---|
| Fórmula | Σ (refacciones + mano de obra + otros) |
| Unidad | moneda |
| Frecuencia | mensual |
| Fuente | Plantilla `maintenance_events` (Eventos de mantenimiento) |
| Campos | `parts_cost`, `labor_cost`, `other_cost` |
| Requisitos mínimos | Al menos un evento con costo. |
| Valores faltantes | Los componentes de costo vacíos se consideran no informados (no cero) y el evento solo suma lo informado. |
| Interpretación | Menor es mejor |
| Desglose | asset_code · serie mensual |

Supuestos:

- Los costos están expresados en la moneda configurada para la organización.

### Número de fallas (`failure_count`)

Cantidad de eventos registrados como falla.

| Atributo | Valor |
|---|---|
| Fórmula | Conteo de eventos con tipo = falla |
| Unidad | eventos |
| Frecuencia | mensual |
| Fuente | Plantilla `maintenance_events` (Eventos de mantenimiento) |
| Campos | `event_type` |
| Requisitos mínimos | Ninguno. |
| Valores faltantes | No aplica. |
| Interpretación | Menor es mejor |
| Desglose | asset_code · serie mensual |

Supuestos:

- Depende de que todas las fallas se registren.

### Puntualidad del mantenimiento preventivo (`preventive_on_time`)

Preventivos ejecutados a más tardar en su fecha programada (más la tolerancia configurada).

| Atributo | Valor |
|---|---|
| Fórmula | Preventivos con inicio ≤ fecha programada + tolerancia ÷ preventivos con fecha programada × 100 |
| Unidad | % |
| Frecuencia | mensual |
| Fuente | Plantilla `maintenance_events` (Eventos de mantenimiento) |
| Campos | `event_type`, `event_start`, `scheduled_date` |
| Requisitos mínimos | Preventivos con fecha programada. |
| Valores faltantes | Preventivos sin fecha programada se excluyen. |
| Interpretación | Mayor es mejor |
| Desglose | asset_code · serie mensual |

Supuestos:

- Solo evalúa preventivos ejecutados; los programados no realizados no están en este conjunto de datos.

## Inventarios

### Valor del inventario (`inventory_value`)

Valor de las existencias a costo unitario.

| Atributo | Valor |
|---|---|
| Fórmula | Σ max(existencia, 0) × costo unitario |
| Unidad | moneda |
| Frecuencia | por corte |
| Fuente | Plantilla `inventory_items` (Existencias de inventario) |
| Campos | `on_hand_qty`, `unit_cost` |
| Requisitos mínimos | Costo unitario informado. |
| Valores faltantes | Artículos sin costo no se valoran y se cuentan aparte. |
| Interpretación | Informativo (sin objetivo) |
| Desglose | category · por corte (sin serie mensual) |

Supuestos:

- Existencias negativas se valoran en cero (son un error de registro).

### Artículos en o bajo punto de reorden (`items_below_reorder_point_pct`)

Proporción de artículos activos cuya existencia es menor o igual a su punto de reorden.

| Atributo | Valor |
|---|---|
| Fórmula | Artículos con existencia ≤ ROP ÷ artículos con demanda y tiempo de reposición × 100; ROP = d·L + z·σ·√L |
| Unidad | % |
| Frecuencia | por corte |
| Fuente | Plantilla `inventory_items` (Existencias de inventario) |
| Campos | `on_hand_qty`, `avg_daily_demand`, `lead_time_days` |
| Requisitos mínimos | Demanda diaria y tiempo de reposición. |
| Valores faltantes | Artículos sin demanda o sin tiempo de reposición no se evalúan. |
| Interpretación | Menor es mejor |
| Desglose | category · por corte (sin serie mensual) |

Supuestos:

- Demanda aproximadamente normal y estable.
- No modela variabilidad del tiempo de reposición.

### Tasa de faltantes (`stockout_items_pct`)

Proporción de artículos con demanda que tienen existencia cero o negativa.

| Atributo | Valor |
|---|---|
| Fórmula | Artículos con demanda > 0 y existencia ≤ 0 ÷ artículos con demanda > 0 × 100 |
| Unidad | % |
| Frecuencia | por corte |
| Fuente | Plantilla `inventory_items` (Existencias de inventario) |
| Campos | `on_hand_qty`, `avg_daily_demand` |
| Requisitos mínimos | Demanda diaria informada. |
| Valores faltantes | Artículos sin demanda no se evalúan. |
| Interpretación | Menor es mejor |
| Desglose | category · por corte (sin serie mensual) |

Supuestos:

- Mide faltantes al momento del corte, no pedidos no surtidos.

### Días de inventario (cobertura) (`inventory_coverage_days`)

Días que alcanzaría el inventario al ritmo de demanda actual, ponderado por valor.

| Atributo | Valor |
|---|---|
| Fórmula | Σ existencia × costo ÷ Σ demanda diaria × costo |
| Unidad | días |
| Frecuencia | por corte |
| Fuente | Plantilla `inventory_items` (Existencias de inventario) |
| Campos | `on_hand_qty`, `unit_cost`, `avg_daily_demand` |
| Requisitos mínimos | Demanda y costo unitario. |
| Valores faltantes | Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron. |
| Interpretación | Informativo (sin objetivo) |
| Desglose | category · por corte (sin serie mensual) |

Supuestos:

- Aproxima días de inventario con demanda, no con costo de ventas contable.

### Inventario sin movimiento (`obsolete_inventory_share`)

Proporción del valor del inventario sin movimiento por más días que el umbral configurado.

| Atributo | Valor |
|---|---|
| Fórmula | Valor de artículos con días sin movimiento > umbral ÷ valor total × 100 |
| Unidad | % |
| Frecuencia | por corte |
| Fuente | Plantilla `inventory_items` (Existencias de inventario) |
| Campos | `on_hand_qty`, `unit_cost`, `last_movement_date` |
| Requisitos mínimos | Costo y fecha del último movimiento. |
| Valores faltantes | Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron. |
| Interpretación | Menor es mejor |
| Desglose | category · por corte (sin serie mensual) |

Supuestos:

- La fecha de referencia es el movimiento más reciente del conjunto de datos.
- Sin movimiento no implica obsolescencia confirmada.

## Logística

### Rendimiento de combustible (`fuel_efficiency_km_l`)

Kilómetros recorridos por litro, método tanque lleno a tanque lleno.

| Atributo | Valor |
|---|---|
| Fórmula | Σ distancia entre cargas llenas ÷ Σ litros cargados en el intervalo |
| Unidad | km/l |
| Frecuencia | mensual |
| Fuente | Plantilla `fuel_logs` (Cargas de combustible) |
| Campos | `vehicle_code`, `date`, `odometer_km`, `liters` |
| Requisitos mínimos | Al menos 3 intervalos válidos. |
| Valores faltantes | La primera carga de cada vehículo solo sirve de referencia; intervalos con odómetro no creciente se excluyen. |
| Interpretación | Mayor es mejor |
| Desglose | vehicle_code · serie mensual |

Supuestos:

- Cada carga llena repone el combustible consumido desde la carga llena anterior.

### Costo de combustible por kilómetro (`fuel_cost_per_km`)

Importe de combustible por kilómetro recorrido.

| Atributo | Valor |
|---|---|
| Fórmula | Σ importe en intervalos válidos ÷ Σ distancia |
| Unidad | moneda/km |
| Frecuencia | mensual |
| Fuente | Plantilla `fuel_logs` (Cargas de combustible) |
| Campos | `vehicle_code`, `date`, `odometer_km`, `liters`, `total_cost` |
| Requisitos mínimos | Al menos 3 intervalos con importe. |
| Valores faltantes | Intervalos sin importe se excluyen. |
| Interpretación | Menor es mejor |
| Desglose | vehicle_code · serie mensual |

Supuestos:

- Solo combustible; no incluye mantenimiento, llantas ni depreciación.

### Gasto en combustible (`fuel_cost_total`)

Suma de importes de cargas de combustible.

| Atributo | Valor |
|---|---|
| Fórmula | Σ importe |
| Unidad | moneda |
| Frecuencia | mensual |
| Fuente | Plantilla `fuel_logs` (Cargas de combustible) |
| Campos | `total_cost` |
| Requisitos mínimos | Al menos una carga con importe. |
| Valores faltantes | Cargas sin importe no suman. |
| Interpretación | Informativo (sin objetivo) |
| Desglose | vehicle_code · serie mensual |
