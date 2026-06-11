"""Generate comprehensive test datasets for the HPC Predictive Quality Platform.

Produces 10,000+ telemetry records spanning multiple failure scenarios,
edge cases, boundary conditions, and invalid inputs. Outputs:
  - test_data/telemetry_dataset.csv  (10,000+ records of normal + fault telemetry)
  - test_data/edge_cases.csv         (boundary and invalid inputs)
  - test_data/fleet_load_test.json   (large fleet payload for API load testing)
  - test_data/drift_sequences.csv    (time-series drift progressions)
  - test_data/api_scenarios.json     (5 real-time production scenario payloads)

Run:
    python -m tests.generate_test_data
"""

import csv
import json
import math
import os
import random
import sys

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.subsystems.battery_thermal import BatteryThermalSubsystem
from app.models.drift_detector import DriftDetector
from app.models.failure_predictor import model_registry

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "test_data")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Dataset 1: Large-scale telemetry dataset (10,000+ records)
# ---------------------------------------------------------------------------

def generate_telemetry_dataset(num_vehicles=50, steps_per_vehicle=200):
    """Generate realistic telemetry data from multiple vehicles with various scenarios."""
    sub = BatteryThermalSubsystem()
    records = []

    scenarios = ["nominal", "coolant_pump_degrading", "cell_imbalance", "sensor_bias"]
    # Distribute vehicles across scenarios with realistic proportions
    scenario_distribution = {
        "nominal": int(num_vehicles * 0.55),
        "coolant_pump_degrading": int(num_vehicles * 0.18),
        "cell_imbalance": int(num_vehicles * 0.15),
        "sensor_bias": int(num_vehicles * 0.12),
    }

    vehicle_idx = 0
    for scenario, count in scenario_distribution.items():
        for i in range(count):
            vin = f"VIN-{vehicle_idx:04d}"
            seed = vehicle_idx * 42 + 7
            sub.reset(vin, seed=seed)
            sub.override_scenario(vin, scenario, scenario_t0=30.0, seed=seed)

            for step in range(steps_per_vehicle):
                sample = sub.step(vin, dt=30.0)
                record = {
                    "vehicle_id": vin,
                    "scenario": scenario,
                    "timestamp_s": sample.t,
                    "fault_active": sample.fault_active,
                    # Actual readings
                    "actual_pack_temp_c": sample.actual["pack_temp_c"],
                    "actual_max_cell_temp_c": sample.actual["max_cell_temp_c"],
                    "actual_coolant_delta_c": sample.actual["coolant_delta_c"],
                    "actual_coolant_flow_lpm": sample.actual["coolant_flow_lpm"],
                    "actual_current_a": sample.actual["current_a"],
                    "actual_pack_voltage_v": sample.actual["pack_voltage_v"],
                    "actual_soc_pct": sample.actual["soc_pct"],
                    # Expected (HPC twin)
                    "expected_pack_temp_c": sample.expected["pack_temp_c"],
                    "expected_max_cell_temp_c": sample.expected["max_cell_temp_c"],
                    "expected_coolant_delta_c": sample.expected["coolant_delta_c"],
                    "expected_coolant_flow_lpm": sample.expected["coolant_flow_lpm"],
                    "expected_current_a": sample.expected["current_a"],
                    "expected_pack_voltage_v": sample.expected["pack_voltage_v"],
                    "expected_soc_pct": sample.expected["soc_pct"],
                    # Residuals
                    "residual_pack_temp_c": round(sample.actual["pack_temp_c"] - sample.expected["pack_temp_c"], 3),
                    "residual_max_cell_temp_c": round(sample.actual["max_cell_temp_c"] - sample.expected["max_cell_temp_c"], 3),
                    "residual_coolant_delta_c": round(sample.actual["coolant_delta_c"] - sample.expected["coolant_delta_c"], 3),
                    "residual_coolant_flow_lpm": round(sample.actual["coolant_flow_lpm"] - sample.expected["coolant_flow_lpm"], 3),
                }
                records.append(record)
            vehicle_idx += 1

    filepath = os.path.join(OUTPUT_DIR, "telemetry_dataset.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    print(f"  [1/5] Telemetry dataset: {len(records)} records -> {filepath}")
    return len(records)


# ---------------------------------------------------------------------------
# Dataset 2: Edge cases and boundary conditions
# ---------------------------------------------------------------------------

def generate_edge_cases():
    """Generate records with boundary conditions, invalid inputs, and nulls."""
    edge_cases = []

    # Boundary values for each signal
    boundary_defs = {
        "pack_temp_c": [-40.0, 0.0, 32.0, 48.0, 58.0, 80.0, 120.0],
        "max_cell_temp_c": [-40.0, 0.0, 35.0, 50.0, 60.0, 85.0, 150.0],
        "coolant_delta_c": [0.0, 1.5, 8.0, 14.0, 25.0, 50.0],
        "coolant_flow_lpm": [0.0, 0.5, 6.0, 12.0, 15.0, 25.0],
        "current_a": [0.0, 50.0, 120.0, 250.0, 300.0, 500.0],
        "pack_voltage_v": [0.0, 200.0, 350.0, 400.0, 420.0, 500.0, 800.0],
        "soc_pct": [0.0, 5.0, 20.0, 50.0, 80.0, 95.0, 100.0, 105.0],
    }

    # Generate all boundary combinations (sampled subset)
    rng = random.Random(12345)
    idx = 0
    for signal, boundaries in boundary_defs.items():
        for value in boundaries:
            record = {
                "test_id": f"EDGE-{idx:04d}",
                "category": "boundary_value",
                "signal": signal,
                "test_value": value,
                "description": f"Boundary test: {signal} = {value}",
                "expected_behavior": _expected_behavior(signal, value),
            }
            edge_cases.append(record)
            idx += 1

    # Invalid / error inputs
    invalid_inputs = [
        {"signal": "pack_temp_c", "test_value": None, "description": "Null temperature"},
        {"signal": "pack_temp_c", "test_value": float("nan"), "description": "NaN temperature"},
        {"signal": "pack_temp_c", "test_value": float("inf"), "description": "Infinite temperature"},
        {"signal": "pack_temp_c", "test_value": -273.16, "description": "Below absolute zero"},
        {"signal": "current_a", "test_value": -50.0, "description": "Negative current (regen)"},
        {"signal": "current_a", "test_value": None, "description": "Null current"},
        {"signal": "soc_pct", "test_value": -10.0, "description": "Negative SoC"},
        {"signal": "soc_pct", "test_value": 200.0, "description": "SoC > 100%"},
        {"signal": "coolant_flow_lpm", "test_value": -5.0, "description": "Negative flow"},
        {"signal": "coolant_flow_lpm", "test_value": 0.0, "description": "Zero flow (pump failure)"},
        {"signal": "pack_voltage_v", "test_value": 0.0, "description": "Zero voltage (disconnect)"},
        {"signal": "pack_voltage_v", "test_value": -100.0, "description": "Negative voltage (error)"},
        {"signal": "all", "test_value": None, "description": "All signals null (total dropout)"},
        {"signal": "timestamp", "test_value": -1.0, "description": "Negative timestamp"},
        {"signal": "timestamp", "test_value": 0.0, "description": "Zero timestamp"},
        {"signal": "vehicle_id", "test_value": "", "description": "Empty vehicle ID"},
        {"signal": "vehicle_id", "test_value": "A" * 500, "description": "Extremely long VIN"},
        {"signal": "vehicle_id", "test_value": "'; DROP TABLE vehicles;--", "description": "SQL injection attempt"},
        {"signal": "vehicle_id", "test_value": "<script>alert(1)</script>", "description": "XSS attempt"},
    ]
    for item in invalid_inputs:
        record = {
            "test_id": f"EDGE-{idx:04d}",
            "category": "invalid_input",
            "signal": item["signal"],
            "test_value": str(item["test_value"]),
            "description": item["description"],
            "expected_behavior": "graceful_error_handling",
        }
        edge_cases.append(record)
        idx += 1

    # Rapid state transitions
    transitions = [
        {"from": "nominal", "to": "coolant_pump_degrading", "description": "Sudden pump failure"},
        {"from": "nominal", "to": "cell_imbalance", "description": "Sudden cell imbalance"},
        {"from": "coolant_pump_degrading", "to": "nominal", "description": "Pump recovery (maintenance)"},
        {"from": "cell_imbalance", "to": "coolant_pump_degrading", "description": "Cascading failure"},
    ]
    for t in transitions:
        record = {
            "test_id": f"EDGE-{idx:04d}",
            "category": "state_transition",
            "signal": "scenario",
            "test_value": f"{t['from']} -> {t['to']}",
            "description": t["description"],
            "expected_behavior": "detect_transition_within_5_minutes",
        }
        edge_cases.append(record)
        idx += 1

    filepath = os.path.join(OUTPUT_DIR, "edge_cases.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=edge_cases[0].keys())
        writer.writeheader()
        writer.writerows(edge_cases)

    print(f"  [2/5] Edge cases: {len(edge_cases)} records -> {filepath}")
    return len(edge_cases)


def _expected_behavior(signal, value):
    thresholds = {
        "pack_temp_c": [(48.0, "warn"), (58.0, "critical")],
        "max_cell_temp_c": [(50.0, "warn"), (60.0, "critical")],
        "coolant_delta_c": [(8.0, "warn"), (14.0, "critical")],
        "coolant_flow_lpm": [(6.0, "warn_low"), (0.5, "critical_low")],
        "current_a": [(250.0, "over_current_warn")],
        "pack_voltage_v": [(350.0, "under_voltage_warn")],
        "soc_pct": [(5.0, "critical_low_soc"), (20.0, "warn_low_soc")],
    }
    if signal in thresholds:
        for threshold, behavior in thresholds[signal]:
            if signal in ("coolant_flow_lpm", "pack_voltage_v", "soc_pct"):
                if value <= threshold:
                    return behavior
            else:
                if value >= threshold:
                    return behavior
    return "nominal"


# ---------------------------------------------------------------------------
# Dataset 3: Fleet load test payload
# ---------------------------------------------------------------------------

def generate_fleet_load_test(num_vehicles=500):
    """Generate a large fleet payload for API load testing."""
    rng = random.Random(99)
    vehicles = []
    scenarios = ["nominal", "coolant_pump_degrading", "cell_imbalance", "sensor_bias"]
    weights = [0.55, 0.18, 0.15, 0.12]

    for i in range(num_vehicles):
        scenario = rng.choices(scenarios, weights=weights, k=1)[0]
        drift_score = rng.uniform(0.0, 1.2) if scenario != "nominal" else rng.uniform(0.0, 0.3)
        failure_prob = rng.uniform(0.0, 0.95) if scenario != "nominal" else rng.uniform(0.0, 0.25)
        vehicles.append({
            "vin": f"VIN-LOAD-{i:05d}",
            "scenario": scenario,
            "region": rng.choice(["NA-West", "NA-East", "EU-North", "EU-South", "APAC"]),
            "model_year": rng.choice([2022, 2023, 2024, 2025]),
            "mileage_km": rng.randint(5000, 150000),
            "drift_score": round(drift_score, 4),
            "failure_probability": round(failure_prob, 4),
            "ci_low": round(max(0, failure_prob - rng.uniform(0.05, 0.15)), 4),
            "ci_high": round(min(1, failure_prob + rng.uniform(0.05, 0.15)), 4),
            "time_to_failure_hours": round(rng.uniform(0.5, 72.0), 2) if failure_prob > 0.35 else None,
            "status": "critical" if failure_prob > 0.65 else "warning" if failure_prob > 0.35 else "healthy",
            "last_updated_epoch": 1718000000 + rng.randint(0, 86400),
            "telemetry_signals": {
                "pack_temp_c": round(rng.uniform(25.0, 65.0), 2),
                "max_cell_temp_c": round(rng.uniform(28.0, 70.0), 2),
                "coolant_delta_c": round(rng.uniform(2.0, 20.0), 2),
                "coolant_flow_lpm": round(rng.uniform(1.0, 13.0), 2),
                "current_a": round(rng.uniform(0.0, 280.0), 1),
                "pack_voltage_v": round(rng.uniform(320.0, 420.0), 2),
                "soc_pct": round(rng.uniform(5.0, 98.0), 1),
            },
        })

    payload = {
        "test_type": "fleet_load_test",
        "fleet_size": num_vehicles,
        "generated_at": "2026-06-11T18:30:00Z",
        "vehicles": vehicles,
        "expected_response_time_ms": 500,
        "expected_max_memory_mb": 256,
    }

    filepath = os.path.join(OUTPUT_DIR, "fleet_load_test.json")
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"  [3/5] Fleet load test: {num_vehicles} vehicles -> {filepath}")
    return num_vehicles


# ---------------------------------------------------------------------------
# Dataset 4: Drift detection time-series
# ---------------------------------------------------------------------------

def generate_drift_sequences(num_sequences=20, steps=500):
    """Generate long time-series for drift detection validation."""
    sub = BatteryThermalSubsystem()
    detector = DriftDetector(alpha=0.15)
    records = []

    scenarios = ["nominal", "coolant_pump_degrading", "cell_imbalance", "sensor_bias"]

    for seq_idx in range(num_sequences):
        scenario = scenarios[seq_idx % len(scenarios)]
        vin = f"VIN-DRIFT-{seq_idx:03d}"
        seed = seq_idx * 101

        sub.reset(vin, seed=seed)
        sub.override_scenario(vin, scenario, scenario_t0=50.0, seed=seed)
        detector.reset(vin)

        samples_buffer = []
        for step in range(steps):
            sample = sub.step(vin, dt=30.0)
            samples_buffer.append(sample)

            if len(samples_buffer) >= 30:
                features = sub.extract_features(samples_buffer[-30:])
                drift_result = detector.update(vin, features)
                prediction = model_registry.get("ewma_plus_v2").predict(features, drift_result["score"])

                records.append({
                    "sequence_id": seq_idx,
                    "vehicle_id": vin,
                    "scenario": scenario,
                    "step": step,
                    "timestamp_s": sample.t,
                    "fault_active": sample.fault_active,
                    "drift_score": drift_result["score"],
                    "failure_probability": prediction["probability"],
                    "ci_low": prediction["ci_low"],
                    "ci_high": prediction["ci_high"],
                    "ttf_hours": prediction["time_to_failure_hours"],
                    "residual_mean_max_cell_temp_c": features.get("residual_mean_max_cell_temp_c", 0.0),
                    "residual_slope_max_cell_temp_c": features.get("residual_slope_max_cell_temp_c", 0.0),
                    "residual_mean_coolant_delta_c": features.get("residual_mean_coolant_delta_c", 0.0),
                    "residual_mean_coolant_flow_lpm": features.get("residual_mean_coolant_flow_lpm", 0.0),
                })

    filepath = os.path.join(OUTPUT_DIR, "drift_sequences.csv")
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    print(f"  [4/5] Drift sequences: {len(records)} records -> {filepath}")
    return len(records)


# ---------------------------------------------------------------------------
# Dataset 5: Real-time production scenario payloads
# ---------------------------------------------------------------------------

def generate_api_scenarios():
    """Generate 5 realistic production scenario payloads for API integration testing."""
    scenarios = [
        {
            "scenario_name": "Fleet-Wide Monitoring Dashboard Load",
            "description": "Simulates a fleet operator loading the executive dashboard with 200 vehicles",
            "api_calls": [
                {"method": "GET", "path": "/api/fleet", "expected_status": 200,
                 "expected_response_fields": ["fleet_size", "vehicles"],
                 "max_response_time_ms": 300},
                {"method": "GET", "path": "/api/roi?fleet_size=200&detection_lift_pct=35",
                 "expected_status": 200,
                 "expected_response_fields": ["annual_warranty_savings_usd", "total_annual_savings_usd"]},
                {"method": "GET", "path": "/api/alerts", "expected_status": 200},
                {"method": "GET", "path": "/api/reports/executive?format=json", "expected_status": 200},
            ],
        },
        {
            "scenario_name": "Vehicle Drill-Down with Prediction",
            "description": "Operator investigates a specific flagged vehicle",
            "api_calls": [
                {"method": "GET", "path": "/api/vehicles/VIN-0001?window=60",
                 "expected_status": 200,
                 "expected_response_fields": ["vin", "telemetry", "prediction", "drift"]},
                {"method": "POST", "path": "/api/alerts/1/ack", "expected_status": 200},
            ],
        },
        {
            "scenario_name": "A/B Model Comparison",
            "description": "Data scientist evaluates model performance and adjusts split",
            "api_calls": [
                {"method": "GET", "path": "/api/models", "expected_status": 200,
                 "expected_response_fields": ["models", "active"]},
                {"method": "PATCH", "path": "/api/models/ab_split",
                 "body": {"baseline_v1": 0.3, "ewma_plus_v2": 0.7},
                 "expected_status": 200},
                {"method": "POST", "path": "/api/models/activate",
                 "body": {"version": "ewma_plus_v2"},
                 "expected_status": 200},
            ],
        },
        {
            "scenario_name": "Customer Feedback and Retraining Loop",
            "description": "Field engineer submits feedback triggering model retraining",
            "api_calls": [
                {"method": "POST", "path": "/api/feedback",
                 "body": {"vin": "VIN-0005", "subsystem": "battery_thermal",
                          "label": "true_positive", "notes": "Confirmed pump degradation"},
                 "expected_status": 200},
                {"method": "POST", "path": "/api/feedback",
                 "body": {"vin": "VIN-0012", "subsystem": "battery_thermal",
                          "label": "false_positive", "notes": "Sensor was replaced, readings normal"},
                 "expected_status": 200},
                {"method": "POST", "path": "/api/feedback/retrain",
                 "body": {"new_version": "ewma_plus_v2.1"},
                 "expected_status": 200,
                 "expected_response_fields": ["version", "samples_incorporated"]},
            ],
        },
        {
            "scenario_name": "Configuration Hot-Update Under Load",
            "description": "Platform admin adjusts thresholds while fleet is actively monitored",
            "api_calls": [
                {"method": "GET", "path": "/api/config", "expected_status": 200},
                {"method": "PATCH", "path": "/api/config",
                 "body": {"drift_warn_score": 0.40, "drift_critical_score": 0.70,
                          "failure_warn_prob": 0.30, "failure_critical_prob": 0.60},
                 "expected_status": 200},
                {"method": "GET", "path": "/api/fleet", "expected_status": 200,
                 "validation": "verify vehicles re-evaluated with new thresholds"},
                {"method": "PATCH", "path": "/api/config",
                 "body": {"drift_warn_score": 0.45, "drift_critical_score": 0.75},
                 "expected_status": 200,
                 "validation": "restore defaults"},
            ],
        },
    ]

    payload = {
        "test_type": "api_integration_scenarios",
        "num_scenarios": len(scenarios),
        "generated_at": "2026-06-11T18:30:00Z",
        "scenarios": scenarios,
    }

    filepath = os.path.join(OUTPUT_DIR, "api_scenarios.json")
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"  [5/5] API scenarios: {len(scenarios)} scenarios -> {filepath}")
    return len(scenarios)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("HPC Predictive Quality Platform - Test Data Generator")
    print("=" * 70)
    ensure_output_dir()

    total = 0
    total += generate_telemetry_dataset(num_vehicles=55, steps_per_vehicle=200)
    total += generate_edge_cases()
    total += generate_fleet_load_test(num_vehicles=500)
    total += generate_drift_sequences(num_sequences=20, steps=500)
    total += generate_api_scenarios()

    print(f"\n{'=' * 70}")
    print(f"Total test data records generated: {total:,}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
