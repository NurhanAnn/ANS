import os
import streamlit as st
import requests
import msal
import pandas as pd
import json
from datetime import datetime
from msal_extensions import (
    FilePersistenceWithDataProtection, PersistedTokenCache, FilePersistence
)
import streamlit as st
import plotly.graph_objects as go
from email_fetch import get_access_token, fetch_email_attachments, clear_cache, send_email
from dt_fetch import get_dynatrace_access_token, fetch_forecasted_budget, get_subscription_cost, get_subscriptions,flatten_cost_data
from utils import load_credentials, save_credentials, get_selected_credentials

# Streamlit UI
st.title("📊 Dashboard")

# Create tabs
tab1, tab2 = st.tabs(["Email Attachment Viewer", "Dynatrace License Tracker"])

with tab1:
    st.header("📩 Email Attachment Viewer")
    
    # Initialize session state
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "emails_fetched" not in st.session_state:
        st.session_state.emails_fetched = False

    # Fetch emails button
    if st.button("Fetch Emails"):
        st.session_state.access_token = get_access_token()
        if st.session_state.access_token:
            st.session_state.emails_fetched = True

    # Clear cache button
    if st.button("Clear Cache"):
        clear_cache()
        st.session_state.emails_fetched = False

    # Display email attachments if available
    if st.session_state.emails_fetched and st.session_state.access_token:
        df = fetch_email_attachments(st.session_state.access_token)
        if not df.empty:
            # Filtering options
            senders = df["Sender"].unique()
            selected_sender = st.selectbox("Filter by Sender", ["All"] + list(senders))
            
            keyword = st.text_input("Filter by Attachment Name")

            # Apply filters
            if selected_sender != "All":
                df = df[df["Sender"] == selected_sender]
            
            if keyword:
                df = df[df["Attachment Name"].str.contains(keyword, case=False, na=False)]

            # Display filtered table and count
            st.write(f"📄 Found {len(df)} attachments:")
            st.dataframe(df[["Sender", "Attachment Name", "Month", "Day"]])
        else:
            st.warning("No emails with attachments found.")

    with tab2:
        st.header("🔍 Dynatrace License Tracker")
        
        # Credential selection
        saved_credentials = load_credentials()
        if not saved_credentials:
            st.error("🚨 No Dynatrace accounts configured - add one in the sidebar first!")
            st.stop()

        with st.sidebar:
            st.header("🔑 Credentials Manager")
            selected_account = st.selectbox("Select Account", list(saved_credentials.keys()))
            
            st.markdown("---")
            with st.expander("➕ Add New Account"):
                with st.form("save_credentials_form"):
                    new_account_name = st.text_input("Account Name", placeholder="e.g., Production Account")
                    client_id = st.text_input("Client ID")
                    client_secret = st.text_input("Client Secret", type="password")
                    account_urn = st.text_input("Account URN")
                    
                    if st.form_submit_button("Save Credentials"):
                        if new_account_name and client_id and client_secret and account_urn:
                            save_credentials(new_account_name, client_id, client_secret, account_urn)
                            st.success("✅ Account saved!")
                        else:
                            st.error("❌ Please fill all fields")

        # Load selected credentials
        creds = get_selected_credentials(selected_account)
        st.session_state.client_id = creds["client_id"]
        st.session_state.client_secret = creds["client_secret"] 
        st.session_state.account_uuid = creds["account_urn"]
        
        # Initialize access token in session state
        if "dt_access_token" not in st.session_state:
            st.session_state.dt_access_token = None

        # Button to generate access token and fetch data
        if st.button("Generate Access Token"):
            if all([st.session_state.client_id, st.session_state.client_secret]):
                st.session_state.dt_access_token = get_dynatrace_access_token(st.session_state.client_id, st.session_state.client_secret)
                # print("\naccess token: ", st.session_state.dt_access_token)
                if st.session_state.dt_access_token:
                    st.success("Access token generated successfully!")
                    
                    # Immediately fetch and display subscriptions
                    subscriptions = get_subscriptions(st.session_state.account_uuid, st.session_state.dt_access_token)
                    # print("\nsubscriptions")
                    # print(subscriptions)
                    if subscriptions:
                        st.subheader("📑 Active Subscriptions")
                        
                        # Create DataFrame from subscriptions
                        subs_df = pd.DataFrame(subscriptions)
                        subs_df = subs_df[['name', 'startTime', 'endTime', 'status']]
                        subs_df['startTime'] = pd.to_datetime(subs_df['startTime']).dt.date
                        subs_df['endTime'] = pd.to_datetime(subs_df['endTime']).dt.date
                        
                        # Display subscriptions table
                        st.dataframe(subs_df, use_container_width=True)

        # Fetch subscriptions
        if st.session_state.dt_access_token:
            subscriptions = get_subscriptions(st.session_state.account_uuid, st.session_state.dt_access_token)
            if subscriptions:
                # Add selection dropdown
                subscription_options = {sub['name']: sub for sub in subscriptions}
                selected_subscription_name = st.selectbox("Select a Subscription:",
                                                        list(subscription_options.keys()))
                selected_subscription = subscription_options[selected_subscription_name]
                # Extract start and end times from the selected subscription
                sub_start_time = datetime.strptime(selected_subscription['startTime'], "%Y-%m-%d")
                sub_end_time = datetime.strptime(selected_subscription['endTime'], "%Y-%m-%d")
                
                # Create columns for subscription info
                col1, col2 = st.columns(2)
                
                with col1:
                    # Subscription period card
                    st.markdown(f"""
                    <div style="
                        padding: 1rem;
                        border-radius: 0.5rem;
                        background: #f0f2f6;
                        margin-bottom: 1rem;
                    ">
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span style="font-size: 1.5rem;">📅</span>
                            <h4 style="margin: 0;">Subscription Period</h4>
                        </div>
                        <p style="margin: 0.5rem 0 0 0; font-size: 1.1rem;">
                            {sub_start_time.date()} - {sub_end_time.date()}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Calculate subscription progress
                    total_days = (sub_end_time - sub_start_time).days
                    elapsed_days = (datetime.now() - sub_start_time).days
                    progress = min(max(elapsed_days / total_days, 0), 1)  # Clamp between 0 and 1
                    
                    st.progress(progress)
                    st.caption(f"{int(progress * 100)}% of subscription period elapsed")

                    # Fetch and display forecasted budget automatically
                    if st.session_state.account_uuid:
                        forecast_data = fetch_forecasted_budget(st.session_state.dt_access_token, st.session_state.account_uuid)
                        if forecast_data:
                            # st.subheader("Forecasted Budget Data")
                            # st.json(forecast_data)  # Display raw JSON data
                            budget = forecast_data.get("budget", 0)
                            forecast_pct = forecast_data.get("forecastBudgetPct", 0)

                            # Convert percentage to actual value
                            used_budget = (forecast_pct / 100) * budget
                            remaining_budget = budget - used_budget

                            # Decide color based on usage level
                            if forecast_pct >= 90:
                                used_color = "#FF3333"  # Red (Critical)
                            elif forecast_pct >= 70:
                                used_color = "#FFAA33"  # Orange (Warning)
                            else:
                                used_color = "#33CC33"  # Green (Safe)

                            # Create donut chart
                            fig = go.Figure(data=[go.Pie(
                                labels=["Used", "Remaining"],
                                values=[used_budget, remaining_budget],
                                hole=0.6,
                                marker=dict(colors=[used_color, "#E0E0E0"]),
                                hoverinfo="label+percent+value",
                                textinfo="none"  # Hide slice labels for a clean donut
                            )])

                            # Add an annotation in the center to show forecast percentage
                            fig.add_annotation(dict(
                                text=f"{forecast_pct:.1f}%",
                                x=0.5,
                                y=0.5,
                                font_size=22,
                                showarrow=False
                            ))

                            # Adjust layout to fit in a 400px-wide card
                            fig.update_layout(
                                width=300,   # Chart width
                                height=300,  # Chart height
                                margin=dict(l=0, r=0, t=0, b=0),
                                showlegend=False
                            )

                            # Create a container for the card
                            with st.container():
                                # Add card content
                                st.markdown('<h4>📊 Budget Forecast Usage</h4>', unsafe_allow_html=True)
                                st.plotly_chart(fig, use_container_width=False)

                with col2:
                    # Date range selection within the subscription's timeframe
                    start_date = st.date_input("Start Date:", sub_start_time, min_value=sub_start_time, max_value=sub_end_time)
                    end_date = st.date_input("End Date:", sub_end_time, min_value=sub_start_time, max_value=sub_end_time)
                    
                    if start_date > end_date:
                        st.error("Start date must be before end date.")
                    else:
                        # Fetch and display cost data
                        start_time = start_date.strftime("%Y-%m-%d")
                        end_time = end_date.strftime("%Y-%m-%d")
                        costs = get_subscription_cost(st.session_state.account_uuid, selected_subscription['uuid'], st.session_state.dt_access_token, start_time, end_time)
                        # print("\n\n\n\ncosts: ")
                        # print(costs)
                        cost_df = flatten_cost_data(costs)

                        # Display in Streamlit
                        if cost_df.empty:
                            st.warning("No cost data available for this subscription.")
                        else:
                            st.subheader("Cost Details")
                            st.dataframe(cost_df)

                            # Display total cost in a styled card
                            total_cost = cost_df["value"].sum()
                            currency = cost_df['currencyCode'].iloc[0]
                            st.markdown(f"""
                            <div style="
                                padding: 1rem;
                                border-radius: 0.5rem;
                                background: #f0f2f6;
                                margin: 1rem 0;
                            ">
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <span style="font-size: 1.5rem;">💵</span>
                                    <h4 style="margin: 0;">Total Cost</h4>
                                </div>
                                <p style="margin: 0.5rem 0 0 0; font-size: 1.5rem; font-weight: bold;">
                                    {currency} {total_cost:,.2f}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                with col1:
                    # Ensure budget data exists before plotting
                    budget = forecast_data.get("budget", 0)
                    
                    if budget > 0:
                        # Calculate used budget percentage
                        used_budget_pct = (total_cost / budget) * 100
                        remaining_budget = budget - total_cost

                        # Set color based on budget usage
                        if used_budget_pct >= 90:
                            used_color = "#FF3333"  # Red (Critical)
                        elif used_budget_pct >= 70:
                            used_color = "#FFAA33"  # Orange (Warning)
                        else:
                            used_color = "#33CC33"  # Green (Safe)

                        # Create donut chart for budget usage
                        budget_fig = go.Figure(data=[go.Pie(
                            labels=["Used Budget", "Remaining Budget"],
                            values=[total_cost, remaining_budget],
                            hole=0.6,
                            marker=dict(colors=[used_color, "#E0E0E0"]),
                            hoverinfo="label+percent+value",
                            textinfo="none"
                        )])

                        # Add annotation for percentage
                        budget_fig.add_annotation(dict(
                            text=f"{used_budget_pct:.1f}%",
                            x=0.5,
                            y=0.5,
                            font_size=22,
                            showarrow=False
                        ))

                        # Adjust layout
                        budget_fig.update_layout(
                            width=300,
                            height=300,
                            margin=dict(l=0, r=0, t=0, b=0),
                            showlegend=False
                        )

                        # Display the chart
                        with st.container():
                            st.markdown('<h4>💰 Current Budget Usage</h4>', unsafe_allow_html=True)
                            st.plotly_chart(budget_fig, use_container_width=False)
                    else:
                        st.warning("No account uuid.")
                # Input: Client's email address
                to_email = st.text_input("Client's Email Address")

                # Email template
                default_subject = "Dynatrace Subscription Usage Alert"
                current_usage = total_cost
                forecasted_usage = forecast_pct
                default_body = f"""
                <p>Dear Client,</p>
                <p>This is a notification regarding your current and forecasted Dynatrace subscription usage.</p>
                <p><strong>Current Usage:</strong>RM {current_usage}</p>
                <p><strong>Forecasted Usage:</strong>RM {forecasted_usage}</p>
                <p><strong>From total budget:</strong>RM {budget}</p>
                <p>If you have any questions or need further assistance, please contact us.</p>
                <p>Best regards,<br>Core Consulting Sdn Bhd</p>
                """

                # Input: Email subject and body with editing capability
                subject = st.text_input("Email Subject", value=default_subject)
                body = st.text_area("Email Body", value=default_body, height=300)

                # Send email button
                if st.button("Send Email"):
                    if to_email:
                        send_email(st.session_state.access_token, to_email, subject, body)
                    else:
                        st.error("Please enter the client's email address.")
        else:
            st.error("Generate access token first.")
