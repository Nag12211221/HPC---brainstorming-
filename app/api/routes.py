"""REST API blueprint exposing all platform services."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, request

from ..config import CONFIG
from ..models.failure_predictor import model_registry
from ..services.ab_testing import ab_router
from ..services.case_study import run_case_study
from ..services.feedback import feedback_store
from ..services.roi_calculator import compute_roi
from ..subsystems import registry as subsystem_registry

api = Blueprint("api", __name__, url_prefix="/api")

# fleet manager is initialised lazily after Flask app is created
_fleet = None


def init_fleet(fleet):
    global _fleet
    _fleet = fleet


def _f():
    if _fleet is None:
        raise RuntimeError("Fleet manager not initialised")
    return _fleet


# -- Meta --------------------------------------------------------------------

@api.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@api.get("/subsystems")
def list_subsystems() -> Any:
    return jsonify([
        {"id": s.id, "name": s.name, "description": s.description,
         "signals": s.signals, "units": s.units}
        for s in subsystem_registry.all()
    ])


# -- Config ------------------------------------------------------------------

@api.get("/config")
def get_config() -> Any:
    return jsonify(CONFIG.as_dict())


@api.patch("/config")
def patch_config() -> Any:
    patch = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(CONFIG.update(patch))
    except KeyError:
        return jsonify({"error": "unknown configuration key"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "invalid configuration value"}), 400


# -- Fleet & vehicles --------------------------------------------------------

@api.get("/fleet")
def fleet() -> Any:
    return jsonify({
        "summary": _f().summary(),
        "vehicles": _f().list_vehicles(),
    })


@api.get("/fleet/summary")
def fleet_summary() -> Any:
    return jsonify(_f().summary())


@api.get("/vehicles/<vehicle_id>")
def vehicle_detail(vehicle_id: str) -> Any:
    window = int(request.args.get("window", 180))
    data = _f().get_vehicle(vehicle_id, window=window)
    if data is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(data)


@api.post("/fleet/reseed")
def reseed_fleet() -> Any:
    body = request.get_json(force=True, silent=True) or {}
    size = int(body.get("fleet_size", CONFIG.fleet_size))
    CONFIG.fleet_size = size
    _f().reseed(size)
    return jsonify({"status": "reseeded", "fleet_size": size})


# -- Alerts ------------------------------------------------------------------

@api.get("/alerts")
def alerts() -> Any:
    limit = int(request.args.get("limit", 50))
    return jsonify(_f().alerts.list(limit=limit))


@api.post("/alerts/<alert_id>/ack")
def ack_alert(alert_id: str) -> Any:
    ok = _f().alerts.acknowledge(alert_id)
    return (jsonify({"status": "acknowledged"}) if ok
            else (jsonify({"error": "not found"}), 404))


# -- ROI ---------------------------------------------------------------------

@api.get("/roi")
def roi() -> Any:
    fleet_size = int(request.args.get("fleet_size", CONFIG.fleet_size))
    lift = float(request.args.get("detection_lift_pct", 0.0))
    return jsonify(compute_roi(fleet_size=fleet_size, detection_lift_pct=lift))


# -- Models / A-B ------------------------------------------------------------

@api.get("/models")
def list_models() -> Any:
    return jsonify({
        "active": [m for m in model_registry.list() if m["active"]][0],
        "available": model_registry.list(),
        "history": model_registry.history(),
        "ab_split": CONFIG.ab_traffic_split,
        "ab_report": ab_router.report(),
    })


@api.post("/models/activate")
def activate_model() -> Any:
    body = request.get_json(force=True, silent=True) or {}
    version = body.get("version")
    try:
        model_registry.set_active(version)
        return jsonify({"active": version})
    except KeyError:
        return jsonify({"error": f"unknown model {version}"}), 404


@api.patch("/models/ab_split")
def update_ab_split() -> Any:
    body = request.get_json(force=True, silent=True) or {}
    split = body.get("split") or {}
    if not split or abs(sum(split.values()) - 1.0) > 0.01:
        return jsonify({"error": "split must sum to 1.0"}), 400
    CONFIG.ab_traffic_split = {k: float(v) for k, v in split.items()}
    _f().reseed(CONFIG.fleet_size)
    return jsonify({"ab_split": CONFIG.ab_traffic_split})


# -- Feedback / retraining ---------------------------------------------------

@api.get("/feedback")
def list_feedback() -> Any:
    return jsonify({
        "entries": feedback_store.list(),
        "retraining_history": feedback_store.retraining_history(),
    })


@api.post("/feedback")
def submit_feedback() -> Any:
    body = request.get_json(force=True, silent=True) or {}
    entry = feedback_store.submit(
        vehicle_id=body.get("vehicle_id"),
        subsystem_id=body.get("subsystem_id", "battery_thermal"),
        label=body.get("label", "comment"),
        comment=body.get("comment", ""),
        severity=body.get("severity", "info"),
        submitted_by=body.get("submitted_by", "customer"),
    )
    return jsonify(entry), 201


@api.post("/feedback/retrain")
def retrain() -> Any:
    body = request.get_json(force=True, silent=True) or {}
    version = body.get("new_version") or f"ewma_plus_v2.{len(feedback_store.retraining_history()) + 1}"
    event = feedback_store.trigger_retrain(version)
    return jsonify(event)


# -- Case study --------------------------------------------------------------

@api.get("/case_study")
def case_study() -> Any:
    scenario = request.args.get("scenario", "coolant_pump_degrading")
    horizon = int(request.args.get("horizon_minutes", 240))
    return jsonify(run_case_study(scenario=scenario, horizon_minutes=horizon))


# -- Reports / export --------------------------------------------------------

@api.get("/reports/executive")
def executive_report() -> Any:
    fleet_summary = _f().summary()
    roi_data = compute_roi(fleet_summary["fleet_size"])
    open_alerts = [a for a in _f().alerts.list(200) if not a["acknowledged"]]
    report = {
        "title": "HPC Predictive Quality — Executive Summary",
        "subsystem": "Battery Thermal Management",
        "fleet_summary": fleet_summary,
        "roi": roi_data,
        "active_model": model_registry.active().version,
        "open_alerts": len(open_alerts),
        "ab_report": ab_router.report(),
        "headline_metrics": {
            "validation_cycle_reduction_pct": CONFIG.validation_cycle_reduction_pct,
            "projected_annual_savings_usd": roi_data["total_annual_savings_usd"],
            "open_critical_alerts": sum(1 for a in open_alerts if a["severity"] == "critical"),
        },
    }
    fmt = request.args.get("format", "json")
    if fmt == "csv":
        return _report_csv(report)
    return jsonify(report)


def _report_csv(report: Dict[str, Any]) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["section", "key", "value"])
    def write(section: str, d: Dict[str, Any]):
        for k, v in d.items():
            if isinstance(v, dict):
                write(f"{section}.{k}", v)
            else:
                w.writerow([section, k, json.dumps(v) if not isinstance(v, (int, float, str)) else v])
    write("headline_metrics", report["headline_metrics"])
    write("fleet_summary", report["fleet_summary"])
    write("roi", report["roi"])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=executive_report.csv"},
    )
