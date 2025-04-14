import os
import requests
import msal
import streamlit as st
import pandas as pd
from datetime import datetime
import asyncio
import aiohttp
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

async def fetch_month_emails(session, access_token, month, year):
    """
    Fetches emails for a single month using aiohttp session
    """
    # Calculate the start and end dates for the selected month
    try:
        start_date_dt = datetime(year, month, 1)
    except ValueError as e:
        st.error(f"Invalid month/year provided: {e}")
        return pd.DataFrame()

    start_date = start_date_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    if month == 12:
        end_date_dt = datetime(year + 1, 1, 1)
    else:
        end_date_dt = datetime(year, month + 1, 1)
    end_date = end_date_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    url = (f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?"
           f"$filter=receivedDateTime ge {start_date} and receivedDateTime lt {end_date}"
           f"&$expand=attachments")
        #    f"&$top=10")
    headers = {"Authorization": f"Bearer {access_token}"}
    data = []
    
    # Initialize progress
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_emails = 0
    processed_emails = 0
    valid_attachments = 0

    while url:
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    emails = result.get("value", [])
                    total_emails += len(emails)
                    
                    for email in emails:
                        processed_emails += 1
                        progress = min(processed_emails / max(total_emails, 1), 1.0)
                        progress_bar.progress(progress)
                        status_text.text(f"Processing {processed_emails}/{total_emails} emails ({valid_attachments} valid attachments)...")
                        received_date = email.get("receivedDateTime", "")
                        try:
                            date_obj = datetime.strptime(received_date[:10], "%Y-%m-%d")
                        except (ValueError, TypeError):
                            continue

                        sender = email.get("from", {}).get("emailAddress", {}).get("address", "Unknown")
                        subject = email.get("subject", "No Subject")
                        month_name = date_obj.strftime("%B")
                        day = date_obj.day
                        Year = date_obj.year

                        look_for = ["report", "laporan", "performance analysis"]
                        if not any(word in subject.lower() for word in look_for):
                            continue

                        for attachment in email.get("attachments", []):
                            attachment_name = attachment.get("name", "No Name")
                            # Only process PDF and PPTX attachments
                            ext = os.path.splitext(attachment_name)[1].lower()
                            if ext != '.png':  # Exclude PNG attachments
                                data.append({
                                    "Sender": sender,
                                    "Attachment Name": attachment_name,
                                    "Year": Year,
                                    "Month": month_name,
                                    "Day": day,
                                    "Subject": subject
                                })

                    url = result.get("@odata.nextLink")
                else:
                    error_info = await response.json()
                    st.error(f"Error fetching emails: {error_info}")
                    return pd.DataFrame()
        except Exception as e:
            st.error(f"Network error occurred: {e}")
            return pd.DataFrame()

    df = pd.DataFrame(data)
    
    # Generate monthly report summary grouped by attachment name
    if not df.empty:
        monthly_summary = df.groupby(['Attachment Name', 'Month']).size().reset_index(name='Report Count')
        monthly_summary = monthly_summary.pivot(index='Attachment Name', columns='Month', values='Report Count').fillna(0)
        st.session_state['monthly_report_summary'] = monthly_summary
    
    return df

def fetch_email_attachments(access_token, month=None, year=None, start_date=None, end_date=None):
    """
    Fetches emails and their attachments from the inbox for the specified month/year or date range.
    Uses asyncio for concurrent fetching when a date range is provided.
    """
    if month is not None and year is not None:
        # Single month fetch (original behavior)
        cache_key = f"email_attachments_{year}_{month}"
        if cache_key in st.session_state:
            return st.session_state[cache_key]
        
        async def fetch_single_month():
            async with aiohttp.ClientSession() as session:
                return await fetch_month_emails(session, access_token, month, year)
        
        df = asyncio.run(fetch_single_month())
        st.session_state[cache_key] = df
        return df
    elif start_date is not None and end_date is not None:
        # Date range fetch with concurrent month fetching
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Generate list of (year, month) tuples to fetch
        months_to_fetch = []
        current_dt = start_dt.replace(day=1)
        while current_dt <= end_dt:
            months_to_fetch.append((current_dt.year, current_dt.month))
            if current_dt.month == 12:
                current_dt = current_dt.replace(year=current_dt.year + 1, month=1)
            else:
                current_dt = current_dt.replace(month=current_dt.month + 1)
        
        # Fetch all months concurrently
        async def fetch_all_months():
            async with aiohttp.ClientSession() as session:
                tasks = [
                    fetch_month_emails(session, access_token, month, year)
                    for year, month in months_to_fetch
                ]
                results = await asyncio.gather(*tasks)
                return pd.concat(results, ignore_index=True)
        
        cache_key = f"email_attachments_{start_date}_{end_date}"
        if cache_key in st.session_state:
            return st.session_state[cache_key]
        
        df = asyncio.run(fetch_all_months())
        st.session_state[cache_key] = df
        return df
    else:
        st.error("Invalid parameters: must provide either month/year or start_date/end_date")
        return pd.DataFrame()

def clear_cache():
    """Clear the token cache and reset session state."""
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
        for accnt in app.get_accounts():
            app.remove_account(accnt)
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
