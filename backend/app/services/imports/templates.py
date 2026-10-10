"""Import templates: the target schemas that uploaded columns are mapped onto.

Each template declares typed fields, which of them are required, which ones
identify a record (used for duplicate detection) and synonyms that help the
automatic column suggestion. Templates are the contract between the importer
and the analytics modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FieldType = Literal["string", "integer", "decimal", "date", "datetime", "boolean", "enum"]


@dataclass(frozen=True)
class TemplateField:
    name: str
    label: str
    type: FieldType
    required: bool = False
    description: str = ""
    min_value: float | None = None
    max_value: float | None = None
    choices: tuple[str, ...] = ()
    synonyms: tuple[str, ...] = ()
    max_length: int = 200
    # Accepted spellings for enum values: (alias, canonical choice)
    choice_aliases: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ImportTemplate:
    code: str
    name: str
    area: str
    description: str
    fields: tuple[TemplateField, ...]
    key_fields: tuple[str, ...] = ()
    # Cross-field rules: (field_a, op, field_b, message); op in {"<=", ">="}
    cross_rules: tuple[tuple[str, str, str, str], ...] = field(default_factory=tuple)
    generic: bool = False
    # Field used to place records in time (monthly series, period of analysis).
    date_field: str | None = None

    def field(self, name: str) -> TemplateField:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(name)


PRODUCTION = ImportTemplate(
    code="production_records",
    name="Registros de producción",
    area="production",
    description=(
        "Un renglón por orden, turno o día de un centro de trabajo. Permite calcular cumplimiento, "
        "desperdicio, utilización, tiempos muertos y productividad."
    ),
    fields=(
        TemplateField("date", "Fecha", "date", True, "Fecha de producción.", synonyms=("fecha", "dia", "día", "date", "fecha produccion")),
        TemplateField("work_center", "Centro de trabajo", "string", True, "Línea, celda o máquina.",
                      synonyms=("centro", "centro de trabajo", "linea", "línea", "maquina", "máquina", "work center", "workcenter")),
        TemplateField("product", "Producto", "string", False, synonyms=("producto", "sku", "articulo", "artículo", "item", "product")),
        TemplateField("shift", "Turno", "string", False, synonyms=("turno", "shift")),
        TemplateField("order_ref", "Orden de producción", "string", False, synonyms=("orden", "op", "orden de produccion", "work order", "order")),
        TemplateField("planned_qty", "Cantidad planeada", "decimal", False, "Unidades programadas.", min_value=0,
                      synonyms=("planeado", "cantidad planeada", "plan", "programado", "planned", "planned qty")),
        TemplateField("produced_qty", "Cantidad buena producida", "decimal", True, "Unidades conformes (sin desperdicio).", min_value=0,
                      synonyms=("producido", "cantidad producida", "real", "buenas", "piezas buenas", "produced", "good qty")),
        TemplateField("scrap_qty", "Desperdicio / scrap", "decimal", False, "Unidades rechazadas o desperdiciadas.", min_value=0,
                      synonyms=("scrap", "desperdicio", "merma", "rechazo", "rechazos", "defectuosas")),
        TemplateField("planned_time_min", "Tiempo programado (min)", "decimal", False, "Tiempo disponible planeado para producir.", min_value=0,
                      synonyms=("tiempo programado", "tiempo disponible", "minutos programados", "planned time")),
        TemplateField("run_time_min", "Tiempo de operación (min)", "decimal", False, "Tiempo efectivamente produciendo.", min_value=0,
                      synonyms=("tiempo operacion", "tiempo de operación", "tiempo real", "run time", "minutos operacion")),
        TemplateField("downtime_min", "Tiempo muerto (min)", "decimal", False, "Paros no planeados.", min_value=0,
                      synonyms=("tiempo muerto", "paros", "downtime", "minutos paro")),
        TemplateField("std_time_per_unit_min", "Tiempo estándar por unidad (min)", "decimal", False, min_value=0,
                      synonyms=("tiempo estandar", "tiempo estándar", "standard time", "ciclo estandar")),
    ),
    key_fields=("date", "work_center", "product", "shift", "order_ref"),
    date_field="date",
)

MAINTENANCE = ImportTemplate(
    code="maintenance_events",
    name="Eventos de mantenimiento",
    area="maintenance",
    description=(
        "Fallas, correctivos y preventivos por equipo o vehículo. Permite calcular MTTR, MTBF, "
        "disponibilidad inherente, costos y cumplimiento del preventivo."
    ),
    fields=(
        TemplateField("asset_code", "Código de equipo", "string", True, synonyms=("equipo", "activo", "asset", "codigo equipo", "unidad", "maquina", "máquina")),
        TemplateField("event_type", "Tipo de evento", "enum", True, "falla, correctivo, preventivo o inspeccion.",
                      choices=("falla", "correctivo", "preventivo", "inspeccion"), synonyms=("tipo", "tipo de evento", "event type", "tipo mantenimiento"),
                      choice_aliases=(("failure", "falla"), ("averia", "falla"), ("breakdown", "falla"), ("corrective", "correctivo"),
                                      ("preventive", "preventivo"), ("pm", "preventivo"), ("inspection", "inspeccion"))),
        TemplateField("event_start", "Inicio (falla o servicio)", "datetime", True, "Momento de la falla o inicio del servicio.",
                      synonyms=("inicio", "fecha inicio", "fecha falla", "start", "fecha")),
        TemplateField("event_end", "Fin (equipo disponible)", "datetime", False, "Momento en que el equipo vuelve a estar disponible.",
                      synonyms=("fin", "fecha fin", "fecha termino", "end", "liberado")),
        TemplateField("scheduled_date", "Fecha programada", "date", False, "Solo preventivos: fecha comprometida.",
                      synonyms=("programado", "fecha programada", "scheduled")),
        TemplateField("cause", "Causa", "string", False, synonyms=("causa", "motivo", "falla", "descripcion falla", "cause")),
        TemplateField("work_order_ref", "Orden de trabajo", "string", False, synonyms=("ot", "orden de trabajo", "work order")),
        TemplateField("labor_hours", "Horas hombre", "decimal", False, min_value=0, synonyms=("horas hombre", "hh", "labor hours")),
        TemplateField("parts_cost", "Costo de refacciones", "decimal", False, min_value=0, synonyms=("refacciones", "costo refacciones", "parts")),
        TemplateField("labor_cost", "Costo de mano de obra", "decimal", False, min_value=0, synonyms=("mano de obra", "costo mano de obra", "labor cost")),
        TemplateField("other_cost", "Otros costos", "decimal", False, min_value=0, synonyms=("otros", "otros costos", "servicios externos")),
    ),
    key_fields=("asset_code", "event_type", "event_start"),
    date_field="event_start",
    cross_rules=(("event_start", "<=", "event_end", "El fin no puede ser anterior al inicio."),),
)

INVENTORY = ImportTemplate(
    code="inventory_items",
    name="Existencias de inventario",
    area="inventory",
    description=(
        "Foto de existencias por artículo (y opcionalmente almacén). Permite clasificación ABC, punto de "
        "reorden, stock de seguridad, cobertura y detección de exceso u obsolescencia."
    ),
    fields=(
        TemplateField("sku", "SKU / código", "string", True, synonyms=("sku", "codigo", "código", "clave", "articulo", "item", "part number")),
        TemplateField("description", "Descripción", "string", False, synonyms=("descripcion", "descripción", "nombre", "description")),
        TemplateField("category", "Categoría", "string", False, synonyms=("categoria", "categoría", "familia", "category")),
        TemplateField("unit", "Unidad de medida", "string", False, synonyms=("unidad", "um", "uom", "unit")),
        TemplateField("warehouse", "Almacén", "string", False, synonyms=("almacen", "almacén", "bodega", "warehouse", "ubicacion")),
        TemplateField("on_hand_qty", "Existencia", "decimal", True, synonyms=("existencia", "existencias", "stock", "on hand", "inventario", "cantidad")),
        TemplateField("unit_cost", "Costo unitario", "decimal", False, min_value=0, synonyms=("costo", "costo unitario", "unit cost", "precio costo")),
        TemplateField("avg_daily_demand", "Demanda diaria promedio", "decimal", False, min_value=0,
                      synonyms=("demanda diaria", "consumo diario", "demanda promedio", "daily demand")),
        TemplateField("demand_std_daily", "Desviación estándar de demanda diaria", "decimal", False, min_value=0,
                      synonyms=("desviacion demanda", "desviación", "std demanda", "sigma")),
        TemplateField("lead_time_days", "Tiempo de reposición (días)", "decimal", False, min_value=0,
                      synonyms=("lead time", "tiempo de entrega", "tiempo reposicion", "dias entrega")),
        TemplateField("min_qty", "Mínimo", "decimal", False, min_value=0, synonyms=("minimo", "mínimo", "min")),
        TemplateField("max_qty", "Máximo", "decimal", False, min_value=0, synonyms=("maximo", "máximo", "max")),
        TemplateField("last_movement_date", "Último movimiento", "date", False,
                      synonyms=("ultimo movimiento", "último movimiento", "fecha ultimo movimiento", "last movement")),
    ),
    key_fields=("sku", "warehouse"),
)

FUEL = ImportTemplate(
    code="fuel_logs",
    name="Cargas de combustible",
    area="logistics",
    description=(
        "Una carga por renglón con odómetro. Permite calcular rendimiento (km/l), costo por kilómetro "
        "y detectar consumos atípicos por vehículo."
    ),
    fields=(
        TemplateField("vehicle_code", "Vehículo", "string", True, synonyms=("vehiculo", "vehículo", "unidad", "placa", "economico", "económico", "vehicle")),
        TemplateField("date", "Fecha", "datetime", True, synonyms=("fecha", "fecha carga", "date")),
        TemplateField("odometer_km", "Odómetro (km)", "decimal", True, min_value=0, synonyms=("odometro", "odómetro", "kilometraje", "km", "odometer")),
        TemplateField("liters", "Litros", "decimal", True, min_value=0.001, synonyms=("litros", "lts", "liters", "volumen")),
        TemplateField("total_cost", "Importe total", "decimal", False, min_value=0, synonyms=("importe", "costo", "monto", "total", "cost")),
        TemplateField("driver_code", "Conductor (código interno)", "string", False, synonyms=("conductor", "operador", "chofer", "driver")),
        TemplateField("route", "Ruta", "string", False, synonyms=("ruta", "route")),
        TemplateField("full_tank", "Tanque lleno", "boolean", False, synonyms=("tanque lleno", "lleno", "full")),
    ),
    key_fields=("vehicle_code", "date", "odometer_km"),
    date_field="date",
)

GENERIC = ImportTemplate(
    code="generic",
    name="Tabla genérica",
    area="general",
    description="Cualquier tabla. Solo se perfila la calidad de los datos; no se calculan indicadores operativos.",
    fields=(),
    generic=True,
)

TEMPLATES: dict[str, ImportTemplate] = {t.code: t for t in (PRODUCTION, MAINTENANCE, INVENTORY, FUEL, GENERIC)}


def get_template(code: str) -> ImportTemplate | None:
    return TEMPLATES.get(code)
