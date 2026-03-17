import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import certifi

# Using certifi for secure SSL connection to Atlas
ca = certifi.where()

@st.cache_resource
def get_database():
    """
    Returns the MongoDB database object.
    Reads MONGO_URI from .streamlit/secrets.toml.
    """
    try:
        uri = st.secrets["MONGO_URI"]
        client = MongoClient(uri, tlsCAFile=ca)
        return client["geriatric_db"]
    except Exception as e:
        st.error(f"Database Connection Failed: {e}")
        return None


def get_collection(collection_name: str):
    """Returns a specific collection (patients, assessments, comorbidities, activity_log)."""
    db = get_database()
    if db is not None:
        return db[collection_name]
    return None


def log_activity(action: str, patient_id: str, details: dict = None):
    """
    Writes an entry to the activity_log collection in Atlas.
    Used by all write operations for audit trail (Process 5 – DFD).
    """
    coll = get_collection("activity_log")
    if coll is None:
        return
    coll.insert_one({
        "action": action,
        "patient_id": patient_id,
        "details": details or {},
        "timestamp": datetime.utcnow()
    })