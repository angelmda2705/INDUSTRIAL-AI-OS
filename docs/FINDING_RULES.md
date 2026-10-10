# Reglas de hallazgos

Implementadas en `backend/app/services/analytics/rules.py`. Todas son deterministas: mismos datos, parámetros y
objetivos producen los mismos hallazgos. Los umbrales configurables están en *Organización → Configuración*.

**Naturaleza:** `confirmed_issue` = condición verificada en los datos (no implica causa) · `statistical_anomaly` =
valor inusual (puede ser error de captura) · `hypothesis` = explicación posible que debe investigarse.

**Tipo de impacto:** `recorded_cost` = costo ya registrado · `estimated_excess_cost` = sobrecosto estimado ·
`capital_tied` = valor de inventario expuesto. No se suman entre tipos; ninguno es ahorro realizado.

## Comunes a todas las plantillas

| Regla | Naturaleza | Condición | Prioridad |
|---|---|---|---|
| `DQ-MISSING` | confirmada | Campo opcional mapeado con ≥ 20 % de vacíos | media si ≥ 50 % y afecta KPI; si no, baja |
| `DQ-DUPLICATES` | confirmada | Registros con la misma huella de campos clave en el conjunto | media |
| `KPI-TARGET:<kpi>` | confirmada | Valor total o por dimensión peor que el objetivo ± tolerancia (solo si la organización definió objetivo) | alta ≥ 20 % de brecha relativa, media ≥ 10 %, baja |
| `KPI-TREND:<kpi>` | anomalía | Serie mensual (≥ 6 meses) con tendencia desfavorable significativa: Mann-Kendall con corrección por empates, α = 0.05; pendiente de Sen | media; confianza alta si p < 0.01 y ≥ 8 meses |

## Producción

| Regla | Naturaleza | Condición |
|---|---|---|
| `PRD-DOWNTIME-CONCENTRATION` | confirmada | Con ≥ 3 centros de trabajo, uno concentra ≥ 50 % del tiempo muerto (alta si ≥ 70 %) |

## Mantenimiento

| Regla | Naturaleza | Condición | Impacto |
|---|---|---|---|
| `MNT-RECURRENT-FAILURES` | confirmada | Equipo con ≥ 3 fallas (alta si ≥ 5) | `recorded_cost`: costos registrados de esas fallas |
| `MNT-REPEATED-CAUSE` | hipótesis | Misma causa registrada ≥ 2 veces en un equipo | — |
| `MNT-LONG-REPAIRS` | anomalía | Con ≥ 8 reparaciones, duración con z robusto ≥ umbral (3.5) | — |
| `MNT-PREVENTIVE-LATE` | confirmada | Preventivo iniciado después de la fecha programada + tolerancia | — |
| `MNT-MISSING-END` | confirmada (datos) | Fallas sin fecha de fin | — |
| `MNT-OVERLAP` | confirmada (datos) | Falla que inicia antes del fin de la anterior del mismo equipo | — |

## Inventarios

| Regla | Naturaleza | Condición | Impacto |
|---|---|---|---|
| `INV-NEGATIVE` | confirmada (datos) | Existencia < 0 | — |
| `INV-STOCKOUT` | confirmada | Demanda > 0 y existencia ≤ 0 (crítica si incluye clase A) | — |
| `INV-BELOW-ROP` | confirmada | Existencia ≤ ROP (sin incluir faltantes); adjunta cantidad sugerida como propuesta | — |
| `INV-EXCESS` | confirmada | Existencia > máximo | `capital_tied`: (existencia − máximo) × costo |
| `INV-NO-MOVEMENT` | hipótesis | Días sin movimiento > umbral (180) respecto del movimiento más reciente del conjunto | `capital_tied`: existencia × costo |
| `INV-MISSING-PARAMS` | confirmada (datos) | Sin demanda o tiempo de reposición para calcular ROP | — |

## Logística (combustible)

| Regla | Naturaleza | Condición | Impacto |
|---|---|---|---|
| `FLT-FUEL-ANOMALY` | anomalía | Vehículo con ≥ 6 intervalos y rendimiento con z robusto ≤ −3.5 respecto de su propia mediana | `estimated_excess_cost`: Σ (litros − distancia ÷ mediana km/l) × precio por litro |
| `FLT-ODOMETER` | confirmada (datos) | Odómetro no creciente respecto de la carga llena anterior | — |

Confianza de `FLT-FUEL-ANOMALY`: alta con ≥ 12 intervalos y z ≤ −5; media con ≥ 8; baja en otro caso
(heurística documentada, no una probabilidad). El método z robusto no es aplicable cuando más de la mitad de los
valores son idénticos (MAD = 0); en ese caso no se reporta anomalía.

## Ciclo de vida

* Huella = `sha256(conjunto | regla | clave)`: un mismo problema no se duplica entre análisis.
* Si se vuelve a detectar → se actualiza la evidencia; si estaba *resuelto* → se **reabre** con evento en el historial.
* Si deja de detectarse → `condition_active = false` y evento *condición ya no detectada* (verificación).
* Los hallazgos *descartados* se mantienen descartados aunque la condición persista (decisión del usuario).
