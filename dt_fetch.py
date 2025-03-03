import requests
import streamlit as st
import pandas as pd

# Function to get access token from Dynatrace API
@st.cache_data(ttl=300)  # Cache the token for 1 hour
def get_dynatrace_access_token(client_id, client_secret):
    url = "https://sso.dynatrace.com/sso/oauth2/token"
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'account-uac-read account-env-read'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        st.error("Failed to retrieve access token.")
        return response.json()

# Function to fetch forecasted budget data
def fetch_forecasted_budget(access_token, account_uuid):
    account_uuid_split = account_uuid.split(':')[-1]
    url = f"https://api.dynatrace.com/sub/v2/accounts/{account_uuid_split}/subscriptions/forecast"
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to retrieve forecasted budget data.")
        return response.json()
    
# Function to retrieve subscriptions for a given account
def get_subscriptions(account_uuid, token):
    account_uuid_split = account_uuid.split(':')[-1]
    url = f"https://api.dynatrace.com/sub/v2/accounts/{account_uuid_split}/subscriptions"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('data', [])
    else:
        st.warning("Generate access token to see subscriptions.")
        return []

# Function to retrieve cost data for a specific subscription and timeframe
def get_subscription_cost(account_uuid, subscription_uuid, token, start_time, end_time):
    account_uuid_split = account_uuid.split(':')[-1]
    url = (f"https://api.dynatrace.com/sub/v2/accounts/{account_uuid_split}/subscriptions/"
           f"{subscription_uuid}/environments/cost?startTime={start_time}&endTime={end_time}")
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('data', [])
    else:
        st.error("Failed to retrieve subscription costs.")
        return []
    
def flatten_cost_data(cost_data):
    """Flatten the cost data so each cost object becomes a row in the DataFrame."""
    cost_list = []
    
    for entry in cost_data:
        environment_id = entry.get("environmentId", "Unknown")
        for cost in entry.get("cost", []):
            cost_list.append({
                "environmentId": environment_id,
                "capabilityName": cost.get("capabilityName", "Unknown"),
                "startTime": cost.get("startTime", "Unknown"),
                "endTime": cost.get("endTime", "Unknown"),
                "value": cost.get("value", 0),
                "currencyCode": cost.get("currencyCode", "Unknown")
            })
    
    return pd.DataFrame(cost_list)