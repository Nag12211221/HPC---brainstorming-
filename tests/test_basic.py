"""Smoke tests for the HPC POC. Run with: ``python -m unittest discover tests``."""

import time
import unittest

from app.config import CONFIG
from app.models.drift_detector import DriftDetector
from app.models.failure_predictor import model_registry
from app.services.ab_testing import ABRouter
from app.services.case_study import run_case_study
from app.services.feedback import FeedbackStore
from app.services.fleet_manager import FleetManager
from app.services.roi_calculator import compute_roi
from app.subsystems import registry as subsystem_registry


class SubsystemTests(unittest.TestCase):
    def test_battery_thermal_step_produces_expected_signals(self):
        sub = subsystem_registry.get("battery_thermal")
        sub.reset("T1", seed=1)
        sample = sub.step("T1", dt=30.0)
        for sig in sub.signals:
            self.assertIn(sig, sample.actual)
            self.assertIn(sig, sample.expected)


class DriftAndModelTests(unittest.TestCase):
    def test_drift_score_is_finite(self):
        det = DriftDetector(alpha=0.2)
        score = det.update("V", {"residual_mean_max_cell_temp_c": 1.0})["score"]
        self.assertGreaterEqual(score, 0.0)

    def test_model_versions_predict_in_range(self):
        m = model_registry.get("ewma_plus_v2")
        out = m.predict({"residual_mean_max_cell_temp_c": 2.0,
                         "residual_slope_max_cell_temp_c": 0.1}, drift_score=0.6)
        self.assertGreaterEqual(out["probability"], 0.0)
        self.assertLessEqual(out["probability"], 1.0)
        self.assertLessEqual(out["ci_low"], out["probability"])
        self.assertGreaterEqual(out["ci_high"], out["probability"])


class ServiceTests(unittest.TestCase):
    def test_roi_savings_positive(self):
        roi = compute_roi(fleet_size=1000)
        self.assertGreater(roi["annual_warranty_savings_usd"], 0)
        self.assertGreater(roi["total_annual_savings_usd"], roi["annual_warranty_savings_usd"])

    def test_ab_router_split_is_deterministic(self):
        CONFIG.ab_traffic_split = {"a": 0.5, "b": 0.5}
        r = ABRouter()
        self.assertEqual(r.assign("VIN-1234"), r.assign("VIN-1234"))

    def test_feedback_retrain_marks_entries(self):
        fb = FeedbackStore()
        fb.submit("VIN-1", "battery_thermal", "true_positive", "ok")
        event = fb.trigger_retrain("ewma_plus_v2.1")
        self.assertEqual(event["samples_incorporated"], 1)
        entry = fb.list()[0]
        self.assertEqual(entry["incorporated_in_model"], "ewma_plus_v2.1")

    def test_case_study_runs_end_to_end(self):
        result = run_case_study("coolant_pump_degrading", horizon_minutes=60)
        self.assertIn("series", result)
        self.assertGreater(len(result["series"]), 10)
        self.assertIn("narrative", result)


class FleetIntegrationTest(unittest.TestCase):
    def test_fleet_manager_evaluates_after_a_few_ticks(self):
        sub = subsystem_registry.get("battery_thermal")
        # Use a fresh manager with a small fleet
        original_size = CONFIG.fleet_size
        CONFIG.fleet_size = 4
        try:
            mgr = FleetManager(sub)
            time.sleep(1.5)  # allow background ticker
            summary = mgr.summary()
            self.assertEqual(summary["fleet_size"], 4)
            vehicles = mgr.list_vehicles()
            self.assertEqual(len(vehicles), 4)
            mgr.stop()
        finally:
            CONFIG.fleet_size = original_size


if __name__ == "__main__":
    unittest.main()
