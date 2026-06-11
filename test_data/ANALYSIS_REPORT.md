# HPC Predictive Quality Platform — Test Data & Analysis Report

**Document Version:** 1.0  
**Date:** June 11, 2026  
**System Under Test:** HPC-Driven Predictive Quality Platform (Battery Thermal Management)  
**Prepared For:** QA / Engineering Review  

---

## Executive Summary

This document provides a comprehensive testing methodology and analysis framework for the **HPC-Driven Predictive Quality Platform** — a SaaS-style predictive failure-detection system for EV battery thermal management. The platform ingests real-time CAN-bus telemetry from vehicle fleets, runs EWMA-based drift detection, and predicts battery thermal failures before they escalate to warranty claims.

### Testing Scope

| Area | Coverage |
|------|----------|
| **Telemetry Ingestion** | 10,780 synthetic records across 55 vehicles |
| **Edge Cases** | 70 boundary/invalid/injection test inputs |
| **Fleet Load Testing** | 500-vehicle concurrent fleet simulation |
| **Drift Detection** | 9,420 sequential time-series records (20 sequences × 500 steps) |
| **API Integration** | 5 end-to-end production scenarios with 15+ API calls |
| **Total Test Records** | 20,595+ |

### Key Metrics Targeted

- **Detection accuracy**: True positive rate for fault identification
- **Detection latency**: Time between fault onset and first WARN alert
- **False positive rate**: Healthy vehicles incorrectly flagged
- **API response time**: < 500ms for fleet endpoint under full load
- **Memory footprint**: < 256MB for 500-vehicle fleet state

---

## 1. Tool/System Identification

### Platform Architecture

```
Telemetry → Feature Extraction → Drift Detection (EWMA) → Failure Prediction (Logistic)
     ↓              ↓                     ↓                        ↓
  CAN-bus      Residuals           Drift Score [0-1+]      Probability + CI + TTF
  7 signals   (actual-twin)        Threshold: 0.45/0.75    Threshold: 0.35/0.65
```

### Input Specification

| Signal | Range | Unit | Source |
|--------|-------|------|--------|
| `pack_temp_c` | 18–80°C | °C | Pack thermistor |
| `max_cell_temp_c` | 20–85°C | °C | Per-cell max |
| `coolant_delta_c` | 1.5–25°C | °C | Inlet-outlet diff |
| `coolant_flow_lpm` | 0.5–13.0 | L/min | Flow sensor |
| `current_a` | 0–300 | A | Pack BMS |
| `pack_voltage_v` | 320–420 | V | Pack bus |
| `soc_pct` | 5–100 | % | Coulomb counter |

### Output Specification

| Output | Type | Range |
|--------|------|-------|
| Drift Score | float | 0.0 – 1.2+ |
| Failure Probability | float | 0.0 – 1.0 |
| Confidence Interval | tuple | (ci_low, ci_high) |
| Time to Failure | float | 0.5 – 72.0 hours |
| Alert Severity | enum | healthy / warning / critical |

---

## 2. Test Dataset Breakdown

### Dataset 1: `telemetry_dataset.csv` (10,780 records)

**Purpose:** Validate the full telemetry pipeline from raw signal ingestion through feature extraction.

| Characteristic | Value |
|---------------|-------|
| Vehicles | 55 |
| Steps/vehicle | 200 |
| Time resolution | 30s per step |
| Simulated time | 100 min/vehicle |
| Scenarios | nominal (55%), coolant_pump (18%), cell_imbalance (15%), sensor_bias (12%) |

**Schema (28 columns):**
- Vehicle ID, scenario, timestamp, fault_active flag
- 7 actual sensor readings
- 7 HPC-twin expected values
- 4 computed residuals (pack_temp, max_cell_temp, coolant_delta, coolant_flow)

**Expected Analysis Pattern:**
- Nominal vehicles: residuals cluster around 0 ± 0.5°C noise
- Pump degradation: coolant_flow residual trends negative, coolant_delta rises monotonically
- Cell imbalance: max_cell_temp residual diverges from pack_temp residual
- Sensor bias: reported temps shift downward but coolant_delta still exposes the hidden fault

### Dataset 2: `edge_cases.csv` (70 records)

**Purpose:** Validate graceful handling of extreme, invalid, and malicious inputs.

| Category | Count | Examples |
|----------|-------|---------|
| Boundary values | 47 | Temps at warn/critical thresholds exactly |
| Invalid inputs | 19 | NaN, Inf, null, negative values, SQL injection, XSS |
| State transitions | 4 | Sudden fault onset/recovery |

**Success Criteria:**
- No unhandled exceptions or crashes
- Invalid inputs return appropriate error codes (400/422)
- Boundary values trigger correct severity classification
- Injection attempts are sanitized without data corruption

### Dataset 3: `fleet_load_test.json` (500 vehicles)

**Purpose:** Load testing the fleet API endpoint and memory management.

| Characteristic | Value |
|---------------|-------|
| Fleet size | 500 vehicles |
| Regions | 5 (NA-West, NA-East, EU-North, EU-South, APAC) |
| Model years | 2022–2025 |
| Status distribution | ~55% healthy, ~25% warning, ~20% critical |

**Performance Benchmarks:**

| Metric | Target | Acceptable |
|--------|--------|------------|
| GET /api/fleet response time | < 300ms | < 500ms |
| Memory usage (500 vehicles) | < 128MB | < 256MB |
| CPU usage during tick | < 20% | < 40% |
| Concurrent API calls (50 users) | < 500ms p95 | < 1000ms p99 |

### Dataset 4: `drift_sequences.csv` (9,420 records)

**Purpose:** Validate drift detection timing and failure prediction accuracy over extended time-series.

| Characteristic | Value |
|---------------|-------|
| Sequences | 20 (5 per scenario) |
| Steps/sequence | 500 |
| Warm-up window | 30 steps (drift needs history) |
| Effective records | 470 per sequence |
| Fault onset | t=50s simulated |

**Key Validation Metrics:**

| Metric | Target | Method |
|--------|--------|--------|
| Detection latency (pump) | < 5 minutes post-onset | First drift_score > 0.45 |
| Detection latency (imbalance) | < 7 minutes post-onset | First drift_score > 0.45 |
| Detection latency (sensor bias) | < 10 minutes post-onset | Via coolant_delta residual |
| False positive rate (nominal) | < 5% of steps | drift_score > 0.45 for nominal |
| Failure prob accuracy | AUC > 0.85 | Compare to fault_active ground truth |

### Dataset 5: `api_scenarios.json` (5 scenarios)

**Purpose:** End-to-end integration testing mirroring production workflows.

| Scenario | Simulates | API Calls |
|----------|-----------|-----------|
| Fleet Dashboard Load | Operator viewing 200-vehicle fleet | 4 |
| Vehicle Drill-Down | Investigating flagged vehicle | 2 |
| A/B Model Comparison | Data scientist adjusting model split | 3 |
| Feedback & Retrain | Field engineer feedback loop | 3 |
| Config Hot-Update | Admin adjusting live thresholds | 4 |

---

## 3. Expected Outcomes by Scenario

### 3.1 Coolant Pump Degrading

```
Time (min):   0     5     10    15    20    25    30
Pump Health:  1.0   0.94  0.88  0.82  0.76  0.70  0.64
Flow (L/min): 12.0  11.3  10.6  9.8   9.1   8.4   7.7
Drift Score:  0.05  0.15  0.30  0.48  0.62  0.75  0.88
Status:       OK    OK    OK    WARN  WARN  CRIT  CRIT
```

**Expected:** First WARN alert at ~15 min post-onset. CRITICAL at ~25 min.  
**Pass Criteria:** WARN triggers before pump_health drops below 0.70.

### 3.2 Cell Imbalance

```
Time (min):   0     5     10    15    20    25    30
Cell Balance: 1.0   0.95  0.90  0.85  0.80  0.75  0.70
Max Cell ΔT:  2.5   3.4   4.3   5.2   6.1   7.0   7.9
Drift Score:  0.03  0.12  0.25  0.40  0.52  0.65  0.78
```

**Expected:** Slower detection than pump (imbalance signal is subtler). WARN at ~20 min.

### 3.3 Sensor Bias

```
Time (min):   0     5     10    15    20    25    30
Sensor Bias:  0°C   0.4   0.8   1.2   1.6   2.0   2.4
Reported vs
  Actual gap: 0     0.4   0.8   1.2   1.6   2.0   2.4
Coolant ΔT
  residual:   0     0.1   0.2   0.3   0.5   0.7   0.9
```

**Expected:** Detection via indirect signal (coolant ΔT) since sensor underreports temps. Latent pump degradation contributes. WARN at ~25 min.

### 3.4 Nominal (No Fault)

**Expected:** Drift score remains < 0.2 throughout. Failure probability < 0.15.  
**Pass Criteria:** No alerts generated. < 5% of steps exceed warn threshold due to noise.

---

## 4. Analysis Methodology

### 4.1 Metrics to Track

| Metric | Formula | Target |
|--------|---------|--------|
| **True Positive Rate (TPR)** | TP / (TP + FN) | > 0.90 |
| **False Positive Rate (FPR)** | FP / (FP + TN) | < 0.05 |
| **Precision** | TP / (TP + FP) | > 0.85 |
| **F1 Score** | 2 × (P×R)/(P+R) | > 0.87 |
| **Detection Latency** | t(first_warn) - t(fault_onset) | < 300s |
| **Time to Failure Accuracy** | MAE(predicted_TTF - actual_TTF) | < 4 hours |
| **AUC-ROC** | Area under ROC curve | > 0.85 |

### 4.2 Success Criteria Matrix

| Test Category | Pass | Marginal | Fail |
|--------------|------|----------|------|
| Drift detection latency | < 5 min | 5–10 min | > 10 min |
| False positive rate | < 3% | 3–8% | > 8% |
| API response (fleet) | < 300ms | 300–500ms | > 500ms |
| Memory (500 vehicles) | < 128MB | 128–256MB | > 256MB |
| CI coverage | ≥ 0.05 width | — | width > 0.4 |

### 4.3 Anomaly Detection Methods

1. **Statistical Process Control (SPC):** Track drift_score mean ± 3σ per scenario. Anomaly = score outside 3σ for nominal vehicles.
2. **Residual Trend Analysis:** Fit linear regression to residuals; positive slope > 0.01 °C/step for pack_temp indicates degradation.
3. **Confidence Interval Validation:** Verify that `ci_low ≤ probability ≤ ci_high` in > 95% of predictions.
4. **Temporal Consistency:** Drift score should be monotonically non-decreasing once a fault is active (allowing for small noise fluctuations).

---

## 5. Performance Benchmarks

### API Endpoint Targets

| Endpoint | Method | Target (p50) | Target (p95) | Target (p99) |
|----------|--------|-------------|-------------|-------------|
| `/api/health` | GET | 5ms | 10ms | 20ms |
| `/api/fleet` | GET | 100ms | 300ms | 500ms |
| `/api/vehicles/<vin>` | GET | 50ms | 150ms | 300ms |
| `/api/config` | PATCH | 20ms | 50ms | 100ms |
| `/api/models` | GET | 30ms | 80ms | 150ms |
| `/api/feedback/retrain` | POST | 200ms | 500ms | 1000ms |
| `/api/case_study` | GET | 500ms | 1500ms | 3000ms |

### Throughput Targets

| Scenario | Metric | Target |
|----------|--------|--------|
| Fleet ticks (25 vehicles) | Ticks/second | > 10 |
| Fleet ticks (500 vehicles) | Ticks/second | > 2 |
| Concurrent dashboard users | Concurrent connections | > 50 |
| Alert generation rate | Alerts processed/second | > 100 |

---

## 6. Visual Result Patterns

### Expected Drift Score Distribution by Scenario

```
Score:  0.0   0.2   0.4   0.6   0.8   1.0   1.2
        |     |     |     |     |     |     |
Nominal ████████░░                              (mean=0.08, σ=0.06)
        |     |     |     |     |     |     |
Pump    ░░░░░░░░░░████████████████████████░░    (mean=0.55, σ=0.25)
        |     |     |     |     |     |     |
Cell    ░░░░░░░░░████████████████████░░░░░░     (mean=0.48, σ=0.22)
        |     |     |     |     |     |     |
Sensor  ░░░░░░░░░░░░░████████████████░░░░░      (mean=0.42, σ=0.20)
        |     |     |     |     |     |     |
        HEALTHY    WARN        CRITICAL
```

### Expected Failure Probability Over Time (Pump Degradation)

```
Prob
1.0 |                                          ╭──────
0.8 |                                     ╭────╯
0.6 |                               ╭─────╯  ← CRITICAL threshold
0.4 |                         ╭─────╯
0.35|........................╭╯.................. ← WARN threshold
0.2 |                  ╭─────╯
0.1 |        ╭─────────╯
0.0 |────────╯
    └──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──→ time
       0  5  10 15 20 25 30 35 40 45 50 55  (min)
                  ↑ fault onset
```

### Confusion Matrix Template (Per Run)

```
                     Predicted
                  Fault    No Fault
Actual Fault  │   TP    │    FN    │  → Recall = TP/(TP+FN)
              │─────────│──────────│
No Fault      │   FP    │    TN    │  → Specificity = TN/(TN+FP)
              └─────────┴──────────┘
                    ↓          ↓
              Precision    NPV
```

---

## 7. Troubleshooting Guide

### Common Issues and Resolutions

| Issue | Symptom | Root Cause | Resolution |
|-------|---------|------------|------------|
| High false positive rate | >8% of nominal vehicles flagged | Drift alpha too sensitive | Increase `drift_alpha` from 0.15 to 0.20 |
| Slow detection | WARN > 10 min after onset | Alpha too slow, or threshold too high | Decrease `drift_warn_score` from 0.45 to 0.40 |
| Confidence intervals too wide | CI width > 0.4 | High epistemic sigma | Reduce `epistemic_sigma` (needs more training data) |
| Memory growth | RAM > 256MB at 500 vehicles | Telemetry buffer unbounded | Verify `samples_buffer` is capped at 30 |
| TTF inaccurate | MAE > 8 hours | Slope signal noisy | Apply smoothing to `residual_slope_*` features |
| Drift score oscillation | Score bounces above/below threshold | Noisy features + low alpha | Increase window or add hysteresis to alerts |
| API timeout on fleet | GET /api/fleet > 1s | Fleet tick blocking API thread | Move fleet ticking to background thread |
| Model version mismatch | Wrong model serving predictions | A/B split not updated after activate | Verify `set_active()` propagates to ABRouter |

### Debugging Workflow

1. **Identify**: Check which dataset/scenario exhibits unexpected behavior
2. **Isolate**: Filter records by `vehicle_id` and `scenario`
3. **Trace**: Follow the pipeline: raw signal → residual → drift → prediction
4. **Compare**: Plot actual vs. expected (HPC twin) to find divergence point
5. **Validate**: Confirm fault_active ground truth matches expected onset time

---

## 8. Recommendations for Interpreting Results

### Priority Order for Analysis

1. **Start with nominal baseline**: Confirm < 5% FPR before evaluating fault scenarios
2. **Validate detection ordering**: Pump should detect fastest, sensor bias slowest
3. **Check confidence calibration**: Observed frequency should fall within CIs 95% of the time
4. **Compare models**: ewma_plus_v2 should outperform baseline_v1 on latency and AUC
5. **Stress test boundaries**: Edge cases should never crash the platform

### Red Flags to Watch For

- ⚠️ Drift score > 1.0 for nominal vehicles (detector saturation)
- ⚠️ Failure probability jumps from < 0.1 to > 0.8 in one step (discontinuity)
- ⚠️ TTF decreasing while probability is also decreasing (inconsistency)
- ⚠️ CI_low > probability or CI_high < probability (math error)
- ⚠️ Zero-flow readings not triggering immediate critical alert

### Reporting Template

For each test run, report:
```
Run ID:           <auto-generated>
Date:             <timestamp>
Fleet Size:       <N vehicles>
Duration:         <simulated minutes>
Model Version:    <active model>
A/B Split:        <baseline: X%, ewma: Y%>
─────────────────────────────────────────
TPR:              <value> (target > 0.90)
FPR:              <value> (target < 0.05)
Mean Detection Latency: <seconds> (target < 300s)
API p95 Latency:  <ms> (target < 500ms)
Peak Memory:      <MB> (target < 256MB)
Anomalies Found:  <count and descriptions>
```

---

## Appendix A: File Manifest

| File | Format | Records | Size (approx) |
|------|--------|---------|---------------|
| `test_data/telemetry_dataset.csv` | CSV | 10,780 | ~3.5 MB |
| `test_data/edge_cases.csv` | CSV | 70 | ~8 KB |
| `test_data/fleet_load_test.json` | JSON | 500 | ~350 KB |
| `test_data/drift_sequences.csv` | CSV | 9,420 | ~1.8 MB |
| `test_data/api_scenarios.json` | JSON | 5 scenarios | ~6 KB |

## Appendix B: Reproducing Test Data

```bash
# From repository root:
python -m tests.generate_test_data

# All outputs written to test_data/
```

The generator uses deterministic seeds, ensuring reproducibility across runs.

## Appendix C: Converting This Report to PDF

```bash
# Using pandoc:
pandoc test_data/ANALYSIS_REPORT.md -o test_data/ANALYSIS_REPORT.pdf \
  --pdf-engine=xelatex -V geometry:margin=1in

# Using Python (markdown2pdf):
pip install md2pdf
md2pdf test_data/ANALYSIS_REPORT.md test_data/ANALYSIS_REPORT.pdf

# Or simply print from browser:
# Open in any Markdown viewer → File → Print → Save as PDF
```

---

*End of Report*
