import os
import requests
import msal
import streamlit as st
import pandas as pd
from datetime import datetime
from msal_extensions import (
    FilePersistenceWithDataProtection, PersistedTokenCache, FilePersistence
)
# Microsoft Graph API settings
CLIENT_ID = "0806f2d1-af35-4f33-8ad8-5f29a36a02d9"
TENANT_ID = "3a7635f0-1d1e-4df5-8e24-716c29905a57"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Mail.Read", "Mail.ReadWrite", "Mail.Send", "User.Read"]
CACHE_PATH = os.path.join(os.path.expanduser("~"), ".msal_cache.bin")

if os.name == 'nt':  # Windows
    persistence = FilePersistenceWithDataProtection(CACHE_PATH)
else:  # macOS and Linux
    persistence = FilePersistence(CACHE_PATH)

cache = PersistedTokenCache(persistence)
app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)

def get_access_token():
    """
    Attempts to acquire an access token silently. If that fails, initiates the device flow for interactive authentication.
    """
    print(SCOPES)
    # Attempt to acquire token silently
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            return result["access_token"]
        else:
            st.warning(f"Error acquiring token silently: {result.get('error_description') if result else 'No result returned'}")
            # return None

    # If silent acquisition fails, initiate interactive flow
    flow = app.initiate_device_flow(scopes=SCOPES)

    if "user_code" not in flow:
        st.error("Failed to initiate device flow.")
        return None

    st.write(f"Please go to [https://microsoft.com/devicelogin](https://microsoft.com/devicelogin) and enter the code: {flow['user_code']}")
    result = app.acquire_token_by_device_flow(flow)
    
    if "access_token" in result:
        return result["access_token"]
    else:
        st.error(f"Error acquiring token interactively: {result.get('error_description')}")
        return None

def fetch_email_attachments(access_token, month, year):
    """
    Fetches emails and their attachments from the inbox for the specified month and year using the Microsoft Graph API.
    Results are cached in session state to prevent repeated fetching.
    """
    # Check if we already have cached results
    cache_key = f"email_attachments_{year}_{month}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    # Calculate the start and end dates for the selected month
    start_date = datetime(year, month, 1).strftime('%Y-%m-%dT%H:%M:%SZ')
    if month == 12:
        end_date = datetime(year + 1, 1, 1).strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        end_date = datetime(year, month + 1, 1).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Define the API endpoint with filtering based on receivedDateTime
    url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter=receivedDateTime ge {start_date} and receivedDateTime lt {end_date}&$expand=attachments"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = []

    if url:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            result = response.json()
            emails = result.get("value", [])

            for email in emails:
                sender = email.get("from", {}).get("emailAddress", {}).get("address", "Unknown")
                subject = email.get("subject", "No Subject")
                received_date = email.get("receivedDateTime", "")
                date_obj = datetime.strptime(received_date[:10], "%Y-%m-%d")
                month_name = date_obj.strftime("%B")
                day = date_obj.day

                # Only process emails with 'report' in the subject
                if "report" not in subject.lower():
                    continue

                # Process attachments
                for attachment in email.get("attachments", []):
                    attachment_name = attachment.get("name", "No Name")
                    data.append({
                        "Sender": sender,
                        "Attachment Name": attachment_name,
                        "Month": month_name,
                        "Day": day,
                        "Subject": subject
                    })
            
            # Check if there's another page of data
            url = result.get("@odata.nextLink")
        else:
            st.error(f"Error fetching emails: {response.json()}")
            

    # Store results in cache and return
    df = pd.DataFrame(data)
    st.session_state[cache_key] = df
    return df

def clear_cache():
    """Clear the token cache and reset session state."""
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
        app.remove_account(account=app.get_accounts())
        print("\nCache cleared.")
    for key in st.session_state.keys():
        del st.session_state[key]
    st.success("Cache cleared. Please authenticate again.")

def send_email(access_token, to_email, subject, body):
    """
    Send an email using Microsoft Graph API.
    """
    if not access_token:
        st.warning("No access token found.")
        return

    endpoint = "https://graph.microsoft.com/v1.0/me/sendMail"
    email_msg = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_email
                    }
                }
            ]
        }
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    response = requests.post(endpoint, headers=headers, json=email_msg)
    # print(response.json())
    if response.status_code == 202:
        st.success(f"Email successfully sent to {to_email}")
    else:
        st.error(f"Error sending email: {response.json()}")
