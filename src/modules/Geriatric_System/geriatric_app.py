"""
geriatric_app.py – Module 4: Geriatric Patient Health Record Dashboard
Covers all 5 DFD processes:
  1.0  Manage Geriatric Profile & Calc. Frailty Index
  2.0  Assess Fall Risk (Morse Scale)
  3.0  Evaluate Cognitive Function (MMSE)
  4.0  Manage Comorbidities (Link Diseases)
  5.0  Generate Alerts & Reports
"""

import streamlit as st
from database import get_collection, log_activity
from utils import (
    calc_frailty_index, frailty_label,
    morse_risk_level, mmse_severity,
    get_patient_list, get_latest_assessment,
    get_all_assessments, get_comorbidities, count_comorbidities
)
from datetime import datetime, date
import pandas as pd

# ─── ICD-10 Common Geriatric Diseases ─────────────────────────────────────────
DISEASE_OPTIONS = {
    "E11 – Type 2 Diabetes Mellitus":        "E11",
    "I10 – Essential Hypertension":           "I10",
    "J44 – COPD":                             "J44",
    "I50 – Heart Failure":                    "I50",
    "N18 – Chronic Kidney Disease":           "N18",
    "G30 – Alzheimer's Disease":              "G30",
    "M81 – Osteoporosis":                     "M81",
    "F32 – Depressive Episode":               "F32",
    "I69 – Stroke Sequelae":                  "I69",
    "C34 – Lung Cancer":                      "C34",
    "Other (specify below)":                  "ZZZ",
}

MORSE_AMBULATORY = {
    "None / Bedrest / Nurse Assist": 0,
    "Crutches / Cane / Walker":      15,
    "Furniture":                     30,
}
MORSE_IV = {
    "None": 0,
    "IV / Heparin Lock": 20,
}
MORSE_GAIT = {
    "Normal / Bedrest / Immobile": 0,
    "Weak":                         10,
    "Impaired / Unsteady":          20,
}
MORSE_MENTAL = {
    "Oriented to own ability":       0,
    "Overestimates / Forgets limits": 15,
}


# ─────────────────────────────────────────────────────────────────────────────
def _badge(label: str, color: str) -> str:
    """Renders a colored pill badge using HTML."""
    return (
        f'<span style="background:{color};color:#fff;padding:4px 14px;'
        f'border-radius:20px;font-weight:700;font-size:0.85rem;">{label}</span>'
    )


def _section_header(icon: str, title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
            border-left: 5px solid #0f3460;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 18px;
        ">
          <h3 style="color:#e94560;margin:0;">{icon} {title}</h3>
          <p style="color:#a8b2d8;margin:4px 0 0 0;font-size:0.9rem;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(label: str, value, delta=None, color="#0f3460"):
    delta_html = f'<p style="color:#2ecc71;font-size:0.8rem;margin:0;">{delta}</p>' if delta else ""
    st.markdown(
        f"""
        <div style="
            background:{color}22;
            border:1px solid {color}66;
            border-radius:12px;
            padding:14px 18px;
            text-align:center;
        ">
          <p style="color:#a8b2d8;font-size:0.8rem;margin:0 0 4px 0;">{label}</p>
          <h2 style="color:#fff;margin:0;">{value}</h2>
          {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS 1.0 – Patient Sidebar (Profile + Frailty Index)
# ─────────────────────────────────────────────────────────────────────────────
def _sidebar_patient_selection() -> str | None:
    """
    Renders the patient selector sidebar.
    Returns the selected patient_id or None.
    """
    st.sidebar.markdown(
        """
        <div style="
            background:linear-gradient(135deg,#e94560,#0f3460);
            border-radius:12px;
            padding:18px;
            text-align:center;
            margin-bottom:20px;
        ">
          <h2 style="color:#fff;margin:0;">🏥 Module 4</h2>
          <p style="color:#ddd;margin:4px 0 0 0;font-size:0.85rem;">Geriatric Health Records</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### 🔍 Patient Selection")

    # Fetch existing patients for the dropdown
    patients = get_patient_list()
    patient_map = {f"{p.get('name','Unknown')}  [{p['patient_id']}]": p["patient_id"]
                   for p in patients if "patient_id" in p}

    input_mode = st.sidebar.radio(
        "Select mode", ["Choose existing patient", "Enter new ID manually"],
        label_visibility="collapsed"
    )

    patient_id = None

    if input_mode == "Choose existing patient":
        if patient_map:
            selected_label = st.sidebar.selectbox("Patient", list(patient_map.keys()))
            patient_id = patient_map[selected_label]
        else:
            st.sidebar.info("No patients found. Use manual entry below.")
            patient_id = st.sidebar.text_input("Patient ID")
    else:
        patient_id = st.sidebar.text_input("Patient ID (e.g. GER-021)")

    if not patient_id:
        st.sidebar.warning("⚠️ No patient selected.")
        return None

    # ── If manually entered ID is NEW → show registration form ───────────────
    if input_mode != "Choose existing patient":
        pt_coll = get_collection("patients")
        existing_doc = pt_coll.find_one({"patient_id": patient_id}) if pt_coll is not None else None

        if existing_doc is None:
            st.sidebar.markdown(
                """
                <div style="background:#f39c1222;border:1px solid #f39c12;
                border-radius:8px;padding:10px 12px;margin:8px 0;">
                <b style="color:#f39c12;">⚠️ New patient detected</b><br>
                <span style="color:#ddd;font-size:0.82rem;">
                Fill details below and register before proceeding.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            reg_name = st.sidebar.text_input("Full Name *", key="reg_name")
            reg_age  = st.sidebar.number_input(
                "Age *", min_value=60, max_value=110, value=70, step=1, key="reg_age"
            )
            if st.sidebar.button("💾 Register Patient", key="save_patient", use_container_width=True):
                if not reg_name:
                    st.sidebar.error("Please enter the patient's name.")
                    return None
                if pt_coll is not None:
                    pt_coll.insert_one({
                        "patient_id":    patient_id,
                        "name":          reg_name,
                        "age":           int(reg_age),
                        "frailty_index": None,        # computed dynamically in sidebar
                    })
                    log_activity("Patient_Registered", patient_id,
                                 {"name": reg_name, "age": int(reg_age)})
                    st.sidebar.success(f"✅ Registered **{reg_name}**!")
                    st.rerun()
                else:
                    st.sidebar.error("DB connection failed.")
            # Block further rendering until patient is registered
            return None

    # ── Process 1.0: Frailty Index display ──────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Frailty Index")

    latest_fall  = get_latest_assessment(patient_id, "Fall_Risk")
    latest_mmse  = get_latest_assessment(patient_id, "Cognitive")
    n_comorbid   = count_comorbidities(patient_id)
    patients_coll = get_collection("patients")
    patient_doc  = patients_coll.find_one({"patient_id": patient_id}) if patients_coll is not None else None
    age = patient_doc.get("age", 70) if patient_doc else 70

    fi = calc_frailty_index(
        age           = age,
        num_comorbidities = n_comorbid,
        fall_history  = (latest_fall is not None and latest_fall.get("score", 0) >= 25),
        mmse_score    = latest_mmse.get("score", 30) if latest_mmse else 30,
    )
    label, emoji = frailty_label(fi)

    fi_pct = int(fi * 100)
    color_map = {"Fit": "#2ecc71", "Pre-Frail": "#f39c12", "Frail": "#e74c3c"}
    bar_color = color_map[label]

    st.sidebar.markdown(
        f"""
        <div style="
            background:#1a1a2e;border-radius:12px;padding:14px;
            border:1px solid {bar_color}66;
        ">
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <span style="color:#a8b2d8;font-size:0.85rem;">Frailty Index</span>
            <b style="color:#fff;">{fi:.2f}</b>
          </div>
          <div style="background:#2d2d44;border-radius:8px;height:10px;overflow:hidden;">
            <div style="background:{bar_color};width:{fi_pct}%;height:100%;border-radius:8px;transition:width .4s;"></div>
          </div>
          <p style="color:{bar_color};font-weight:700;text-align:center;margin:10px 0 0 0;">
            {emoji} {label}
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Patient ID:** `{patient_id}`")
    if patient_doc:
        st.sidebar.markdown(f"**Name:** {patient_doc.get('name','—')}")
        st.sidebar.markdown(f"**Age:** {patient_doc.get('age','—')}")

    return patient_id


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS 2.0 – Assess Fall Risk (Full Morse Fall Scale)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_fall_risk(patient_id: str):
    _section_header("🚶", "Fall Risk Assessment", "Morse Fall Scale — 6-item standardized tool")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Q1 — History of falling?**")
        q1 = st.selectbox(
            "History of falling",
            [("No (0)", 0), ("Yes (25)", 25)],
            format_func=lambda x: x[0],
            key="morse_q1"
        )[1]

        st.markdown("**Q2 — Secondary diagnosis?**")
        q2 = st.selectbox(
            "Secondary diagnosis",
            [("No (0)", 0), ("Yes (15)", 15)],
            format_func=lambda x: x[0],
            key="morse_q2"
        )[1]

        st.markdown("**Q3 — Ambulatory aid**")
        q3_label = st.selectbox("Ambulatory aid", list(MORSE_AMBULATORY.keys()), key="morse_q3")
        q3 = MORSE_AMBULATORY[q3_label]

    with col2:
        st.markdown("**Q4 — IV / Heparin lock?**")
        q4_label = st.selectbox("IV access", list(MORSE_IV.keys()), key="morse_q4")
        q4 = MORSE_IV[q4_label]

        st.markdown("**Q5 — Gait**")
        q5_label = st.selectbox("Gait type", list(MORSE_GAIT.keys()), key="morse_q5")
        q5 = MORSE_GAIT[q5_label]

        st.markdown("**Q6 — Mental status**")
        q6_label = st.selectbox("Mental status", list(MORSE_MENTAL.keys()), key="morse_q6")
        q6 = MORSE_MENTAL[q6_label]

    total_morse = q1 + q2 + q3 + q4 + q5 + q6
    risk_label, risk_color = morse_risk_level(total_morse)

    st.markdown("<br>", unsafe_allow_html=True)
    r1, r2, r3 = st.columns([1, 1, 1])
    with r1:
        _metric_card("Total Morse Score", total_morse, color="#0f3460")
    with r2:
        _metric_card("Risk Level", risk_label, color=risk_color[:7])
    with r3:
        _metric_card("Assessment Date", datetime.now().strftime("%d %b %Y"), color="#1a1a2e")

    st.markdown(
        f'<div style="text-align:center;margin:12px 0;">{_badge(risk_label, risk_color)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    col_btn, col_hist = st.columns([1, 2])
    with col_btn:
        if st.button("💾 Save Fall Risk Assessment", use_container_width=True):
            coll = get_collection("assessments")
            assessment_id = f"{patient_id}_FR_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            doc = {
                "patient_id":    patient_id,
                "assessment_id": assessment_id,
                "type":          "Fall_Risk",
                "score":         total_morse,
                "morse_components": {
                    "history_of_falling":  q1,
                    "secondary_diagnosis": q2,
                    "ambulatory_aid":      q3,
                    "iv_access":           q4,
                    "gait":                q5,
                    "mental_status":       q6,
                },
                "date": datetime.utcnow(),
            }
            coll.insert_one(doc)
            log_activity("Fall_Risk_Assessment", patient_id, {"score": total_morse, "risk": risk_label})
            st.success(f"✅ Morse Score ({total_morse}) saved! Assessment ID: `{assessment_id}`")
            st.rerun()

    with col_hist:
        history = get_all_assessments(patient_id, "Fall_Risk")
        if history:
            df = pd.DataFrame(history)
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%d %b %Y %H:%M")
            st.markdown("**Assessment History**")
            st.dataframe(df.rename(columns={"score": "Morse Score", "date": "Date"}),
                         use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS 3.0 – Evaluate Cognitive Function (Full MMSE)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_cognitive(patient_id: str):
    _section_header("🧠", "Cognitive Function Evaluation", "Mini-Mental State Exam (MMSE) — 30-point scale")

    st.markdown(
        """
        <div style="background:#1a1a2e;border-radius:10px;padding:12px 18px;margin-bottom:16px;">
          <b style="color:#a8b2d8;">MMSE Domains:</b>
          <span style="color:#e94560;"> Orientation (10)</span> ·
          <span style="color:#e94560;"> Registration (3)</span> ·
          <span style="color:#e94560;"> Attention (5)</span> ·
          <span style="color:#e94560;"> Recall (3)</span> ·
          <span style="color:#e94560;"> Language (9)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Orientation** *(0–10)*")
        orientation = st.slider("What is the date / place / country …?", 0, 10, 8, key="mmse_ori")

        st.markdown("**Registration** *(0–3)*")
        registration = st.slider("Repeat 3 words (Ball, Flag, Tree)?", 0, 3, 3, key="mmse_reg")

        st.markdown("**Attention & Calculation** *(0–5)*")
        attention = st.slider("Serial 7s or spell WORLD backwards?", 0, 5, 4, key="mmse_att")

    with col2:
        st.markdown("**Recall** *(0–3)*")
        recall = st.slider("Recall the 3 words from Registration?", 0, 3, 2, key="mmse_rec")

        st.markdown("**Language** *(0–9)*")
        language = st.slider("Naming, repetition, commands, writing, copying?", 0, 9, 8, key="mmse_lang")

    total_mmse = orientation + registration + attention + recall + language
    severity_label, severity_color = mmse_severity(total_mmse)

    st.markdown("<br>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    with m1: _metric_card("MMSE Total", f"{total_mmse} / 30", color="#0f3460")
    with m2: _metric_card("Severity", severity_label, color=severity_color[:7])
    with m3: _metric_card("Orientation", f"{orientation}/10", color="#1a1a2e")
    with m4: _metric_card("Language", f"{language}/9", color="#1a1a2e")

    st.markdown(
        f'<div style="text-align:center;margin:12px 0;">{_badge(severity_label, severity_color)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    col_btn, col_hist = st.columns([1, 2])
    with col_btn:
        if st.button("💾 Save Cognitive Exam", use_container_width=True):
            coll = get_collection("assessments")
            exam_id = f"{patient_id}_MMSE_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            doc = {
                "patient_id": patient_id,
                "exam_id":    exam_id,
                "type":       "Cognitive",
                "score":      total_mmse,
                "mmse_components": {
                    "orientation":   orientation,
                    "registration":  registration,
                    "attention":     attention,
                    "recall":        recall,
                    "language":      language,
                },
                "date": datetime.utcnow(),
            }
            coll.insert_one(doc)
            log_activity("Cognitive_Exam", patient_id, {"score": total_mmse, "severity": severity_label})
            st.success(f"✅ MMSE Score ({total_mmse}/30) saved! Exam ID: `{exam_id}`")
            st.rerun()

    with col_hist:
        history = get_all_assessments(patient_id, "Cognitive")
        if history:
            df = pd.DataFrame(history)
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%d %b %Y %H:%M")
            st.markdown("**Exam History**")
            st.dataframe(df.rename(columns={"score": "MMSE Score", "date": "Date"}),
                         use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS 4.0 – Manage Comorbidities (Link Diseases)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_comorbidities(patient_id: str):
    _section_header("🩺", "Comorbidity Management", "Link ICD-10 diseases to patient • Records Severity & Diagnosis Date")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("**Select Disease**")
        selected_disease = st.selectbox(
            "Disease (ICD-10)",
            list(DISEASE_OPTIONS.keys()),
            key="disease_select"
        )
        disease_code = DISEASE_OPTIONS[selected_disease]

        if disease_code == "ZZZ":
            custom_name = st.text_input("Disease Name (custom)")
            custom_code = st.text_input("ICD-10 Code (optional)")
            disease_name = custom_name
            disease_code = custom_code or "ZZZ"
        else:
            disease_name = selected_disease.split("–")[1].strip()

        st.markdown("**Diagnosis Date**")
        diag_date = st.date_input("Diagnosis Date", value=date.today(), key="diag_date")

        st.markdown("**Severity**")
        severity_opts = ["Mild", "Moderate", "Severe", "Critical"]
        severity = st.selectbox("Severity Level", severity_opts, key="severity_select")

        st.markdown("**Additional Notes**")
        notes = st.text_area("Clinical notes (optional)", height=80, key="comorbid_notes")

    with col2:
        st.markdown("**Current Comorbidities**")
        existing = get_comorbidities(patient_id)
        if existing:
            df_existing = pd.DataFrame([
                {
                    "Disease":   e.get("disease", "—"),
                    "Code":      e.get("disease_code", "—"),
                    "Severity":  e.get("severity", "—"),
                    "Diagnosed": str(e.get("diagnosis_date", "—"))[:10],
                }
                for e in existing
            ])
            st.dataframe(df_existing, use_container_width=True, hide_index=True)
            st.markdown(
                f'<p style="color:#a8b2d8;font-size:0.85rem;">Total: <b style="color:#e94560;">{len(existing)}</b> condition(s) linked</p>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No comorbidities linked yet.")

    st.markdown("---")
    if st.button("🔗 Link Disease to Patient", use_container_width=True):
        if disease_code == "ZZZ" and not disease_name:
            st.warning("Please enter a disease name.")
        else:
            coll = get_collection("comorbidities")
            doc = {
                "patient_id":     patient_id,
                "disease":        disease_name,
                "disease_code":   disease_code,
                "severity":       severity,
                "diagnosis_date": datetime.combine(diag_date, datetime.min.time()),
                "notes":          notes,
                "timestamp":      datetime.utcnow(),
            }
            coll.insert_one(doc)
            log_activity("Comorbidity_Linked", patient_id, {"disease": disease_name, "severity": severity})
            st.success(f"✅ Linked **{disease_name}** ({disease_code}) to patient `{patient_id}`")
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS 5.0 – Alerts & Reports (read-only dashboard)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_alerts(patient_id: str):
    _section_header("🔔", "Alerts & Clinical Reports", "Process 5.0 — High-risk flags + score trend charts")

    # Fetch latest scores
    latest_fall  = get_latest_assessment(patient_id, "Fall_Risk")
    latest_mmse  = get_latest_assessment(patient_id, "Cognitive")
    comorbidities = get_comorbidities(patient_id)

    morse_score = latest_fall.get("score") if latest_fall else None
    mmse_score  = latest_mmse.get("score") if latest_mmse else None

    # ── Alert banners ────────────────────────────────────────────────────────
    has_alert = False

    if morse_score is not None and morse_score >= 45:
        has_alert = True
        st.markdown(
            f"""
            <div style="
                background: #e74c3c22;
                border: 2px solid #e74c3c;
                border-radius: 12px;
                padding: 16px 20px;
                margin-bottom: 12px;
            ">
              <h4 style="color:#e74c3c;margin:0;">🚨 HIGH FALL RISK — Morse Score {morse_score}</h4>
              <p style="color:#ddd;margin:6px 0 0 0;">
                Morse ≥ 45 requires <b>immediate fall prevention protocol</b>.
                Bed rails raised, call bell within reach, non-slip footwear.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if mmse_score is not None and mmse_score <= 17:
        has_alert = True
        st.markdown(
            f"""
            <div style="
                background: #e67e2222;
                border: 2px solid #e67e22;
                border-radius: 12px;
                padding: 16px 20px;
                margin-bottom: 12px;
            ">
              <h4 style="color:#e67e22;margin:0;">⚠️ COGNITIVE IMPAIRMENT — MMSE Score {mmse_score}/30</h4>
              <p style="color:#ddd;margin:6px 0 0 0;">
                MMSE ≤ 17 indicates <b>Moderate–Severe impairment</b>.
                Refer to specialist for further evaluation (GDS, ADL/IADL).
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if len(comorbidities) >= 4:
        has_alert = True
        st.markdown(
            f"""
            <div style="
                background: #9b59b622;
                border: 2px solid #9b59b6;
                border-radius: 12px;
                padding: 16px 20px;
                margin-bottom: 12px;
            ">
              <h4 style="color:#9b59b6;margin:0;">💊 POLYPHARMACY RISK — {len(comorbidities)} Comorbidities</h4>
              <p style="color:#ddd;margin:6px 0 0 0;">
                ≥4 comorbidities increases polypharmacy risk.
                Review medications for interactions.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not has_alert:
        st.markdown(
            """
            <div style="
                background:#2ecc7122;border:2px solid #2ecc71;border-radius:12px;
                padding:16px 20px;margin-bottom:12px;
            ">
              <h4 style="color:#2ecc71;margin:0;">✅ No Critical Alerts</h4>
              <p style="color:#ddd;margin:6px 0 0 0;">Patient is within safe clinical thresholds.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Score trend charts ───────────────────────────────────────────────────
    ch1, ch2 = st.columns(2)

    with ch1:
        st.markdown("#### 📈 Morse Score Trend")
        fall_history = get_all_assessments(patient_id, "Fall_Risk")
        if fall_history:
            df_f = pd.DataFrame(fall_history)
            df_f["date"] = pd.to_datetime(df_f["date"])
            df_f = df_f.set_index("date")
            st.line_chart(df_f["score"], use_container_width=True)
            st.caption("Morse Scale: < 25 = Low | 25–44 = Moderate | ≥ 45 = High Risk")
        else:
            st.info("No fall risk history yet.")

    with ch2:
        st.markdown("#### 🧠 MMSE Score Trend")
        mmse_history = get_all_assessments(patient_id, "Cognitive")
        if mmse_history:
            df_m = pd.DataFrame(mmse_history)
            df_m["date"] = pd.to_datetime(df_m["date"])
            df_m = df_m.set_index("date")
            st.line_chart(df_m["score"], use_container_width=True)
            st.caption("MMSE: ≥25 Normal | 21–24 Mild | 10–20 Moderate | <10 Severe")
        else:
            st.info("No cognitive exam history yet.")

    # ── Comorbidity summary table ────────────────────────────────────────────
    if comorbidities:
        st.markdown("---")
        st.markdown("#### 🩺 Comorbidity Summary")
        df_c = pd.DataFrame([
            {
                "Disease":        c.get("disease", "—"),
                "ICD-10 Code":    c.get("disease_code", "—"),
                "Severity":       c.get("severity", "—"),
                "Diagnosed":      str(c.get("diagnosis_date", ""))[:10],
                "Notes":          c.get("notes", ""),
            }
            for c in comorbidities
        ])

        severity_order = {"Mild": 0, "Moderate": 1, "Severe": 2, "Critical": 3}
        df_c["_order"] = df_c["Severity"].map(severity_order).fillna(99)
        df_c = df_c.sort_values("_order").drop(columns="_order")
        st.dataframe(df_c, use_container_width=True, hide_index=True)

    # ── Summary metrics row ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📊 Patient Summary Metrics")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        _metric_card("Morse Score", morse_score if morse_score is not None else "N/A",
                     color="#e74c3c" if (morse_score or 0) >= 45 else "#0f3460")
    with s2:
        _metric_card("MMSE Score", f"{mmse_score}/30" if mmse_score is not None else "N/A",
                     color="#e67e22" if (mmse_score or 30) <= 17 else "#0f3460")
    with s3:
        _metric_card("Comorbidities", len(comorbidities), color="#9b59b6")
    with s4:
        fi_patients_coll = get_collection("patients")
        patient_doc = fi_patients_coll.find_one({"patient_id": patient_id}) if fi_patients_coll is not None else None
        age = patient_doc.get("age", "—") if patient_doc else "—"
        _metric_card("Age", age, color="#1a1a2e")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def run_geriatric_module():
    # ── Global dark-theme CSS ────────────────────────────────────────────────
    st.markdown(
        """
        <style>
        /* ── Base ── */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #0d0d1a 0%, #1a1a2e 100%);
        }
        [data-testid="stSidebar"] {
            background: #12122a !important;
        }
        [data-testid="stSidebar"] * { color: #c9d1d9; }

        /* ── Tab bar ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            background: #1a1a2e;
            border-radius: 12px;
            padding: 6px;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border-radius: 8px;
            color: #a8b2d8;
            font-weight: 600;
            padding: 8px 20px;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #e94560, #0f3460) !important;
            color: #fff !important;
        }

        /* ── Inputs ── */
        .stSelectbox > div > div,
        .stTextInput > div > div {
            background: #1a1a2e !important;
            border: 1px solid #0f3460 !important;
            color: #fff !important;
            border-radius: 8px !important;
        }
        .stSlider > div > div > div {
            background: linear-gradient(90deg, #e94560, #0f3460) !important;
        }

        /* ── Buttons ── */
        .stButton > button {
            background: linear-gradient(135deg, #e94560 0%, #0f3460 100%) !important;
            color: #fff !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            padding: 10px 24px !important;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(233,69,96,0.4) !important;
        }

        /* ── Dataframe ── */
        [data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
        }

        /* ── Metrics ── */
        .stMetric { background: #1a1a2e; border-radius: 10px; padding: 10px; }

        /* ── Radio ── */
        .stRadio > div { flex-direction: row; gap: 16px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Page banner ──────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #e94560 0%, #0f3460 50%, #1a1a2e 100%);
            border-radius: 16px;
            padding: 30px 40px;
            margin-bottom: 24px;
        ">
          <h1 style="color:#fff;margin:0;font-size:2.2rem;">
            🏥 Module 4: Geriatric Patient Health Records
          </h1>
          <p style="color:#ddd;margin:8px 0 0 0;">
            Comprehensive geriatric assessment · Fall Risk · Cognitive Function · Comorbidity Management
          </p>
          <div style="display:flex;gap:12px;margin-top:14px;flex-wrap:wrap;">
            <span style="background:#fff2;padding:4px 12px;border-radius:20px;color:#fff;font-size:0.8rem;">
              🔬 Morse Fall Scale
            </span>
            <span style="background:#fff2;padding:4px 12px;border-radius:20px;color:#fff;font-size:0.8rem;">
              🧠 MMSE Cognitive Exam
            </span>
            <span style="background:#fff2;padding:4px 12px;border-radius:20px;color:#fff;font-size:0.8rem;">
              🩺 ICD-10 Comorbidities
            </span>
            <span style="background:#fff2;padding:4px 12px;border-radius:20px;color:#fff;font-size:0.8rem;">
              📊 Frailty Index
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Process 1.0 – Patient selection in sidebar ───────────────────────────
    patient_id = _sidebar_patient_selection()

    if not patient_id:
        st.info("👈 Select or enter a patient ID in the sidebar to begin.")
        return

    # ── Main tabs (Processes 2–5) ────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚶 Fall Risk (Morse)",
        "🧠 Cognitive Exam (MMSE)",
        "🩺 Comorbidities",
        "🔔 Alerts & Reports",
    ])

    with tab1:
        _tab_fall_risk(patient_id)

    with tab2:
        _tab_cognitive(patient_id)

    with tab3:
        _tab_comorbidities(patient_id)

    with tab4:
        _tab_alerts(patient_id)


if __name__ == "__main__":
    run_geriatric_module()
