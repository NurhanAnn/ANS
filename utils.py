import os
import json
import streamlit as st

# Saved credentials for Dynatrace API
CREDENTIALS_FILE = "credentials.json"

def load_credentials():
    """Load credentials from the JSON file."""
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as file:
            return json.load(file)
    return {}

def save_credentials(name, client_id, client_secret, account_urn):
    """Save a new set of credentials."""
    credentials = load_credentials()
    credentials[name] = {
        "client_id": client_id,
        "client_secret": client_secret,
        "account_urn": account_urn
    }
    
    with open(CREDENTIALS_FILE, "w") as file:
        json.dump(credentials, file, indent=4)
    
    st.success(f"✅ Credentials saved under '{name}'")

def get_selected_credentials(name):
    """Retrieve credentials based on the selected account."""
    credentials = load_credentials()
    return credentials.get(name, None)