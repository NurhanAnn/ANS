import requests
import streamlit as st
import pandas as pd
from datetime import datetime
import utils

# Function to get access token from Dynatrace API (SaaS DPS)
@st.cache_data(ttl=300)  # Cache the token for 5 minutes
def get_dynatrace_access_token(client_id, client_secret):
    """Get access token for SaaS DPS license type"""
    url = "https://sso.dynatrace.com/sso/oauth2/token"
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'account-uac-read account-env-read'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=payload, headers=headers)
    print(response.json())
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        st.error("Failed to retrieve access token.")
        return response.json()

# Function to fetch forecasted budget data (DPS Specific)
def fetch_forecasted_budget(access_token, account_uuid):
    """Fetch forecasted budget for SaaS DPS license type"""
    account_uuid_split = account_uuid.split(':')[-1]
    url = f"https://api.dynatrace.com/sub/v2/accounts/{account_uuid_split}/subscriptions/forecast"
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    print("\nForecasted Budget Data: \n")
    print(response.json())
    if response.status_code == 200:
        return response.json()
    else:
        st.error("Failed to retrieve forecasted budget data.")
        return response.json()

# Function to retrieve active subscriptions for a given account (DPS Specific)
def get_subscriptions_DPS(account_uuid, token):
    """Get active subscriptions for SaaS DPS and Managed DPS license types"""
    account_uuid_split = account_uuid.split(':')[-1]
    url = f"https://api.dynatrace.com/sub/v2/accounts/{account_uuid_split}/subscriptions"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    print("\nSubscriptions: \n")
    print(response.json())
    if response.status_code == 200:
        subs = response.json().get('data', [])
        active_subs = [sub for sub in subs if sub.get('status') == 'ACTIVE']
        return active_subs
    else:
        st.warning(response.status_code)
        st.warning(response.json())
        st.warning("Generate access token to see subscriptions.")
        return []

# Function to retrieve cost data for a specific subscription and timeframe (DPS Specific)
def get_subscription_cost(account_uuid, subscription_uuid, token, start_time, end_time):
    """Get subscription cost for SaaS DPS and Managed DPS license types"""
    account_uuid_split = account_uuid.split(':')[-1]
    url = (f"https://api.dynatrace.com/sub/v2/accounts/{account_uuid_split}/subscriptions/"
           f"{subscription_uuid}/environments/cost?startTime={start_time}&endTime={end_time}")
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('data', [])
    else:
        st.warning(response.status_code)
        st.warning(response.json())
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

# For SaaS DPS and Managed DPS
def get_dps_license_data(account_urn, access_token):
    """
    Fetch license data for DPS licenses (SaaS DPS and Managed DPS).
    
    Flow:
      - GET all subscriptions using get_subscriptions() and filter by ACTIVE status.
      - Select the subscription with the latest expiry date.
      - Using that subscription ID, GET cost data (via get_subscription_cost()) and sum it up.
      - GET forecast data (via fetch_forecasted_budget()) to retrieve the budget.
    
    Returns a dictionary with:
      - 'expiry_date': Subscription expiry date (YYYY-MM-DD string)
      - 'usage': Total cost (summed cost value)
      - 'limit': Forecasted budget (if available)
    """
    subscriptions = get_subscriptions_DPS(account_urn, access_token)
    if not subscriptions:
        st.warning("No active subscriptions found. Please input data manually.")
        return {}
    
    try:
        # Select the subscription with the latest expiry date
        chosen_sub = max(subscriptions, key=lambda sub: datetime.strptime(sub['endTime'], "%Y-%m-%d"))
    except Exception as e:
        st.error(f"Error parsing subscription expiry dates: {e}")
        return {}
    
    expiry_date = chosen_sub.get('endTime')
    start_time = chosen_sub.get('startTime')
    end_time = chosen_sub.get('endTime')
    
    if chosen_sub:  # Ensure there's a subscription before proceeding
        # Retrieve cost data for the chosen subscription
        cost_data = get_subscription_cost(account_urn, chosen_sub.get('uuid'), access_token, start_time, end_time)
        st.write(cost_data)

        if cost_data:  # Ensure cost_data is not empty
            total_cost_df = calculate_total_cost(cost_data)
            st.dataframe(total_cost_df)

            # Calculate total cost
            total_cost = sum(
                cost.get("value", 0)
                for entry in cost_data
                for cost in entry.get("cost", [])
            )
        else:
            total_cost_df = pd.DataFrame()  # Empty DataFrame
            total_cost = 0
    else:
        # Default values when no subscription exists
        cost_data = []
        total_cost_df = pd.DataFrame()  # Empty DataFrame
        total_cost = 0

    # Display default values if needed
    st.write(f"Total Cost: {total_cost}")
    st.dataframe(total_cost_df)
    
    # Retrieve forecast to get the budget
    forecast = fetch_forecasted_budget(access_token, account_urn)
    budget = forecast.get("budget") if forecast else None
    
    return {
        "expiry_date": expiry_date,
        "usage": total_cost,
        "limit": budget,
        "details (df)": total_cost_df.to_dict(orient='records')
    }

def calculate_total_cost(environments):
    """
    Calculates the total cost per capabilityKey from the given environments data.
    
    Parameters:
        environments (list): List of dictionaries where each dictionary contains 
                             an "environmentId" and a "cost" key, which is a list of 
                             cost entries.
    
    Returns:
        pd.DataFrame: DataFrame with columns "capabilityKey", "capabilityName", 
                      "currencyCode", and "total_cost".
    """
    all_entries = []
    # Loop through each environment dictionary
    for env in environments:
        environment_id = env.get("environmentId")
        cost_list = env.get("cost", [])
        # Optionally add the environment id to each entry if needed
        for entry in cost_list:
            entry["environmentId"] = environment_id
            all_entries.append(entry)
    
    # Create DataFrame from the list of cost entries
    df = pd.DataFrame(all_entries)
    
    # Group by capabilityKey, capabilityName, and currencyCode and sum the values
    total_cost_df = (
        df.groupby(["capabilityKey", "capabilityName", "currencyCode"])["value"]
          .sum()
          .reset_index()
          .rename(columns={"value": "total_cost"})
    )
    
    return total_cost_df

# Only for Managed Classic
def get_classic_license_data(access_token, base_url):
    """
    Fetch license data for Managed Classic licenses.
    
    Flow:
      - Build the Cluster API URL dynamically using the provided base_url.
      - GET environments data and filter for those with state "ENABLED".
      - Sum up the 'usage' and 'limit' values from each environment's consumption info.
    
    Returns a dictionary with:
      - 'expiry_date': None (not applicable)
      - 'usage': Total usage (summed from environments)
      - 'limit': Total limit (summed from environments)
    """
    url = f"{base_url}/api/cluster/v2/environments?filter=state%28ENABLED%29&includeConsumptionInfo=true&includeUncachedConsumptionInfo=true"
    headers = {
        'accept': 'application/json; charset=utf-8',
        'Authorization': f'Api-Token {access_token}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        # st.write(response.json())
        environments = response.json().get('environments', [])
        total_host_usage = 0
        total_host_limit = 0
        total_dem_usage = 0
        total_dem_limit = 0
        total_davis_usage = 0
        total_davis_limit = 0

        for env in environments:
            host_units = env.get("quotas", {}).get("hostUnits", {})
            current_usage_host = host_units.get("currentUsage", 0)
            max_limit_host = host_units.get("maxLimit")
            
            dem_units = env.get("quotas", {}).get("demUnits", {})
            current_usage_dem = dem_units.get("consumedThisMonth", 0)
            max_limit_dem = dem_units.get("monthlyLimit")

            davis_units = env.get("quotas", {}).get("davisDataUnits", {})
            current_usage_davis = davis_units.get("consumedThisMonth", 0)
            max_limit_davis = davis_units.get("monthlyLimit")
            
            
            # Treat None as 0 for summation purposes.
            if max_limit_host is None:
                max_limit_host = 0

            if max_limit_dem is None:
                max_limit_dem = 0

            if max_limit_davis is None:
                max_limit_davis = 0
            
            total_host_usage += current_usage_host
            total_host_limit += max_limit_host

            total_dem_usage += current_usage_dem
            total_dem_limit += max_limit_dem

            total_davis_usage += current_usage_davis
            total_davis_limit += max_limit_davis

        return {
            "expiry_date": None,
            "host usage": total_host_usage,
            "host limit": total_host_limit,
            "dem usage": total_dem_usage,
            "dem limit": total_dem_limit,
            "davis usage": total_davis_usage,
            "davis limit": total_davis_limit
        }
    else:
        st.error("Failed to fetch Managed Classic license data from the Cluster API.")
        return {}


def get_client_summary():
    """
    Get a summary of all clients with their subscription details.
    
    Returns:
        pd.DataFrame: DataFrame containing client summary information with columns:
            - Client Name
            - Expiry Date
            - Days to Expiry
    """
    summary_data = utils.load_client_summary()  # This function loads data from SUMMARY_FILE
    
    
    df = pd.DataFrame(summary_data)
    if "Expiry Date" in df.columns:
        # Convert expiry date to a date object
        df["Expiry Date"] = pd.to_datetime(df["Expiry Date"], errors='coerce').dt.date
        df["Days to Expiry"] = df["Expiry Date"].apply(
            lambda x: (x - datetime.now().date()).days if pd.notnull(x) else None
        )
    return df

def save_manual_client(client_name, license_type, expiry_date, usage, limit, total_host_usage, total_host_limit, total_dem_usage, total_dem_limit, total_davis_usage, total_davis_limit):
    """Save manually entered client data"""
    summary = get_client_summary().to_dict('records')
    
    # Update or add new entry
    found = False
    for client in summary:
        if client['Client Name'] == client_name:
            client.update({
                'License Type': license_type,
                'Expiry Date': expiry_date.strftime('%Y-%m-%d') if isinstance(expiry_date, datetime) else expiry_date,
                'Usage': usage,
                'Limit': limit,
                'Host Usage': total_host_usage,
                'Host Limit': total_host_limit,
                'DEM Usage': total_dem_usage,
                'DEM Limit': total_dem_limit,
                'Davis Usage': total_davis_usage,
                'Davis Limit': total_davis_limit
            })
            found = True
            break
            
    if not found:
        summary.append({
            'Client Name': client_name,
            'License Type': license_type,
            'Expiry Date': expiry_date.strftime('%Y-%m-%d') if isinstance(expiry_date, datetime) else expiry_date,
            'Usage': usage,
            'Limit': limit,
            'Host Usage': total_host_usage,
            'Host Limit': total_host_limit,
            'DEM Usage': total_dem_usage,
            'DEM Limit': total_dem_limit,
            'Davis Usage': total_davis_usage,
            'Davis Limit': total_davis_limit
        })
    st.write(summary)
    utils.save_client_summary(summary)

def save_dps_client(client_name, license_type, client_id, client_secret, account_urn, expiry_date, usage, limit, details_cost):
    """Save DPS client credentials with additional information"""
    summary = get_client_summary().to_dict('records')

    # Update or add new entry
    found = False
    for client in summary:
        if client['Client Name'] == client_name:
            client.update({
                'License Type': license_type,
                'Client ID': client_id,
                'Client Secret': client_secret,
                'Account URN': account_urn,
                'Expiry Date': expiry_date.strftime('%Y-%m-%d') if isinstance(expiry_date, datetime) else expiry_date,
                'Usage': usage,
                'Limit': limit,
                'Cost Details' : details_cost
            })
            found = True
            st.success(f"Attempt to update Client '{client_name}' data.")
            break

    if not found:
        summary.append({
            'Client Name': client_name,
            'License Type': license_type,
            'Client ID': client_id,
            'Client Secret': client_secret,
            'Account URN': account_urn,
            'Expiry Date': expiry_date.strftime('%Y-%m-%d') if isinstance(expiry_date, datetime) else expiry_date,
            'Usage': usage,
            'Limit': limit,
            'Cost Details' : details_cost
        })
        st.success(f"Attempt to append Client '{client_name}' data.")
    st.write(summary)
    utils.save_client_summary(summary)

def save_classic_client(client_name, license_type, api_key, base_url, expiry_date, total_host_usage, total_host_limit, total_dem_usage, total_dem_limit, total_davis_usage, total_davis_limit, details_cost):
    """Save Classic client credentials and license data"""
    summary = get_client_summary().to_dict('records')
    st.write("should go here once")
    
    # Update or add new entry
    found = False
    for client in summary:
        if client['Client Name'] == client_name:
            client.update({
                'License Type': license_type,
                'API Key': api_key,
                'Base URL': base_url,
                'Expiry Date': expiry_date.strftime('%Y-%m-%d') if isinstance(expiry_date, datetime) else expiry_date,
                'Host Usage': total_host_usage,
                'Host Limit': total_host_limit,
                'DEM Usage': total_dem_usage,
                'DEM Limit': total_dem_limit,
                'Davis Usage': total_davis_usage,
                'Davis Limit': total_davis_limit,
                'Cost Details' : details_cost
            })
            found = True
            st.success(f"Attempt to update Client '{client_name}' data.")
            break
            
    if not found:
        summary.append({
            'Client Name': client_name,
            'License Type': license_type,
            'API Key': api_key,
            'Base URL': base_url,
            'Expiry Date': expiry_date.strftime('%Y-%m-%d') if isinstance(expiry_date, datetime) else expiry_date,
            'Host Usage': total_host_usage,
            'Host Limit': total_host_limit,
            'DEM Usage': total_dem_usage,
            'DEM Limit': total_dem_limit,
            'Davis Usage': total_davis_usage,
            'Davis Limit': total_davis_limit,
            'Cost Details' : details_cost
        })
    
    utils.save_client_summary(summary)
