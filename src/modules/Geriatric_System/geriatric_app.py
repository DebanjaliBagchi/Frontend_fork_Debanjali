import streamlit as st
from database import get_collection
from datetime import datetime

def run_geriatric_module():
    st.header("👵 Module 4: Geriatric Health Records")
    
    # 1. Patient Selection (Input from Module 1) [cite: 740]
    st.subheader("Patient Identification")
    patient_id = st.text_input("Enter Patient UUID (from Module 1)")
    
    if patient_id:
        tab1, tab2, tab3 = st.tabs(["Fall Risk", "Cognitive Assessment", "Comorbidities"])

        # --- TAB 1: MORSE FALL SCALE [cite: 816, 822] ---
        with tab1:
            st.write("### Morse Fall Scale Assessment")
            history_falls = st.radio("History of falling?", [0, 25], format_func=lambda x: "Yes (25)" if x == 25 else "No (0)")
            secondary_diag = st.radio("Secondary diagnosis?", [0, 15])
            ambulatory_aid = st.selectbox("Ambulatory aid", [0, 15, 30], format_func=lambda x: {0: "None/Bedrest", 15: "Crutches/Walker", 30: "Furniture"}[x])
            
            total_morse = history_falls + secondary_diag + ambulatory_aid
            st.metric("Total Morse Score", total_morse)
            
            if st.button("Save Fall Assessment"):
                coll = get_collection("assessments")
                coll.insert_one({
                    "patient_id": patient_id,
                    "type": "Fall_Risk",
                    "score": total_morse,
                    "date": datetime.now()
                })
                st.success("Morse Score Logged!")

        # --- TAB 2: COGNITIVE (MMSE) [cite: 817, 822] ---
        with tab2:
            st.write("### Mini-Mental State Exam (MMSE)")
            orientation = st.slider("Orientation Score (0-10)", 0, 10)
            registration = st.slider("Registration Score (0-3)", 0, 3)
            attention = st.slider("Attention Score (0-5)", 0, 5)
            
            total_mmse = orientation + registration + attention
            st.metric("Total MMSE Score", total_mmse)
            
            if st.button("Save Cognitive Exam"):
                coll = get_collection("assessments")
                coll.insert_one({
                    "patient_id": patient_id,
                    "type": "Cognitive",
                    "score": total_mmse,
                    "date": datetime.now()
                })
                st.success("MMSE Score Logged!")

        # --- TAB 3: COMORBIDITY LOGGING [cite: 820, 824] ---
        with tab3:
            st.write("### Comorbidity Management")
            disease_name = st.text_input("Disease Name (e.g., COPD, Diabetes)")
            severity = st.select_slider("Severity Index", options=["Low", "Medium", "High"])
            
            if st.button("Link Disease to Patient"):
                coll = get_collection("comorbidities")
                coll.insert_one({
                    "patient_id": patient_id,
                    "disease": disease_name,
                    "severity": severity,
                    "timestamp": datetime.now()
                })
                st.info(f"Linked {disease_name} to Patient {patient_id}")

if __name__ == "__main__":
    run_geriatric_module()