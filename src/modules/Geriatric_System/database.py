import streamlit as st
from pymongo import MongoClient
import certifi

# Using certifi for secure SSL connection to Atlas
ca = certifi.where()

@st.cache_resource
def get_database():
    """
    Returns the MongoDB database object.
    Cites the MONGO_URI from .streamlit/secrets.toml[cite: 1489, 1490].
    """
    try:
        # Accessing secrets as defined in the deployment guide [cite: 1496]
        uri = st.secrets["MONGO_URI"]
        client = MongoClient(uri, tlsCAFile=ca)
        # Defining the database name specifically for your module [cite: 1498]
        return client["geriatric_db"]
    except Exception as e:
        st.error(f"Database Connection Failed: {e}")
        return None

def get_collection(collection_name):
    """Returns a specific collection (patients, assessments, or comorbidities)."""
    db = get_database()
    if db is not None:
        return db[collection_name]
    return None