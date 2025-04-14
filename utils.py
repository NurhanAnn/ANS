import os
import json
import streamlit as st
import pandas as pd
from datetime import datetime

# Saved credentials for Dynatrace API
CREDENTIALS_FILE = "credentials.json"
# Define the path for the JSON file
DATA_FILE = 'client_data.json'
SUMMARY_FILE = 'client_summary.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            file_content = f.read()
            if not file_content.strip():
                return pd.DataFrame(columns=[
                    'Client Name',
                    'Associated String',
                    'Monthly Reports'
                ])
            
            data = json.loads(file_content)
            if isinstance(data, list) and len(data) > 0:
                new_data = []
                for client in data:
                    new_client = {
                        'Client Name': client['Client Name'],
                        'Associated String': client['Associated String'],
                        'Monthly Reports': client['Monthly Reports']
                    }
                    new_data.append(new_client)
                return pd.concat([pd.DataFrame(new_data)], ignore_index=True)
            else:
                st.warning("There is no client information.")
                return pd.DataFrame(columns=[
                    'Client Name',
                    'Associated String',
                    'Monthly Reports'
                ])
    else:
        # Create file with empty structure if it doesn't exist
        with open(DATA_FILE, 'w') as f:
            json.dump([], f)
        return pd.DataFrame(columns=[
            'Client Name', 
            'Associated String', 
            'Monthly Reports'
        ])

def save_data(df):
    if 'Reports' not in df.columns:
        df['Reports'] = [{} for _ in range(len(df))]
    with open(DATA_FILE, 'w') as f:
        json.dump(df.to_dict(orient='records'), f)

def load_credentials():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as file:
            try:
                return json.load(file)
            except:
                st.warning("Credentials file is empty.")
    return {}

def save_credentials(name, client_id, client_secret, account_urn, license_type="SaaS DPS"):
    credentials = load_credentials()
    credentials[name] = {
        "client_id": client_id,
        "client_secret": client_secret, 
        "account_urn": account_urn,
        "license_type": license_type
    }
    
    with open(CREDENTIALS_FILE, "w") as file:
        json.dump(credentials, file, indent=4)
    
    st.success(f"✅ Credentials saved under '{name}'")

def get_selected_credentials(name):
    credentials = load_credentials()
    return credentials.get(name, None)

def load_client_summary():
    """Load client summary data with validation and error handling"""
    # Create file if it doesn't exist with default structure
    if not os.path.exists(SUMMARY_FILE):
        default_data = {
            "clients": [],
            "last_updated": datetime.now().isoformat(),
            "version": 1.0
        }
        with open(SUMMARY_FILE, 'w') as f:
            json.dump(default_data, f)
    
    try:
        with open(SUMMARY_FILE, 'r') as f:
            data = json.load(f)
            
            # If data is a list (old format), convert to new format
            if isinstance(data, list):
                data = {
                    "clients": data,
                    "last_updated": datetime.now().isoformat(),
                    "version": 1.0
                }
                # Save converted format
                with open(SUMMARY_FILE, 'w') as f:
                    json.dump(data, f, indent=4)
            
            # Validate data structure
            if not isinstance(data, dict):
                raise ValueError("Invalid data format - expected dictionary")
                
            if "clients" not in data:
                data["clients"] = []
                
            # Validate each client entry
            valid_clients = []
            for client in data["clients"]:
                if not isinstance(client, dict):
                    continue
                if "Client Name" not in client:
                    continue
                    
                # Ensure required fields exist
                client.setdefault("License Type", "")
                client.setdefault("Expiry Date", "")
                client.setdefault("Usage", 0)
                client.setdefault("Limit", 0)
                client.setdefault("Last Updated", datetime.now().isoformat())
                
                valid_clients.append(client)
                
            data["clients"] = valid_clients
            return data["clients"]
            
            
    except (json.JSONDecodeError, IOError, ValueError) as e:
        print(f"Error loading client summary: {str(e)}")
        return []
    
def update_client_summary_after_deletion(updated_clients_df):
    """
    Update the client summary after deletion of clients.
    This function saves only the non-deleted client data to the summary file.
    """
    # Ensure updated_clients_df is a pandas DataFrame
    if hasattr(updated_clients_df, 'to_dict'):
        updated_clients_df = updated_clients_df.to_dict(orient='records')

    # Check if the summary file exists, if not create it
    if not os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, 'w') as f:
            json.dump({
                "clients": [],
                "last_updated": datetime.now().isoformat(),
                "version": 1.0
            }, f)

    # Load existing data from the summary file
    existing_data = load_client_summary()

    # Merge updated clients with the existing data
    client_names = {client['Client Name'] for client in updated_clients_df}
    print("client_names:")
    print(client_names)
    print("existing_data:")
    print(existing_data)
    merged_data = [client for client in existing_data 
                  if client['Client Name'] in client_names]
    # merged_data.extend(updated_clients_df)

    # Convert expiry date to ISO format if it's a date object
    for client in merged_data:
        expiry = client.get("Expiry Date")
        if expiry and hasattr(expiry, "isoformat"):
            client["Expiry Date"] = expiry.isoformat()

    # Save merged data to the file
    with open(SUMMARY_FILE, 'w') as f:
        json.dump({
            "clients": merged_data,
            "last_updated": datetime.now().isoformat(),
            "version": 1.0
        }, f, indent=4)

    print("Client summary updated successfully after deletion.")

def save_client_summary(summary_data):
    # Create file if it doesn't exist
    if not os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, 'w') as f:
            json.dump({
                "clients": [],
                "last_updated": datetime.now().isoformat(),
                "version": 1.0
            }, f)
    
    # Load existing data
    existing_data = load_client_summary()
    
    # Convert DataFrame to list of dicts if needed
    if hasattr(summary_data, 'to_dict'):
        summary_data = summary_data.to_dict(orient='records')
    
    # Ensure summary_data is a list
    if not isinstance(summary_data, list):
        summary_data = [summary_data]
    
    # Merge new data with existing, preserving existing entries
    client_names = {client['Client Name'] for client in summary_data}
    merged_data = [client for client in existing_data 
                  if client['Client Name'] not in client_names]
    merged_data.extend(summary_data)
    
    # Convert date objects to strings (e.g., ISO format)
    for client in merged_data:
        expiry = client.get("Expiry Date")
        if expiry and hasattr(expiry, "isoformat"):
            client["Expiry Date"] = expiry.isoformat()
    
    # Save merged data with proper structure
    with open(SUMMARY_FILE, 'w') as f:
        json.dump({
            "clients": merged_data,
            "last_updated": datetime.now().isoformat(),
            "version": 1.0
        }, f, indent=4)

def non_destructive_save_client_summary(edited_records):
    try:
        # Load the existing summary from the JSON file
        existing_data = load_client_summary() or []
        
        # Build a mapping from client name to full record for easy lookup
        existing_map = {client["Client Name"]: client for client in existing_data}
        
        # Build a mapping from client name to the edited record
        edited_map = {client["Client Name"]: client for client in edited_records}
        
        merged_clients = []
        
        # For each client in the existing data, update it if it's been edited
        for client_name, old_record in existing_map.items():
            if client_name in edited_map:
                # Merge the dictionaries: update only keys that are present in the edited record
                merged_record = old_record.copy()
                merged_record.update(edited_map[client_name])
                
                # Ensure proper date formatting
                if "Expiry Date" in merged_record:
                    expiry = merged_record["Expiry Date"]
                    if hasattr(expiry, "isoformat"):
                        merged_record["Expiry Date"] = expiry.isoformat()
                    elif isinstance(expiry, str):
                        try:
                            # Try to parse and reformat date string
                            dt = datetime.fromisoformat(expiry)
                            merged_record["Expiry Date"] = dt.isoformat()
                        except ValueError:
                            # If invalid date format, keep original
                            pass
                
                merged_clients.append(merged_record)
            else:
                # Client not edited; keep original record
                merged_clients.append(old_record)
        
        # In case there are new clients that were not in existing data, add them
        for client_name, new_record in edited_map.items():
            if client_name not in existing_map:
                # Ensure proper date formatting for new records
                if "Expiry Date" in new_record:
                    expiry = new_record["Expiry Date"]
                    if hasattr(expiry, "isoformat"):
                        new_record["Expiry Date"] = expiry.isoformat()
                    elif isinstance(expiry, str):
                        try:
                            dt = datetime.fromisoformat(expiry)
                            new_record["Expiry Date"] = dt.isoformat()
                        except ValueError:
                            pass
                merged_clients.append(new_record)
        
        # Save the merged data
        save_client_summary(merged_clients)
        return True
    except Exception as e:
        print(f"Error saving client summary: {str(e)}")
        return False

def get_client_credentials(client_name):
    """Get credentials for a specific client"""
    credentials = load_credentials()
    return credentials.get(client_name)

def save_client_credentials(client_name, credentials):
    """Save client credentials separately"""
    all_credentials = load_credentials()
    
    # Ensure credentials is converted to a dictionary
    if isinstance(credentials, pd.DataFrame):
        credentials = credentials.to_dict(orient='records')  # Convert DataFrame to list of dicts

    all_credentials[client_name] = credentials

    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(all_credentials, f, indent=4)

def manage_client_data():
    st.header("Client Data Management")

    client_df = load_data()

    edited_df = st.data_editor(
        client_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True
    )

    if st.button("Save Changes"):
        try:
            save_data(edited_df)
            st.success("Client data updated successfully.")
        except Exception as e:
            st.error(f"An error occurred while saving data: {e}")

def highlight_reports(val, expected):
    val = int(val)
    expected = int(expected)
    if val == 0:
        color = '#FFD6C9'
    elif val < expected:
        color = '#FFF8B8'
    else:
        color = '#E0FFCC'
    return f'background-color: {color}'

def highlight_days_remaining(val):
    try:
        days = int(val)
    except (ValueError, TypeError):
        return ""  # no styling if value is not a valid integer

    # Define thresholds: 2 months ~ 60 days, 6 months ~ 180 days
    if days <= 60:
        color = "#FFCCCC"  # Red for 2 months or less
    elif days <= 180:
        color = "#FFFF99"  # Yellow for between 2 and 6 months
    else:
        color = "#CCFFCC"  # Green for more than 6 months

    return f'background-color: {color}'
