import streamlit as st
from datetime import datetime
import pandas as pd
import utils
from dt_fetch import *
from email_fetch import send_email, get_access_token

def show_dynatrace_tab():
    # Main container
    st.markdown("## Dynatrace License Management")
    
    # Add Client section
    with st.expander("➕ Add New Client", expanded=True):
        # Step 1: License type selection
        st.markdown("### Step 1: Select License Type")
        license_types = [
            "SaaS DPS",
            "SaaS Classic", 
            "Managed DPS",
            "Managed Classic"
        ]
        
        selected_license = st.selectbox(
            "Choose the license type:",
            license_types,
            key="license_type"
        )

        # Step 2: Client name input
        st.markdown("### Step 2: Enter Client Name")
        client_name = st.text_input(
            "Client Name:",
            key="client_name",
            placeholder="Enter client name..."
        )
        
        # Step 3: Data input method
        st.markdown("### Step 3: Choose Data Input Method")
        input_method = st.radio(
            "Select input method:",
            ["Manual", "Automatic"],
            horizontal=True,
            key="input_method"
        )
        
        if input_method == "Manual":
            st.markdown("#### Manual Data Input")
            expiry_date = st.date_input(
                "License Expiry Date:",
                key="expiry_date"
            )
            if selected_license in ["SaaS DPS", "Managed DPS"]:
                st.info("DPS License - Enter usage and limit manually")
                license_usage = st.number_input(
                    "License Usage:",
                    min_value=0,
                    key="license_usage"
                )
                license_limit = st.number_input(
                    "License Limit:", 
                    min_value=0,
                    key="license_limit"
                )
                host_usage = 0
                host_limit = 0
                dem_usage = 0
                dem_limit = 0
                davis_usage = 0
                davis_limit = 0
            elif selected_license in ["SaaS Classic", "Managed Classic"]:
                st.info("Classic License - Enter usage and limit manually")
                host_usage = st.number_input(
                    "Host Usage:",
                    min_value=0,
                    key="host_usage"
                )
                host_limit = st.number_input(
                    "Host Limit:", 
                    min_value=0,
                    key="host_limit"
                )
                dem_usage = st.number_input(
                    "DEM Usage:",
                    min_value=0,
                    key="dem_usage"
                )
                dem_limit = st.number_input(
                    "DEM Limit:", 
                    min_value=0,
                    key="dem_limit"
                )
                davis_usage = st.number_input(
                    "Davis Usage:",
                    min_value=0,
                    key="davis_usage"
                )
                davis_limit = st.number_input(
                    "Davis Limit:", 
                    min_value=0,
                    key="davis_limit"
                )
                license_usage = 0
                license_limit = 0
        else:
            st.markdown("#### Automatic Data Input")
            if selected_license in ["SaaS DPS", "Managed DPS"]:
                st.info("DPS License - Enter API credentials")
                client_id = st.text_input(
                    "Client ID:",
                    key="client_id"
                )
                client_secret = st.text_input(
                    "Client Secret:",
                    type="password",
                    key="client_secret"
                )
                account_urn = st.text_input(
                    "Account URN:",
                    key="account_urn"
                )
            elif selected_license == "Managed Classic":
                st.info("Classic License - Enter API credentials")
                api_key = st.text_input(
                    "Cluster API Token:",
                    type="password",
                    key="api_key"
                )
                base_url = st.text_input(
                    "Base URL:",
                    key="base_url"
                )
            else:
                st.warning("SaaS Classic does not support automatic fetching. Kindly input data manually.")

        if st.button("Add Client"):
            st.session_state.succeeded = False
            if not client_name:
                st.error("Please enter a client name")
            else:
                if input_method == "Manual":
                    # Save client with manual input
                    save_manual_client(
                        client_name,
                        selected_license,
                        expiry_date.isoformat(),
                        license_usage,
                        license_limit,
                        host_usage,
                        host_limit,
                        dem_usage,
                        dem_limit,
                        davis_usage,
                        davis_limit
                    )
                    st.session_state.succeeded = True
                else:
                    try:
                        # Generate access token
                        if selected_license in ["SaaS DPS", "Managed DPS"]:
                            access_token = get_dynatrace_access_token(
                                client_id, 
                                client_secret
                            )
                        elif selected_license == "Managed Classic":
                            access_token = api_key  # Directly use the Cluster API Token
                        else:
                            access_token = None
                            
                        if access_token:
                            # Fetch license data
                            if selected_license in ["SaaS DPS", "Managed DPS"]:
                                license_data = get_dps_license_data(
                                    account_urn,
                                    access_token
                                )
                            elif selected_license == "Managed Classic":
                                license_data = get_classic_license_data(
                                    access_token,
                                    base_url
                                )
                            
                            if license_data:
                                expiry_date = license_data.get('expiry_date')
                                usage = license_data.get('usage')
                                limit = license_data.get('limit')
                                host_usage = license_data.get('host usage')
                                host_limit = license_data.get('host limit')
                                dem_usage = license_data.get('dem usage')
                                dem_limit = license_data.get('dem limit')
                                davis_usage = license_data.get('davis usage')
                                davis_limit = license_data.get('davis limit')
                                details_cost = license_data.get('details (df)')

                                # Issue warning if any value is missing
                                if not expiry_date or usage is None or limit is None:
                                    st.warning("Some license data could not be fetched automatically. Please input missing values manually.")

                                # For saving, convert expiry_date to string if available
                                expiry_date_str = expiry_date.strftime('%Y-%m-%d') if isinstance(expiry_date, datetime) else expiry_date
                                usage_value = usage if usage is not None else 0
                                limit_value = limit if limit is not None else 0
                                host_usage_value = host_usage if host_usage is not None else 0
                                host_limit_value = host_limit if host_limit is not None else 0
                                dem_usage_value = dem_usage if dem_usage is not None else 0
                                dem_limit_value = dem_limit if dem_limit is not None else 0
                                davis_usage_value = davis_usage if davis_usage is not None else 0
                                davis_limit_value = davis_limit if davis_limit is not None else 0

                                # Save client with fetched data
                                if selected_license in ["SaaS DPS", "Managed DPS"]:
                                    save_dps_client(
                                        client_name,
                                        selected_license,
                                        client_id,
                                        client_secret,
                                        account_urn,
                                        expiry_date_str,
                                        usage_value,
                                        limit_value,
                                        details_cost
                                    )
                                elif selected_license == "Managed Classic":
                                    save_classic_client(
                                        client_name,
                                        selected_license,
                                        api_key,
                                        base_url,
                                        expiry_date_str,
                                        host_usage_value,
                                        host_limit_value,
                                        dem_usage_value,
                                        dem_limit_value,
                                        davis_usage_value,
                                        davis_limit_value,
                                        details_cost
                                        )
                            else:
                                st.warning("Failed to fetch some or all license data. Manual input may be required.")
                        else:
                            st.error("Failed to generate access token")
                    except Exception as e:
                        st.error(f"Error during automatic data fetch: {str(e)}")
                    if st.session_state.succeeded:
                        st.rerun()
                    

    # Display summary table section
    st.markdown("## License Summary")
    
    # Load and prepare summary data
    try:
        summary_data = utils.load_client_summary()
        client_summary_df = pd.DataFrame(summary_data if summary_data else [])
        
        if not client_summary_df.empty:
            # Add days remaining calculation
            if 'Expiry Date' in client_summary_df.columns:
                try:
                    # Attempt to convert the "Expiry Date" column to datetime
                    expiry_dt = pd.to_datetime(client_summary_df['Expiry Date'], errors='coerce')
                    # Convert to just the date part
                    client_summary_df['Expiry Date'] = expiry_dt.dt.date
                except Exception as e:
                    st.error(f"Error processing expiry dates: {e}")
                else:
                    client_summary_df['Days Remaining'] = client_summary_df['Expiry Date'].apply(
                        lambda x: (x - datetime.now().date()).days if pd.notnull(x) else None
                    )

            def get_usage_style(usage, limit):
                """
                Returns a style string based on the percentage of usage relative to the limit.
                - Red if usage is 80% or more of limit.
                - Yellow if usage is 50% or more of limit.
                - No style otherwise.
                """
                if limit == 0 or pd.isna(limit):
                    return ''
                percentage = usage / limit
                if percentage >= 0.8:
                    return 'background-color: red; color: white;'
                elif percentage >= 0.5:
                    return 'background-color: yellow; color: black;'
                return ''

            def style_usage_row(row, usage_cols, limit_cols):
                """
                Applies get_usage_style for each pair of usage and limit columns.
                
                Parameters:
                    row (Series): A row from the DataFrame.
                    usage_cols (list): List of column names that contain usage values.
                    limit_cols (list): List of column names that contain limit values.
                    
                Returns:
                    Series: A Series with the same index as usage_cols containing style strings.
                """
                styles = {}
                for usage, limit in zip(usage_cols, limit_cols):
                    print("row: ", row)
                    print("usage: ", usage)
                    print("limit: ", limit)
                    if limit not in row:
                        styles[usage] = ''
                        continue
                    styles[usage] = get_usage_style(row[usage], row[limit])
                return pd.Series(styles)

            # ------------------------------
            # Define the columns for display
            display_columns = [
                'Client Name', 'License Type', 'Expiry Date', 'Usage', 'Limit',
                'Host Usage', 'Host Limit', 'DEM Usage', 'DEM Limit',
                'Davis Usage', 'Davis Limit', 'Days Remaining'
            ]
            display_df = client_summary_df[display_columns]

            # Define specific columns for each license type
            dps_columns = ['Client Name', 'License Type', 'Expiry Date', 'Usage', 'Limit', 'Days Remaining']
            classic_columns = [
                'Client Name', 'License Type', 'Expiry Date',
                'Host Usage', 'Host Limit', 'DEM Usage', 'DEM Limit', 'Davis Usage', 'Davis Limit', 'Days Remaining'
            ]

            # Filter the DataFrame for DPS and Classic license types
            display_df_dps = display_df[display_df['License Type'].isin(["SaaS DPS", "Managed DPS"])][dps_columns]
            display_df_classic = display_df[display_df['License Type'].isin(["SaaS Classic", "Managed Classic"])][classic_columns]

            # ------------------------------
            # DISPLAY DPS LICENSES

            # Format numbers to 2 decimal places for DPS columns
            display_df_dps['Usage'] = display_df_dps['Usage'].apply(lambda x: round(float(x), 2))
            display_df_dps['Limit'] = display_df_dps['Limit'].apply(lambda x: round(float(x), 2))

            # Create a styled DataFrame for DPS licenses:
            # - Format numbers.
            # - Apply conditional styling to the "Usage" column.
            # - Keep the styling for "Days Remaining" using utils.highlight_days_remaining.
            styled_df_dps = display_df_dps.style \
                .format({'Usage': '{:.2f}', 'Limit': '{:.2f}', 'Days Remaining': '{:.0f}'}) \
                .apply(lambda row: style_usage_row(row, ['Usage'], ['Limit']), axis=1) \
                .map(utils.highlight_days_remaining, subset=['Days Remaining'])

            st.write("### DPS Licenses")
            st.dataframe(styled_df_dps, use_container_width=True, hide_index=True)

            # ------------------------------
            # DISPLAY CLASSIC LICENSES

            # Format numbers to 2 decimal places for Classic columns
            for col in ['Host Usage', 'Host Limit', 'DEM Usage', 'DEM Limit', 'Davis Usage', 'Davis Limit']:
                display_df_classic[col] = display_df_classic[col].apply(lambda x: round(float(x), 2))

            # Create a styled DataFrame for Classic licenses:
            # - Format numbers.
            # - Apply conditional styling to the usage columns.
            # - Keep the styling for "Days Remaining".
            styled_df_classic = display_df_classic.style \
                .format({
                    'Host Usage': '{:.2f}', 'Host Limit': '{:.2f}',
                    'DEM Usage': '{:.2f}', 'DEM Limit': '{:.2f}',
                    'Davis Usage': '{:.2f}', 'Davis Limit': '{:.2f}',
                    'Days Remaining': '{:.0f}'
                }) \
                .apply(lambda row: style_usage_row(row, ['Host Usage', 'DEM Usage', 'Davis Usage'],
                                                    ['Host Limit', 'DEM Limit', 'Davis Limit']),
                    axis=1) \
                .map(utils.highlight_days_remaining, subset=['Days Remaining'])

            st.write("### Classic Licenses")
            st.dataframe(styled_df_classic, use_container_width=True, hide_index=True)

            # Initialize edit mode if not set
            if "edit_mode" not in st.session_state:
                st.session_state.edit_mode = False

            # Refresh and Edit buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Refresh Data"):
                    try:
                        summary_data = utils.load_client_summary()
                        for client in summary_data:
                            st.write(f"Refreshing data for {client['Client Name']}...")
                            # Check license type
                            license_type = client['License Type']
                            
                            # Fetch updated data based on license type
                            if license_type in ["SaaS DPS", "Managed DPS"]:
                                # Get DPS credentials from client record
                                if not all(key in client for key in ['Client ID', 'Client Secret', 'Account URN']):
                                    st.warning(f"Missing DPS credentials for {client['Client Name']}")
                                    continue
                                    
                                access_token = get_dynatrace_access_token(
                                    client['Client ID'],
                                    client['Client Secret']
                                )
                                if access_token:
                                    license_data = get_dps_license_data(
                                        client['Account URN'],
                                        access_token
                                    )
                            elif license_type == "Managed Classic":
                                # Get Classic credentials from client record
                                if not all(key in client for key in ['API Key', 'Base URL']):
                                    st.warning(f"Missing Classic credentials for {client['Client Name']}")
                                    continue
                                    
                                license_data = get_classic_license_data(
                                    client['API Key'],
                                    client['Base URL']
                                )
                            else:
                                # st.warning(f"Automatic refresh not supported for {license_type}")
                                continue
                            
                            # Update only fetched fields
                            if license_data:
                                st.write(f"Updating data for {client['Client Name']}...")
                                st.write(client)
                                client['Expiry Date'] = license_data.get('expiry_date', client['Expiry Date'])
                                client['Host Usage'] = license_data.get('host usage', client['Host Usage'] if client['Host Usage'] is not None else 0)
                                client['Host Limit'] = license_data.get('host limit', client['Host Limit'] if client['Host Limit'] is not None else 0)
                                client['DEM Usage'] = license_data.get('dem usage', client['DEM Usage'] if client['DEM Usage'] is not None else 0)
                                client['DEM Limit'] = license_data.get('dem limit', client['DEM Limit'] if client['DEM Limit'] is not None else 0)
                                client['Davis Usage'] = license_data.get('davis usage', client['Davis Usage'] if client['Davis Usage'] is not None else 0)
                                client['Davis Limit'] = license_data.get('davis limit', client['Davis Limit'] if client['Davis Limit'] is not None else 0)
                                client['Usage'] = license_data.get('usage', client['Usage'] if client['Usage'] is not None else 0)
                                client['Limit'] = license_data.get('limit', client['Limit'] if client['Limit'] is not None else 0)
                                client['Cost Details'] = license_data.get('details (df)', client['Cost Details'])
                                client['Last Updated'] = datetime.now().isoformat()
                                
                            # Save updated data
                            if client["License Type"] in ["SaaS DPS", "Managed DPS"]:
                                st.write("Saving DPS client...")
                                save_dps_client(
                                    client['Client Name'],
                                    client['License Type'],
                                    client['Client ID'],
                                    client['Client Secret'],
                                    client['Account URN'],
                                    client['Expiry Date'],
                                    client['Usage'],
                                    client['Limit'],
                                    client['Cost Details']
                                )
                            elif client["License Type"] == "Managed Classic":
                                st.write("Saving Classic client...")
                                save_classic_client(
                                    client['Client Name'],
                                    client['License Type'],
                                    client['API Key'],
                                    client['Base URL'],
                                    client['Expiry Date'],
                                    client['Host Usage'],
                                    client['Host Limit'],
                                    client['DEM Usage'],
                                    client['DEM Limit'],
                                    client['Davis Usage'],
                                    client['Davis Limit'],
                                    client['Cost Details']
                                )
                        # utils.save_client_summary(summary_data)
                        st.success("Data refreshed successfully!")
                    except Exception as e:
                        st.error(f"Error refreshing data: {str(e)}")
                        st.exception(e)

            with col2:
                if st.button("Edit"):
                    st.session_state.edit_mode = not st.session_state.edit_mode

            # When in edit mode, show the editable table inside a form
            if st.session_state.edit_mode:
                with st.form("edit_form"):
                    st.markdown("### Edit")
                    # Display editable table
                    edited_df = st.data_editor(
                        display_df,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="dynamic",
                        column_config={
                            "Days Remaining": st.column_config.NumberColumn(
                                format="%d days",
                                help="Days until license expiration"
                            )
                        }
                    )
                    
                    # "Apply changes" submit button within the form
                    submit = st.form_submit_button("Apply changes")
                    if submit:
                        if not edited_df.equals(display_df):
                            # Merge edited columns back into full client records
                            updated_records = []
                            for idx, edited_row in edited_df.iterrows():
                                # Find matching full client record
                                client_name = edited_row['Client Name']
                                full_record = next((c for c in summary_data if c['Client Name'] == client_name), {})
                                
                                # Update all editable fields
                                full_record.update({
                                    'Client Name': edited_row['Client Name'],
                                    'License Type': edited_row['License Type'],
                                    'Expiry Date': edited_row['Expiry Date'],
                                    'Usage': edited_row['Usage'],
                                    'Limit': edited_row['Limit'],
                                    'Days Remaining': edited_row['Days Remaining']
                                })
                                updated_records.append(full_record)
                            
                            # Save changes and check result
                            save_success = utils.non_destructive_save_client_summary(updated_records)
                            
                            if save_success:
                                # Detect deleted rows by comparing client names
                                original_names = set(c['Client Name'] for c in summary_data)
                                edited_names = set(edited_df['Client Name'])
                                deleted_names = original_names - edited_names
                                
                                # If there are deleted rows, update the JSON file
                                if deleted_names:
                                    updated_clients = [c for c in summary_data if c['Client Name'] not in deleted_names]
                                    utils.update_client_summary_after_deletion(updated_clients)
                                    st.success(f"Deleted {len(deleted_names)} rows from client_summary.json.")
                                else:
                                    st.info("No rows have been deleted.")
                                
                                # Turn off edit mode after applying changes
                                st.session_state.edit_mode = False
                                st.success("Changes applied successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to save changes. Please try again.")
        else:
            st.info("No client data available. Add clients using the form above.")
            
    except Exception as e:
        st.error(f"Error loading summary data: {e}")
        st.exception(e)


    st.write("## Cost Details")

    if not client_summary_df.empty:
        # Select client from unique names
        chosen_client = st.selectbox("Select client", client_summary_df['Client Name'].unique())

        # Filter the DataFrame for the chosen client
        filtered_df = client_summary_df[client_summary_df['Client Name'] == chosen_client]

        if not filtered_df.empty:
            row = filtered_df.iloc[0]
            cost_details = None  # Default value

            if row['License Type'] in ["SaaS DPS", "Managed DPS"]:
                cost_details = row['Cost Details']

            elif row['License Type'] in ["SaaS Classic", "Managed Classic"]:
                # Compile quotas into a structured DataFrame
                cost_details = pd.DataFrame({
                    "Quotas": ["Host", "DEM", "Davis"],
                    "Usage": [row.get('Host Usage', 0), row.get('DEM Usage', 0), row.get('Davis Usage', 0)],
                    "Limit": [row.get('Host Limit', 0), row.get('DEM Limit', 0), row.get('Davis Limit', 0)]
                })

            # Display the cost details if available
            if cost_details is not None:
                if isinstance(cost_details, pd.DataFrame):
                    st.dataframe(cost_details, use_container_width=True, hide_index=True)
                else:
                    flattened_df = pd.json_normalize(cost_details)
                    st.dataframe(flattened_df, use_container_width=True, hide_index=True)
        else:
            st.write("Details are not available for this account.")
    else:
        st.warning("Client summary data is unavailable.")

    # Email Notification Section
    with st.expander("📧 Send License Expiry Notifications", expanded=True):
        st.markdown("## License Expiry Notifications")
        
        if not client_summary_df.empty:
            # Client selection dropdown
            client_names = client_summary_df['Client Name'].tolist()
            selected_client = st.selectbox("Select Client", client_names)
            
            # Get client details
            client_details = next((c for c in summary_data if c['Client Name'] == selected_client), {})
            
            # Email template
            default_subject = f"Dynatrace License Expiry Notification - {selected_client}"
            default_template = f"""Dear {selected_client},

This is a reminder that your Dynatrace license will expire on {client_details.get('Expiry Date', '[Expiry Date]')}.

Current License Usage:
- Usage: {round(float(client_details.get('Usage', 0)), 2)} units
- Limit: {round(float(client_details.get('Limit', 0)), 2)} units
- Days Remaining: {client_details.get('Days to Expiry', 0)} days

Please contact us if you need to renew or adjust your license.

Best regards,
Your Dynatrace Team
"""
            
            email_body = st.text_area("Email Template", value=default_template, height=300)
            
            # Recipient email
            recipient_email = st.text_input("Recipient Email Address", placeholder="Enter email address to send notification")
            
            # Send button
            if st.button("Send Notification"):
                if not recipient_email:
                    st.error("Please enter a recipient email address")
                else:
                    access_token = get_access_token()
                    if access_token:
                        try:
                            send_email(
                                access_token,
                                recipient_email,
                                default_subject,
                                email_body
                            )
                            st.success("Notification email sent successfully!")
                        except Exception as e:
                            st.error(f"Error sending email: {str(e)}")
                    else:
                        st.error("Failed to authenticate with Microsoft Graph API")
        else:
            st.info("No clients available to send notifications. Add clients using the form above.")
