# HPC-Driven Predictive Quality Platform — POC

A functional prototype of a SaaS-style predictive failure-detection platform for
OEMs, built around the **Battery Thermal Management** subsystem. The POC is
service-oriented from day one so that additional subsystems (HVAC, infotainment)
can be plugged in incrementally without touching the dashboard or APIs.

> Selected subsystem: **Battery Thermal Management**
>
> *Justification:* modern EV packs already stream the richest, easiest-to-access
> telemetry on the vehicle CAN bus (cell temps, coolant flow, pack current,
> voltage, SoC), and thermal-related events drive the **largest single warranty
> cost line** for EV OEMs — a full pack replacement runs into five figures per
> vehicle. A 30–40% reduction in warranty validation cycles therefore yields
> the highest dollar value of any candidate subsystem.

---

## Quick start

```bash
pip install -r requirements.txt
python run.py
# open http://localhost:5000
```

Run the test suite:

```bash
python -m unittest discover tests -v
```

No external services required — Plotly is loaded from CDN in the browser; the
backend is pure Python + Flask with no numpy/sklearn dependency.

---

## What the dashboard demonstrates

| Tab | Shows |
|---|---|
| **Executive** | C-level KPIs, projected warranty savings vs. baseline, validation-cycle reduction, before/after detection accuracy. |
| **Fleet** | Live fleet table with status badges, drift scores, failure probabilities with 95% confidence intervals, time-to-failure, model assignment. Filter & drill-down. |
| **Vehicle Drill-down** | Per-vehicle digital twin (HPC expected vs. actual field measurements) for pack temp & coolant ΔT, drift trend, load profile, vehicle-scoped alerts with acknowledgement. |
| **Case Study** | Reproducible scenario simulator (coolant pump degradation, cell imbalance, sensor bias) that compares baseline vs. EWMA+ models side-by-side and reports warning lead time. |
| **Models & A/B** | Versioned model registry, model activation, configurable traffic split, per-arm precision/recall report. |
| **Feedback** | Customer-facing intake form (true positive / false positive / missed) and on-demand retraining trigger with version history. |
| **Config** | Live edit of thresholds, ROI assumptions, and fleet size via `PATCH /api/config`. |

The header includes **JSON / CSV report export** for management reviews.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Single-Page Dashboard  (static/index.html + app.js)        │
│  Plotly charts, drill-down, exports — all via /api/*        │
└─────────────────────────────┬────────────────────────────────┘
                              │ REST/JSON
┌─────────────────────────────▼────────────────────────────────┐
│  Flask API  (app/api/routes.py)                              │
│   /api/{health,subsystems,config,fleet,vehicles,alerts,roi,  │
│         models,case_study,feedback,reports}                  │
└──────┬──────────────────────┬──────────────────────┬─────────┘
       │                      │                      │
┌──────▼────────┐  ┌──────────▼─────────┐  ┌─────────▼─────────┐
│  Subsystem    │  │  Models            │  │  Services         │
│  registry     │  │  - DriftDetector   │  │  - FleetManager   │
│  - base.py    │  │    (EWMA)          │  │  - AlertCenter    │
│  - battery_   │  │  - FailureModel    │  │  - ROI calc       │
│    thermal.py │  │    Registry (v1,v2)│  │  - FeedbackStore  │
│  + HVAC /     │  │  + A/B router      │  │  - Case study sim │
│    infotain-  │  │  + version history │  │                   │
│    ment …     │  │                    │  │                   │
└───────────────┘  └────────────────────┘  └───────────────────┘
```

Key design points that satisfy the SOA requirements:

* **`SubsystemRegistry`** — drop a new class implementing `Subsystem` into
  `app/subsystems/`, register it, and the API + UI light up the new domain
  with zero changes elsewhere.
* **`PlatformConfig`** is mutable at runtime via `PATCH /api/config`; thresholds
  and ROI assumptions can be tuned per-customer without redeploying.
* **`FailureModelRegistry`** holds versioned, named models. The `/api/models`
  endpoint exposes the catalog, lets ops promote a version, and reports A/B
  performance per arm.
* **`ABRouter`** is hash-deterministic per VIN, so the same vehicle is always
  in the same arm — required for honest A/B measurement.
* **`FeedbackStore` + `/api/feedback/retrain`** simulate the
  customer → retraining → new-version → version-history pipeline.

---

## Telemetry & failure simulation

`BatteryThermalSubsystem` produces realistic synthetic data:

* **Drive cycle** drives current draw (0–250 A) which generates I²R heat.
* **Cooling** is a function of coolant flow (degrades when the pump is failing).
* **Digital twin (HPC expected)** assumes nominal hardware — so the residual
  (`actual − expected`) is the signal the platform exploits.

Built-in failure scenarios (randomly assigned per vehicle, deterministic seed):

| Scenario | Effect |
|---|---|
| `coolant_pump_degrading` | Flow slowly drops → ΔT widens → pack temp rises above twin. |
| `cell_imbalance` | One cell heats faster than the rest → max-cell residual climbs. |
| `sensor_bias` | Reported temps drift below truth — *hidden* fault the drift detector still catches via coolant ΔT residual. |
| `nominal` | Healthy. |

---

## Predictive pipeline

1. **Feature extraction** — rolling residuals (mean + slope) per channel.
2. **`DriftDetector`** — EWMA mean/variance per feature; normalised drift score.
3. **`FailureModel`** — transparent logistic over features + drift score with
   propagated 95% confidence interval and heuristic time-to-failure horizon.
4. **`AlertCenter`** — dedup by (vehicle, severity), acknowledged via API.

Two models are shipped so the A/B harness has something real to compare:

* `baseline_v1` — residual-mean only, mimics legacy thresholding.
* `ewma_plus_v2` — adds residual-slope features, fires earlier (default active).

---

## ROI / business value

`compute_roi(fleet_size, detection_lift_pct)` produces:

* Annual baseline vs. projected warranty cost
* Claims avoided per year
* Validation-cycle savings (default **35%** reduction — within the 30–40% target)
* Total projected savings used by the Executive dashboard tile

All assumptions (avg claim cost, claims/1k vehicles, cycle cost, recovery rate)
are exposed in `app/config.py` and editable from the **Config** tab.

---

## REST API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness |
| GET | `/api/subsystems` | List registered subsystems |
| GET / PATCH | `/api/config` | Read / patch platform configuration |
| GET | `/api/fleet` | Fleet summary + per-vehicle status |
| GET | `/api/vehicles/<vin>?window=N` | Telemetry timeline, twin, prediction |
| POST | `/api/fleet/reseed` | Re-initialise the simulated fleet |
| GET | `/api/alerts` · POST `/api/alerts/<id>/ack` | Alert feed + ack |
| GET | `/api/roi?fleet_size=…&detection_lift_pct=…` | ROI projection |
| GET | `/api/models` · POST `/api/models/activate` · PATCH `/api/models/ab_split` | Model registry & A/B |
| GET / POST | `/api/feedback` · POST `/api/feedback/retrain` | Feedback + retrain trigger |
| GET | `/api/case_study?scenario=…` | Reproducible scenario simulation |
| GET | `/api/reports/executive?format=json\|csv` | Exportable management report |

---

## Adding a new subsystem (e.g. HVAC)

1. Create `app/subsystems/hvac.py` with a class implementing `Subsystem`
   (`reset`, `step`, `extract_features`, plus `id`, `name`, `signals`, `units`).
2. Register it in `app/subsystems/__init__.py`:
   ```python
   from .hvac import HVACSubsystem
   registry.register(HVACSubsystem())
   ```
3. (Optional) point a second `FleetManager` instance at the new subsystem in
   `app/main.py`, or extend the existing one to multiplex.

No dashboard or API code needs to change — the catalog endpoint will surface
the new subsystem automatically.

---

## Repository layout

```
app/
├── api/routes.py              REST endpoints
├── config.py                  Mutable platform configuration
├── main.py                    Flask factory
├── models/
│   ├── drift_detector.py      EWMA-based drift scoring
│   └── failure_predictor.py   Logistic failure model + versioned registry
├── services/
│   ├── ab_testing.py          Hash-deterministic A/B router
│   ├── alerts.py              Alert center with dedup & acknowledgement
│   ├── case_study.py          Reproducible scenario harness
│   ├── feedback.py            Customer feedback store + retrain log
│   ├── fleet_manager.py       Background fleet simulator
│   └── roi_calculator.py      Warranty / validation savings
├── static/                    Dashboard (index.html, app.js, style.css)
└── subsystems/
    ├── base.py                Plugin interface
    ├── battery_thermal.py     Shipped subsystem
    └── registry.py            Pluggable catalog
run.py                         python run.py → http://localhost:5000
tests/test_basic.py            8 smoke + integration tests
```
