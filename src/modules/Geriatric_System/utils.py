"""
utils.py – Helper functions for the Geriatric System Module.
Covers: Frailty Index calculation, Morse risk classification, MMSE severity.
"""

"""
utils.py – Helper functions for the Geriatric System Module.
Version: 1.1.0
Last Updated: 2026-03-18
Author: D
"""

from database import get_collection
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# 1.0  Frailty Index (Process 1 – DFD)
# ─────────────────────────────────────────────────────────────────────────────

def calc_frailty_index(age: int, num_comorbidities: int, fall_history: bool, mmse_score: int) -> float:
    """
    Simplified Frailty Index (0.0 – 1.0).
    Based on 4 deficit components that mirror the ER + DFD data sources.
    """
    deficits = 0
    total = 4

    if age >= 75:
        deficits += 1
    if num_comorbidities >= 2:
        deficits += 1
    if fall_history:
        deficits += 1
    if mmse_score <= 17:
        deficits += 1

    return round(deficits / total, 2)


def frailty_label(fi: float) -> tuple[str, str]:
    """Returns (label, emoji) for a frailty index value."""
    if fi <= 0.25:
        return "Fit", "🟢"
    elif fi <= 0.50:
        return "Pre-Frail", "🟡"
    else:
        return "Frail", "🔴"


# ─────────────────────────────────────────────────────────────────────────────
# 2.0  Morse Fall Scale (Process 2 – DFD)
# ─────────────────────────────────────────────────────────────────────────────

def morse_risk_level(score: int) -> tuple[str, str]:
    """
    Returns (risk_label, hex_color) based on Morse total score.
    Thresholds: 0-24 Low, 25-44 Moderate, ≥45 High.
    """
    if score < 25:
        return "Low Risk", "#2ecc71"
    elif score < 45:
        return "Moderate Risk", "#f39c12"
    else:
        return "High Risk", "#e74c3c"


# ─────────────────────────────────────────────────────────────────────────────
# 3.0  MMSE (Process 3 – DFD)
# ─────────────────────────────────────────────────────────────────────────────

def mmse_severity(score: int) -> tuple[str, str]:
    """
    Returns (severity_label, hex_color) for MMSE total (0-30).
    25-30 Normal | 21-24 Mild | 10-20 Moderate | <10 Severe
    """
    if score >= 25:
        return "Normal", "#2ecc71"
    elif score >= 21:
        return "Mild Impairment", "#f39c12"
    elif score >= 10:
        return "Moderate Impairment", "#e67e22"
    else:
        return "Severe Impairment", "#e74c3c"


# ─────────────────────────────────────────────────────────────────────────────
# 5.0  Alerts & Reports helpers (Process 5 – DFD)
# ─────────────────────────────────────────────────────────────────────────────

def get_patient_list() -> list[dict]:
    """Fetch all patients from the patients collection."""
    coll = get_collection("patients")
    if coll is None:
        return []
    return list(coll.find({}, {"_id": 0, "patient_id": 1, "name": 1, "age": 1}))


def get_latest_assessment(patient_id: str, assessment_type: str) -> dict | None:
    """Returns the most recent assessment document for a patient and type."""
    coll = get_collection("assessments")
    if coll is None:
        return None
    return coll.find_one(
        {"patient_id": patient_id, "type": assessment_type},
        sort=[("date", -1)]
    )


def get_all_assessments(patient_id: str, assessment_type: str) -> list[dict]:
    """Returns all assessments of a type for a patient, sorted by date ascending."""
    coll = get_collection("assessments")
    if coll is None:
        return []
    return list(coll.find(
        {"patient_id": patient_id, "type": assessment_type},
        {"_id": 0, "score": 1, "date": 1}
    ).sort("date", 1))


def get_comorbidities(patient_id: str) -> list[dict]:
    """Returns all comorbidities linked to a patient."""
    coll = get_collection("comorbidities")
    if coll is None:
        return []
    return list(coll.find({"patient_id": patient_id}, {"_id": 0}))


def count_comorbidities(patient_id: str) -> int:
    coll = get_collection("comorbidities")
    if coll is None:
        return 0
    return coll.count_documents({"patient_id": patient_id})
