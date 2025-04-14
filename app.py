import os
import streamlit as st
import requests
import msal
import pandas as pd
import json
from datetime import datetime, timedelta
from msal_extensions import (
    FilePersistenceWithDataProtection, PersistedTokenCache, FilePersistence
)
import streamlit as st
import plotly.graph_objects as go

# Streamlit UI
st.title("📊 Dashboard")

# Create tabs
tab1, tab2 = st.tabs(["Email Attachment Viewer", "Dynatrace License Tracker"])

# Import tab modules
from emails_tab import show_email_tab
from dynatrace_tab import show_dynatrace_tab

with tab1:
    show_email_tab()

with tab2:
    show_dynatrace_tab()
