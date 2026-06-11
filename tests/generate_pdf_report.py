"""Generate a professional PDF analysis report for the HPC Predictive Quality Platform.

This script produces a polished PDF with:
- Professional layout, headers, footers, page numbers
- Embedded charts and diagrams (matplotlib-generated)
- Tables with proper formatting
- Color scheme and typography

Output: test_data/HPC_Test_Analysis_Report.pdf
"""

import os
import io
import math
import tempfile
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether, ListFlowable, ListItem,
    NextPageTemplate, PageTemplate, Frame
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

# --- Color Scheme ---
PRIMARY = HexColor('#1B3A5C')       # Dark navy
SECONDARY = HexColor('#2E86AB')     # Teal blue
ACCENT = HexColor('#A23B72')        # Berry/magenta
SUCCESS = HexColor('#2D8659')       # Green
WARNING = HexColor('#D4A029')       # Amber
DANGER = HexColor('#C0392B')        # Red
LIGHT_BG = HexColor('#F4F7FA')      # Light gray-blue
TABLE_HEADER = HexColor('#1B3A5C')
TABLE_ROW_ALT = HexColor('#EDF2F7')
TEXT_COLOR = HexColor('#2D3748')
MUTED = HexColor('#718096')

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_data")
PDF_PATH = os.path.join(OUTPUT_DIR, "HPC_Test_Analysis_Report.pdf")


# --- Chart Generation ---

def create_architecture_diagram():
    """Create platform architecture flow diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(7.5, 3))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis('off')

    boxes = [
        (0.5, 1.5, 'CAN-Bus\nTelemetry\n(7 signals)', '#2E86AB'),
        (2.5, 1.5, 'Feature\nExtraction\n(Residuals)', '#3498DB'),
        (4.5, 1.5, 'Drift\nDetection\n(EWMA)', '#A23B72'),
        (6.5, 1.5, 'Failure\nPrediction\n(Logistic)', '#C0392B'),
        (8.5, 1.5, 'Alert\nEngine\n(Dedup)', '#D4A029'),
    ]

    for x, y, text, color in boxes:
        rect = FancyBboxPatch((x, y), 1.6, 1.8, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='white', alpha=0.85)
        ax.add_patch(rect)
        ax.text(x + 0.8, y + 0.9, text, ha='center', va='center',
                fontsize=8, color='white', fontweight='bold')

    for i in range(len(boxes) - 1):
        ax.annotate('', xy=(boxes[i+1][0], 2.4),
                   xytext=(boxes[i][0] + 1.6, 2.4),
                   arrowprops=dict(arrowstyle='->', lw=2, color='#2D3748'))

    ax.text(5, 3.7, 'HPC Predictive Quality Platform — Data Pipeline',
            ha='center', va='center', fontsize=11, fontweight='bold', color='#1B3A5C')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()
    buf.seek(0)
    return buf


def create_drift_score_chart():
    """Create drift score over time for different scenarios."""
    fig, ax = plt.subplots(1, 1, figsize=(7, 4))

    time = np.linspace(0, 30, 100)

    # Nominal
    nominal = 0.08 + 0.04 * np.sin(time * 0.5) + np.random.normal(0, 0.02, 100)
    nominal = np.clip(nominal, 0, 0.25)

    # Pump degradation
    pump = np.where(time < 5, 0.05, 0.05 + (time - 5) * 0.035)
    pump += np.random.normal(0, 0.02, 100)
    pump = np.clip(pump, 0, 1.2)

    # Cell imbalance
    cell = np.where(time < 5, 0.04, 0.04 + (time - 5) * 0.030)
    cell += np.random.normal(0, 0.025, 100)
    cell = np.clip(cell, 0, 1.1)

    # Sensor bias
    sensor = np.where(time < 5, 0.03, 0.03 + (time - 5) * 0.020)
    sensor += np.random.normal(0, 0.015, 100)
    sensor = np.clip(sensor, 0, 0.8)

    ax.plot(time, nominal, color='#2D8659', linewidth=2, label='Nominal')
    ax.plot(time, pump, color='#C0392B', linewidth=2, label='Coolant Pump Degrading')
    ax.plot(time, cell, color='#A23B72', linewidth=2, label='Cell Imbalance')
    ax.plot(time, sensor, color='#D4A029', linewidth=2, label='Sensor Bias')

    ax.axhline(y=0.45, color='#D4A029', linestyle='--', alpha=0.7, label='WARN Threshold')
    ax.axhline(y=0.75, color='#C0392B', linestyle='--', alpha=0.7, label='CRITICAL Threshold')

    ax.axvline(x=5, color='gray', linestyle=':', alpha=0.5)
    ax.text(5.2, 0.02, 'Fault Onset', fontsize=8, color='gray')

    ax.set_xlabel('Time (minutes)', fontsize=10)
    ax.set_ylabel('Drift Score', fontsize=10)
    ax.set_title('Drift Score Progression by Failure Scenario', fontsize=12, fontweight='bold', color='#1B3A5C')
    ax.legend(loc='upper left', fontsize=8)
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#FAFBFC')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def create_failure_probability_chart():
    """Create failure probability over time with confidence intervals."""
    fig, ax = plt.subplots(1, 1, figsize=(7, 4))

    time = np.linspace(0, 55, 150)
    onset = 10

    prob = np.where(time < onset, 0.02 + 0.01 * np.random.randn(150),
                    1 / (1 + np.exp(-(time - onset - 20) * 0.2)))
    prob = np.clip(prob, 0, 1)

    ci_width = 0.05 + 0.08 * prob * (1 - prob)
    ci_low = np.clip(prob - ci_width, 0, 1)
    ci_high = np.clip(prob + ci_width, 0, 1)

    ax.fill_between(time, ci_low, ci_high, alpha=0.2, color='#2E86AB', label='95% CI')
    ax.plot(time, prob, color='#1B3A5C', linewidth=2.5, label='Failure Probability')

    ax.axhline(y=0.35, color='#D4A029', linestyle='--', linewidth=1.5, label='WARN (0.35)')
    ax.axhline(y=0.65, color='#C0392B', linestyle='--', linewidth=1.5, label='CRITICAL (0.65)')
    ax.axvline(x=onset, color='gray', linestyle=':', alpha=0.6)
    ax.text(onset + 0.5, 0.95, 'Fault Onset', fontsize=8, color='gray', rotation=90, va='top')

    ax.set_xlabel('Time (minutes)', fontsize=10)
    ax.set_ylabel('Failure Probability', fontsize=10)
    ax.set_title('Failure Probability with Confidence Interval\n(Coolant Pump Degradation)', fontsize=11, fontweight='bold', color='#1B3A5C')
    ax.legend(loc='lower right', fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#FAFBFC')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def create_scenario_distribution_pie():
    """Pie chart of test scenario distribution."""
    fig, ax = plt.subplots(1, 1, figsize=(5, 4))

    labels = ['Nominal (55%)', 'Coolant Pump (18%)', 'Cell Imbalance (15%)', 'Sensor Bias (12%)']
    sizes = [55, 18, 15, 12]
    colors_list = ['#2D8659', '#C0392B', '#A23B72', '#D4A029']
    explode = (0.02, 0.05, 0.05, 0.05)

    wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=labels,
                                       colors=colors_list, autopct='%1.0f%%',
                                       shadow=False, startangle=90,
                                       textprops={'fontsize': 9})
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')

    ax.set_title('Test Data Scenario Distribution', fontsize=11, fontweight='bold', color='#1B3A5C')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def create_performance_bar_chart():
    """Bar chart of API performance benchmarks."""
    fig, ax = plt.subplots(1, 1, figsize=(7, 3.5))

    endpoints = ['/health', '/fleet', '/vehicles', '/config', '/models', '/retrain', '/case_study']
    p50 = [5, 100, 50, 20, 30, 200, 500]
    p95 = [10, 300, 150, 50, 80, 500, 1500]
    p99 = [20, 500, 300, 100, 150, 1000, 3000]

    x = np.arange(len(endpoints))
    width = 0.25

    bars1 = ax.bar(x - width, p50, width, label='p50', color='#2D8659', alpha=0.85)
    bars2 = ax.bar(x, p95, width, label='p95', color='#D4A029', alpha=0.85)
    bars3 = ax.bar(x + width, p99, width, label='p99', color='#C0392B', alpha=0.85)

    ax.set_xlabel('API Endpoint', fontsize=10)
    ax.set_ylabel('Response Time (ms)', fontsize=10)
    ax.set_title('API Response Time Targets by Percentile', fontsize=11, fontweight='bold', color='#1B3A5C')
    ax.set_xticks(x)
    ax.set_xticklabels(endpoints, fontsize=8, rotation=15)
    ax.legend(fontsize=9)
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_facecolor('#FAFBFC')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def create_confusion_matrix_diagram():
    """Create a visual confusion matrix."""
    fig, ax = plt.subplots(1, 1, figsize=(4.5, 3.5))
    ax.axis('off')

    matrix = np.array([[87, 4], [3, 106]])
    im = ax.imshow(matrix, cmap='Blues', alpha=0.7)

    labels = [['TP\n87', 'FN\n4'], ['FP\n3', 'TN\n106']]
    for i in range(2):
        for j in range(2):
            color = 'white' if matrix[i, j] > 50 else '#1B3A5C'
            ax.text(j, i, labels[i][j], ha='center', va='center',
                   fontsize=14, fontweight='bold', color=color)

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(['Predicted\nFault', 'Predicted\nNo Fault'], fontsize=9)
    ax.set_yticklabels(['Actual\nFault', 'Actual\nNo Fault'], fontsize=9)
    ax.set_title('Example Confusion Matrix\n(Expected Results)', fontsize=11,
                fontweight='bold', color='#1B3A5C')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


def create_residual_heatmap():
    """Create a heatmap showing residuals over time for multiple vehicles."""
    fig, ax = plt.subplots(1, 1, figsize=(7, 3.5))

    np.random.seed(42)
    n_vehicles = 12
    n_steps = 50
    data = np.zeros((n_vehicles, n_steps))

    # Nominal vehicles (0-5)
    for i in range(6):
        data[i] = np.random.normal(0, 0.3, n_steps)

    # Fault vehicles (6-11) with progressive residual
    for i in range(6, 12):
        onset = 15
        for j in range(n_steps):
            if j < onset:
                data[i, j] = np.random.normal(0, 0.3)
            else:
                data[i, j] = (j - onset) * 0.15 + np.random.normal(0, 0.4)

    im = ax.imshow(data, aspect='auto', cmap='RdYlBu_r', vmin=-2, vmax=8,
                   interpolation='nearest')
    ax.set_xlabel('Time Step', fontsize=10)
    ax.set_ylabel('Vehicle Index', fontsize=10)
    ax.set_title('Residual Heatmap: Nominal (0–5) vs Fault (6–11)', fontsize=11,
                fontweight='bold', color='#1B3A5C')
    ax.axhline(y=5.5, color='white', linewidth=2, linestyle='--')
    ax.text(25, 2.5, 'NOMINAL', ha='center', fontsize=9, color='white', fontweight='bold')
    ax.text(25, 8.5, 'FAULT', ha='center', fontsize=9, color='white', fontweight='bold')
    plt.colorbar(im, ax=ax, label='Residual (°C)')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    buf.seek(0)
    return buf


# --- PDF Page Templates ---

class NumberedCanvas(canvas.Canvas):
    """Custom canvas that adds page numbers and headers."""

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        page_num = len(self._saved_page_states)
        # Footer
        self.setFont("Helvetica", 8)
        self.setFillColor(MUTED)
        self.drawString(72, 30, "HPC Predictive Quality Platform — Test Data & Analysis Report")
        self.drawRightString(A4[0] - 72, 30, f"Page {page_num} of {page_count}")
        # Header line
        if page_num > 1:
            self.setStrokeColor(HexColor('#E2E8F0'))
            self.setLineWidth(0.5)
            self.line(72, A4[1] - 50, A4[0] - 72, A4[1] - 50)


# --- Styles ---

def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='DocTitle',
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name='DocSubtitle',
        fontName='Helvetica',
        fontSize=13,
        textColor=SECONDARY,
        alignment=TA_CENTER,
        spaceAfter=20,
    ))
    styles.add(ParagraphStyle(
        name='H1',
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=PRIMARY,
        spaceBefore=20,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name='H2',
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=SECONDARY,
        spaceBefore=14,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name='H3',
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=TEXT_COLOR,
        spaceBefore=10,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name='BodyText2',
        fontName='Helvetica',
        fontSize=11,
        textColor=TEXT_COLOR,
        leading=15,
        spaceAfter=8,
        alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        name='Caption',
        fontName='Helvetica-Oblique',
        fontSize=9,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name='BulletText',
        fontName='Helvetica',
        fontSize=11,
        textColor=TEXT_COLOR,
        leading=15,
        leftIndent=20,
        spaceAfter=4,
    ))
    return styles


# --- Table Helper ---

def make_table(data, col_widths=None):
    """Create a styled table."""
    t = Table(data, colWidths=col_widths)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_COLOR),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, TABLE_ROW_ALT]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(style))
    return t


# --- Build PDF ---

def build_pdf():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    doc = SimpleDocTemplate(
        PDF_PATH,
        pagesize=A4,
        rightMargin=60,
        leftMargin=60,
        topMargin=65,
        bottomMargin=55,
    )

    styles = get_styles()
    story = []

    # === COVER PAGE ===
    story.append(Spacer(1, 80))
    story.append(Paragraph("HPC Predictive Quality Platform", styles['DocTitle']))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Test Data & Analysis Report", styles['DocTitle']))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Battery Thermal Management Subsystem", styles['DocSubtitle']))
    story.append(Spacer(1, 40))
    story.append(HRFlowable(width="60%", thickness=2, color=SECONDARY))
    story.append(Spacer(1, 30))

    meta_data = [
        ['Document Version', '1.0'],
        ['Date', 'June 11, 2026'],
        ['System Under Test', 'HPC Predictive Quality Platform (POC)'],
        ['Subsystem', 'Battery Thermal Management'],
        ['Prepared For', 'QA / Engineering Review'],
        ['Classification', 'Internal — Engineering'],
    ]
    meta_table = Table(meta_data, colWidths=[150, 280])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (-1, -1), TEXT_COLOR),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('LEFTPADDING', (1, 0), (1, -1), 15),
    ]))
    story.append(meta_table)
    story.append(PageBreak())

    # === TABLE OF CONTENTS ===
    story.append(Paragraph("Table of Contents", styles['H1']))
    story.append(Spacer(1, 10))
    toc_items = [
        "1. Executive Summary",
        "2. Platform Architecture & Identification",
        "3. Test Dataset Breakdown",
        "4. Expected Outcomes by Scenario",
        "5. Analysis Methodology",
        "6. Performance Benchmarks",
        "7. Visual Result Patterns",
        "8. Troubleshooting Guide",
        "9. Recommendations for Interpreting Results",
        "Appendix A: File Manifest",
        "Appendix B: Reproducing Test Data",
    ]
    for item in toc_items:
        story.append(Paragraph(f"• {item}", styles['BulletText']))
    story.append(PageBreak())

    # === 1. EXECUTIVE SUMMARY ===
    story.append(Paragraph("1. Executive Summary", styles['H1']))
    story.append(Paragraph(
        "This document provides a comprehensive testing methodology and analysis framework for the "
        "<b>HPC-Driven Predictive Quality Platform</b> — a SaaS-style predictive failure-detection "
        "system for EV battery thermal management. The platform ingests real-time CAN-bus telemetry "
        "from vehicle fleets, runs EWMA-based drift detection, and predicts battery thermal failures "
        "before they escalate to warranty claims.",
        styles['BodyText2']
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Testing Scope", styles['H2']))
    scope_data = [
        ['Area', 'Coverage'],
        ['Telemetry Ingestion', '10,780 synthetic records across 55 vehicles'],
        ['Edge Cases', '70 boundary/invalid/injection test inputs'],
        ['Fleet Load Testing', '500-vehicle concurrent fleet simulation'],
        ['Drift Detection', '9,420 sequential time-series records (20 × 500 steps)'],
        ['API Integration', '5 end-to-end production scenarios (15+ API calls)'],
        ['Total Test Records', '20,595+'],
    ]
    story.append(make_table(scope_data, col_widths=[140, 320]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Key Metrics Targeted", styles['H2']))
    metrics_bullets = [
        "<b>Detection accuracy:</b> True positive rate for fault identification (target > 90%)",
        "<b>Detection latency:</b> Time between fault onset and first WARN alert (target < 5 min)",
        "<b>False positive rate:</b> Healthy vehicles incorrectly flagged (target < 5%)",
        "<b>API response time:</b> < 500ms for fleet endpoint under full load",
        "<b>Memory footprint:</b> < 256MB for 500-vehicle fleet state",
    ]
    for bullet in metrics_bullets:
        story.append(Paragraph(f"• {bullet}", styles['BulletText']))
    story.append(PageBreak())

    # === 2. PLATFORM ARCHITECTURE ===
    story.append(Paragraph("2. Platform Architecture & Identification", styles['H1']))
    story.append(Paragraph(
        "The HPC Predictive Quality Platform processes battery telemetry through a multi-stage "
        "pipeline. Each stage progressively refines raw sensor data into actionable failure predictions "
        "with confidence intervals and time-to-failure estimates.",
        styles['BodyText2']
    ))
    story.append(Spacer(1, 8))

    # Architecture diagram
    arch_buf = create_architecture_diagram()
    story.append(Image(arch_buf, width=7*inch, height=2.8*inch))
    story.append(Paragraph("Figure 1: Platform data pipeline — from CAN-bus telemetry through drift detection to alert generation", styles['Caption']))

    story.append(Paragraph("Input Specification", styles['H2']))
    input_data = [
        ['Signal', 'Range', 'Unit', 'Source'],
        ['pack_temp_c', '18–80', '°C', 'Pack thermistor'],
        ['max_cell_temp_c', '20–85', '°C', 'Per-cell max'],
        ['coolant_delta_c', '1.5–25', '°C', 'Inlet-outlet diff'],
        ['coolant_flow_lpm', '0.5–13.0', 'L/min', 'Flow sensor'],
        ['current_a', '0–300', 'A', 'Pack BMS'],
        ['pack_voltage_v', '320–420', 'V', 'Pack bus'],
        ['soc_pct', '5–100', '%', 'Coulomb counter'],
    ]
    story.append(make_table(input_data, col_widths=[120, 70, 55, 130]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Output Specification", styles['H2']))
    output_data = [
        ['Output', 'Type', 'Range', 'Description'],
        ['Drift Score', 'float', '0.0 – 1.2+', 'EWMA-normalized deviation magnitude'],
        ['Failure Probability', 'float', '0.0 – 1.0', 'Logistic model output'],
        ['Confidence Interval', 'tuple', '(ci_low, ci_high)', 'Epistemic uncertainty band'],
        ['Time to Failure', 'float', '0.5 – 72.0 hours', 'Heuristic horizon estimate'],
        ['Alert Severity', 'enum', 'healthy/warning/critical', 'Threshold-based classification'],
    ]
    story.append(make_table(output_data, col_widths=[110, 50, 100, 185]))
    story.append(PageBreak())

    # === 3. TEST DATASET BREAKDOWN ===
    story.append(Paragraph("3. Test Dataset Breakdown", styles['H1']))

    # Scenario distribution chart
    pie_buf = create_scenario_distribution_pie()
    story.append(Image(pie_buf, width=4.5*inch, height=3.6*inch))
    story.append(Paragraph("Figure 2: Distribution of failure scenarios across the test fleet (55 vehicles)", styles['Caption']))

    story.append(Paragraph("Dataset 1: telemetry_dataset.csv (10,780 records)", styles['H2']))
    story.append(Paragraph(
        "Validates the full telemetry pipeline from raw signal ingestion through feature extraction. "
        "Each record contains actual sensor readings, HPC digital-twin expected values, and computed "
        "residuals across 28 columns.",
        styles['BodyText2']
    ))
    ds1_data = [
        ['Characteristic', 'Value'],
        ['Vehicles', '55'],
        ['Steps per vehicle', '200'],
        ['Time resolution', '30s per step'],
        ['Simulated time', '100 min/vehicle'],
        ['Total columns', '28 (IDs + 7 actual + 7 expected + 4 residuals + flags)'],
    ]
    story.append(make_table(ds1_data, col_widths=[140, 320]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Dataset 2: edge_cases.csv (70 records)", styles['H2']))
    story.append(Paragraph(
        "Tests boundary conditions, invalid inputs, and security attack vectors. Ensures the "
        "platform handles extreme values gracefully without crashes or data corruption.",
        styles['BodyText2']
    ))
    ds2_data = [
        ['Category', 'Count', 'Examples'],
        ['Boundary values', '47', 'Temps at exact warn/critical thresholds'],
        ['Invalid inputs', '19', 'NaN, Inf, null, negative, SQL injection, XSS'],
        ['State transitions', '4', 'Sudden fault onset / recovery'],
    ]
    story.append(make_table(ds2_data, col_widths=[120, 60, 280]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Dataset 3: fleet_load_test.json (500 vehicles)", styles['H2']))
    story.append(Paragraph(
        "Large-scale fleet payload for API load testing and memory management validation. "
        "Includes vehicles distributed across 5 regions and 4 model years.",
        styles['BodyText2']
    ))

    story.append(Paragraph("Dataset 4: drift_sequences.csv (9,420 records)", styles['H2']))
    story.append(Paragraph(
        "Extended time-series for validating drift detection timing and failure prediction accuracy. "
        "20 sequences (5 per scenario) with 500 steps each, providing continuous tracking of "
        "drift score evolution from fault onset through critical alert.",
        styles['BodyText2']
    ))

    story.append(Paragraph("Dataset 5: api_scenarios.json (5 scenarios)", styles['H2']))
    story.append(Paragraph(
        "End-to-end integration testing payloads that mirror production workflows including "
        "dashboard loading, vehicle drill-down, A/B testing, feedback loops, and live configuration updates.",
        styles['BodyText2']
    ))
    ds5_data = [
        ['Scenario', 'Simulates', 'API Calls'],
        ['Fleet Dashboard Load', 'Operator viewing full fleet', '4'],
        ['Vehicle Drill-Down', 'Investigating flagged vehicle', '2'],
        ['A/B Model Comparison', 'Data scientist adjusting split', '3'],
        ['Feedback & Retrain', 'Field engineer feedback loop', '3'],
        ['Config Hot-Update', 'Admin adjusting live thresholds', '4'],
    ]
    story.append(make_table(ds5_data, col_widths=[140, 200, 70]))
    story.append(PageBreak())

    # === 4. EXPECTED OUTCOMES ===
    story.append(Paragraph("4. Expected Outcomes by Scenario", styles['H1']))

    # Drift score chart
    drift_buf = create_drift_score_chart()
    story.append(Image(drift_buf, width=6.5*inch, height=3.7*inch))
    story.append(Paragraph("Figure 3: Expected drift score progression by failure scenario over 30 minutes", styles['Caption']))

    story.append(Paragraph("4.1 Coolant Pump Degrading", styles['H2']))
    story.append(Paragraph(
        "Pump health degrades at 1.2% per minute post-onset. Coolant flow drops from 12.0 to ~7.7 L/min "
        "over 30 minutes. The resulting thermal imbalance drives drift score from 0.05 to 0.88. "
        "<b>Expected:</b> First WARN alert at ~15 min post-onset; CRITICAL at ~25 min.",
        styles['BodyText2']
    ))

    story.append(Paragraph("4.2 Cell Imbalance", styles['H2']))
    story.append(Paragraph(
        "Cell balance factor degrades at 1.0% per minute. Max-cell temperature diverges from pack average "
        "by up to 7.9°C. Detection is slightly slower than pump due to subtler signal. "
        "<b>Expected:</b> WARN at ~20 min post-onset.",
        styles['BodyText2']
    ))

    story.append(Paragraph("4.3 Sensor Bias", styles['H2']))
    story.append(Paragraph(
        "Sensor reports lower-than-actual temperatures (growing at 0.08°C/min). The platform must detect "
        "this hidden fault through indirect signals (coolant ΔT residual). Latent pump degradation also "
        "contributes. <b>Expected:</b> WARN at ~25 min post-onset (slowest detection).",
        styles['BodyText2']
    ))

    story.append(Paragraph("4.4 Nominal (No Fault)", styles['H2']))
    story.append(Paragraph(
        "Drift score remains below 0.2 throughout. Failure probability stays under 0.15. "
        "<b>Pass Criteria:</b> No alerts generated; fewer than 5% of steps exceed warn threshold due to noise.",
        styles['BodyText2']
    ))

    # Failure probability chart
    story.append(Spacer(1, 10))
    prob_buf = create_failure_probability_chart()
    story.append(Image(prob_buf, width=6.5*inch, height=3.7*inch))
    story.append(Paragraph("Figure 4: Failure probability with 95% confidence interval (coolant pump degradation scenario)", styles['Caption']))
    story.append(PageBreak())

    # === 5. ANALYSIS METHODOLOGY ===
    story.append(Paragraph("5. Analysis Methodology", styles['H1']))

    story.append(Paragraph("5.1 Metrics to Track", styles['H2']))
    metrics_data = [
        ['Metric', 'Formula', 'Target'],
        ['True Positive Rate (TPR)', 'TP / (TP + FN)', '> 0.90'],
        ['False Positive Rate (FPR)', 'FP / (FP + TN)', '< 0.05'],
        ['Precision', 'TP / (TP + FP)', '> 0.85'],
        ['F1 Score', '2 × (P×R)/(P+R)', '> 0.87'],
        ['Detection Latency', 't(first_warn) - t(fault_onset)', '< 300s'],
        ['TTF Accuracy', 'MAE(predicted_TTF - actual)', '< 4 hours'],
        ['AUC-ROC', 'Area under ROC curve', '> 0.85'],
    ]
    story.append(make_table(metrics_data, col_widths=[140, 180, 80]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("5.2 Success Criteria Matrix", styles['H2']))
    criteria_data = [
        ['Test Category', 'Pass', 'Marginal', 'Fail'],
        ['Drift detection latency', '< 5 min', '5–10 min', '> 10 min'],
        ['False positive rate', '< 3%', '3–8%', '> 8%'],
        ['API response (fleet)', '< 300ms', '300–500ms', '> 500ms'],
        ['Memory (500 vehicles)', '< 128MB', '128–256MB', '> 256MB'],
        ['CI calibration', '≥ 95% coverage', '90–95%', '< 90%'],
    ]
    story.append(make_table(criteria_data, col_widths=[130, 100, 100, 100]))
    story.append(Spacer(1, 12))

    # Confusion matrix
    cm_buf = create_confusion_matrix_diagram()
    story.append(Image(cm_buf, width=4*inch, height=3.1*inch))
    story.append(Paragraph("Figure 5: Expected confusion matrix for fault detection (based on 200-vehicle test fleet)", styles['Caption']))

    story.append(Paragraph("5.3 Anomaly Detection Methods", styles['H2']))
    methods = [
        "<b>Statistical Process Control (SPC):</b> Track drift_score mean ± 3σ per scenario. "
        "Anomaly = score outside 3σ for nominal vehicles.",
        "<b>Residual Trend Analysis:</b> Fit linear regression to residuals; positive slope > 0.01°C/step "
        "for pack_temp indicates degradation.",
        "<b>Confidence Interval Validation:</b> Verify that ci_low ≤ probability ≤ ci_high in > 95% of predictions.",
        "<b>Temporal Consistency:</b> Drift score should be monotonically non-decreasing once a fault is active "
        "(allowing for small noise fluctuations).",
    ]
    for i, method in enumerate(methods, 1):
        story.append(Paragraph(f"{i}. {method}", styles['BulletText']))
    story.append(PageBreak())

    # === 6. PERFORMANCE BENCHMARKS ===
    story.append(Paragraph("6. Performance Benchmarks", styles['H1']))

    perf_buf = create_performance_bar_chart()
    story.append(Image(perf_buf, width=6.5*inch, height=3.2*inch))
    story.append(Paragraph("Figure 6: API response time targets by percentile (logarithmic scale)", styles['Caption']))

    story.append(Paragraph("API Endpoint Targets", styles['H2']))
    api_data = [
        ['Endpoint', 'Method', 'p50', 'p95', 'p99'],
        ['/api/health', 'GET', '5ms', '10ms', '20ms'],
        ['/api/fleet', 'GET', '100ms', '300ms', '500ms'],
        ['/api/vehicles/<vin>', 'GET', '50ms', '150ms', '300ms'],
        ['/api/config', 'PATCH', '20ms', '50ms', '100ms'],
        ['/api/models', 'GET', '30ms', '80ms', '150ms'],
        ['/api/feedback/retrain', 'POST', '200ms', '500ms', '1000ms'],
        ['/api/case_study', 'GET', '500ms', '1500ms', '3000ms'],
    ]
    story.append(make_table(api_data, col_widths=[130, 55, 60, 60, 60]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Throughput Targets", styles['H2']))
    throughput_data = [
        ['Scenario', 'Metric', 'Target'],
        ['Fleet ticks (25 vehicles)', 'Ticks/second', '> 10'],
        ['Fleet ticks (500 vehicles)', 'Ticks/second', '> 2'],
        ['Concurrent dashboard users', 'Connections', '> 50'],
        ['Alert generation rate', 'Alerts/second', '> 100'],
    ]
    story.append(make_table(throughput_data, col_widths=[180, 120, 100]))
    story.append(PageBreak())

    # === 7. VISUAL RESULT PATTERNS ===
    story.append(Paragraph("7. Visual Result Patterns", styles['H1']))
    story.append(Paragraph(
        "The following visualizations illustrate expected data patterns that should be observed "
        "when running the test datasets through the platform. Deviations from these patterns "
        "indicate potential issues requiring investigation.",
        styles['BodyText2']
    ))

    # Residual heatmap
    heatmap_buf = create_residual_heatmap()
    story.append(Image(heatmap_buf, width=6.5*inch, height=3.2*inch))
    story.append(Paragraph("Figure 7: Residual heatmap showing clear separation between nominal vehicles (indices 0–5) "
                           "and fault vehicles (indices 6–11) after fault onset", styles['Caption']))

    story.append(Paragraph("Expected Pattern Characteristics", styles['H2']))
    patterns = [
        "<b>Nominal region (top half):</b> Uniform blue/green noise centered at zero. No systematic drift.",
        "<b>Fault region (bottom half):</b> Progressive red divergence starting at step 15 (fault onset). "
        "Intensity correlates with time since onset.",
        "<b>Transition boundary:</b> Sharp demarcation at the onset step. Earlier steps should show "
        "identical noise patterns for both groups.",
        "<b>Cross-channel correlation:</b> Multiple residual channels should diverge simultaneously "
        "for pump failures; only max_cell_temp for cell imbalance.",
    ]
    for pattern in patterns:
        story.append(Paragraph(f"• {pattern}", styles['BulletText']))
    story.append(PageBreak())

    # === 8. TROUBLESHOOTING GUIDE ===
    story.append(Paragraph("8. Troubleshooting Guide", styles['H1']))

    story.append(Paragraph("Common Issues and Resolutions", styles['H2']))
    trouble_data = [
        ['Issue', 'Symptom', 'Resolution'],
        ['High FPR', '>8% nominal flagged', 'Increase drift_alpha to 0.20'],
        ['Slow detection', 'WARN >10 min after onset', 'Decrease drift_warn_score to 0.40'],
        ['Wide CIs', 'CI width > 0.4', 'Reduce epistemic_sigma'],
        ['Memory growth', 'RAM > 256MB (500 vehicles)', 'Cap samples_buffer at 30'],
        ['TTF inaccurate', 'MAE > 8 hours', 'Smooth residual_slope features'],
        ['Score oscillation', 'Bounces above/below threshold', 'Add hysteresis to alerts'],
        ['API timeout', 'GET /api/fleet > 1s', 'Move ticking to background thread'],
        ['Model mismatch', 'Wrong model serving', 'Verify set_active() propagation'],
    ]
    story.append(make_table(trouble_data, col_widths=[100, 150, 200]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Debugging Workflow", styles['H2']))
    debug_steps = [
        "<b>Identify:</b> Check which dataset/scenario exhibits unexpected behavior",
        "<b>Isolate:</b> Filter records by vehicle_id and scenario",
        "<b>Trace:</b> Follow the pipeline: raw signal → residual → drift → prediction",
        "<b>Compare:</b> Plot actual vs. expected (HPC twin) to find divergence point",
        "<b>Validate:</b> Confirm fault_active ground truth matches expected onset time",
    ]
    for i, step in enumerate(debug_steps, 1):
        story.append(Paragraph(f"{i}. {step}", styles['BulletText']))
    story.append(PageBreak())

    # === 9. RECOMMENDATIONS ===
    story.append(Paragraph("9. Recommendations for Interpreting Results", styles['H1']))

    story.append(Paragraph("Priority Order for Analysis", styles['H2']))
    priorities = [
        "<b>Start with nominal baseline:</b> Confirm < 5% FPR before evaluating fault scenarios",
        "<b>Validate detection ordering:</b> Pump should detect fastest, sensor bias slowest",
        "<b>Check confidence calibration:</b> Observed frequency should fall within CIs 95% of the time",
        "<b>Compare models:</b> ewma_plus_v2 should outperform baseline_v1 on latency and AUC",
        "<b>Stress test boundaries:</b> Edge cases should never crash the platform",
    ]
    for i, p in enumerate(priorities, 1):
        story.append(Paragraph(f"{i}. {p}", styles['BulletText']))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Red Flags to Watch For", styles['H2']))
    red_flags = [
        "⚠️ Drift score > 1.0 for nominal vehicles (detector saturation)",
        "⚠️ Failure probability jumps from < 0.1 to > 0.8 in one step (discontinuity)",
        "⚠️ TTF decreasing while probability is also decreasing (inconsistency)",
        "⚠️ CI_low > probability or CI_high < probability (math error)",
        "⚠️ Zero-flow readings not triggering immediate critical alert",
    ]
    for flag in red_flags:
        story.append(Paragraph(f"• {flag}", styles['BulletText']))
    story.append(Spacer(1, 15))

    story.append(Paragraph("Reporting Template", styles['H2']))
    story.append(Paragraph(
        "For each test run, document the following metrics to enable consistent comparison "
        "across iterations and model versions:",
        styles['BodyText2']
    ))
    template_data = [
        ['Field', 'Value', 'Target'],
        ['Run ID', '<auto-generated>', '—'],
        ['Fleet Size', '<N vehicles>', '≥ 25'],
        ['Duration', '<simulated minutes>', '≥ 60'],
        ['Model Version', '<active model>', '—'],
        ['TPR', '<value>', '> 0.90'],
        ['FPR', '<value>', '< 0.05'],
        ['Mean Detection Latency', '<seconds>', '< 300s'],
        ['API p95 Latency', '<ms>', '< 500ms'],
        ['Peak Memory', '<MB>', '< 256MB'],
    ]
    story.append(make_table(template_data, col_widths=[150, 140, 100]))
    story.append(PageBreak())

    # === APPENDIX A ===
    story.append(Paragraph("Appendix A: File Manifest", styles['H1']))
    manifest_data = [
        ['File', 'Format', 'Records', 'Size (approx)'],
        ['test_data/telemetry_dataset.csv', 'CSV', '10,780', '~3.5 MB'],
        ['test_data/edge_cases.csv', 'CSV', '70', '~8 KB'],
        ['test_data/fleet_load_test.json', 'JSON', '500 vehicles', '~350 KB'],
        ['test_data/drift_sequences.csv', 'CSV', '9,420', '~1.8 MB'],
        ['test_data/api_scenarios.json', 'JSON', '5 scenarios', '~6 KB'],
    ]
    story.append(make_table(manifest_data, col_widths=[180, 55, 85, 85]))
    story.append(Spacer(1, 20))

    # === APPENDIX B ===
    story.append(Paragraph("Appendix B: Reproducing Test Data", styles['H1']))
    story.append(Paragraph(
        "All test data is generated deterministically using fixed random seeds. To regenerate:",
        styles['BodyText2']
    ))
    story.append(Paragraph(
        "<font face='Courier' size='10'>python -m tests.generate_test_data</font>",
        styles['BulletText']
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "The generator produces identical output across runs, enabling reproducible testing "
        "and reliable comparison between platform versions.",
        styles['BodyText2']
    ))
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#CBD5E0')))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<i>End of Report — Generated June 11, 2026</i>",
        ParagraphStyle('EndNote', fontName='Helvetica-Oblique', fontSize=9,
                      textColor=MUTED, alignment=TA_CENTER)
    ))

    # Build
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generated: {PDF_PATH}")
    print(f"File size: {os.path.getsize(PDF_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    build_pdf()
