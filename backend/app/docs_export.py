"""Generate reference documentation from the code so docs cannot drift.

Produces docs/KPI_CATALOG.md, docs/API_ENDPOINTS.md and docs/openapi.json.
Run: python -m app.cli export-docs   (a test checks the committed files are current)
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.analytics.kpis import CATALOG
from app.services.imports.templates import TEMPLATES

DIRECTION = {"higher_is_better": "Mayor es mejor", "lower_is_better": "Menor es mejor", "neutral": "Informativo (sin objetivo)"}
AREA = {"production": "Producción", "maintenance": "Mantenimiento", "inventory": "Inventarios", "logistics": "Logística"}


def kpi_catalog_md() -> str:
    lines = [
        "# Catálogo de indicadores",
        "",
        "> Documento generado desde `backend/app/services/analytics/kpis.py` con `python -m app.cli export-docs`. No editar a mano.",
        "",
        "Reglas generales:",
        "",
        "- Si no se cumplen los requisitos mínimos, el indicador se reporta como **datos insuficientes** y no se muestra ningún valor.",
        "- El tamaño de muestra y los valores de entrada (numerador/denominador) se guardan con cada cálculo para que sea reproducible.",
        "- Los objetivos los define cada organización; la plataforma no asume estándares universales.",
        "- Cada análisis calcula el valor total del conjunto de datos, el desglose por la dimensión indicada y, cuando aplica, la serie mensual.",
        "",
    ]
    for area in ("production", "maintenance", "inventory", "logistics"):
        lines += [f"## {AREA[area]}", ""]
        for k in (k for k in CATALOG if k.area == area):
            lines += [
                f"### {k.name} (`{k.code}`)",
                "",
                k.description,
                "",
                "| Atributo | Valor |",
                "|---|---|",
                f"| Fórmula | {k.formula} |",
                f"| Unidad | {k.unit} |",
                f"| Frecuencia | {k.frequency} |",
                f"| Fuente | Plantilla `{k.template}` ({TEMPLATES[k.template].name}) |",
                f"| Campos | {', '.join(f'`{f}`' for f in k.required_fields)} |",
                f"| Requisitos mínimos | {k.min_requirements} |",
                f"| Valores faltantes | {k.missing_handling} |",
                f"| Interpretación | {DIRECTION[k.direction]} |",
                f"| Desglose | {k.dimension or '—'}{' · serie mensual' if k.monthly else ' · por corte (sin serie mensual)'} |",
                "",
            ]
            if k.assumptions:
                lines += ["Supuestos:", ""] + [f"- {a}" for a in k.assumptions] + [""]
    return "\n".join(lines).rstrip() + "\n"


def api_endpoints_md(spec: dict) -> str:
    lines = [
        "# Referencia de endpoints",
        "",
        "> Documento generado desde la especificación OpenAPI (`docs/openapi.json`) con `python -m app.cli export-docs`.",
        "> Convenciones (autenticación, CSRF, errores, paginación, aislamiento): ver [API.md](API.md).",
        "",
        "| Método | Ruta | Descripción |",
        "|---|---|---|",
    ]
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            lines.append(f"| {method.upper()} | `{path}` | {op.get('summary', '')} |")
    return "\n".join(lines) + "\n"


def export(out_dir: Path) -> list[Path]:
    from app.main import create_app

    spec = create_app().openapi()
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        out_dir / "KPI_CATALOG.md": kpi_catalog_md(),
        out_dir / "API_ENDPOINTS.md": api_endpoints_md(spec),
        out_dir / "openapi.json": json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
    return list(files)
