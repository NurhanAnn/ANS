import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from email_fetch import get_access_token, fetch_email_attachments, clear_cache
from utils import load_data, save_data, manage_client_data, highlight_reports

def show_email_tab():
    st.header("📩 Email Attachment Organizer")
    manage_client_data()
    # Initialize session state
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "emails_fetched" not in st.session_state:
        st.session_state.emails_fetched = False

    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        date_range_option = st.radio(
            "Select date range type:",
            ["Single Month", "Custom Range"],
            index=0
        )

    if date_range_option == "Single Month":
        # Single month selection
        with col2:
            selected_date = st.date_input("Select a month and year", value=datetime.today())
            selected_month = selected_date.month
            selected_year = selected_date.year
            start_date = None
            end_date = None
    else:
        # Custom date range selection
        with col2:
            start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30))
            end_date = st.date_input("End Date", value=datetime.today())
            selected_month = None
            selected_year = None

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
        try:
            if date_range_option == "Single Month":
                email_data = fetch_email_attachments(
                    st.session_state.access_token, 
                    month=selected_month, 
                    year=selected_year
                )
            else:
                email_data = fetch_email_attachments(
                    st.session_state.access_token,
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )
        except Exception as e:
            st.error(f"Error fetching emails: {str(e)}")
            email_data = pd.DataFrame()

        if not email_data.empty:
            # Load client data
            client_df = load_data()

            # Initialize a dictionary to store organized data
            organized_data = {client: [] for client in client_df['Client Name']}

            # Iterate over each email attachment
            for _, email_row in email_data.iterrows():
                attachment_name = email_row['Attachment Name']
                attachment_date = f"{email_row['Day']}/{email_row['Month']}/{email_row['Year']}"

                # Check if the attachment name contains any associated string
                for _, client_row in client_df.iterrows():
                    associated_string = client_row['Associated String']
                    if associated_string in attachment_name:
                        organized_data[client_row['Client Name']].append({
                            'Attachment Name': attachment_name,
                            'Date': attachment_date
                        })
                        break  # Stop checking after the first match

             # Build summary data with dynamic month columns
            # Start with a base summary that includes Client Name and Expected Monthly Reports
            summary_data = {'Client Name': [], 'Expected Monthly Reports': []}
            month_columns = {}
            
            # Collect all month names from email_data (assuming email_row['Month'] is the month name)
            for _, email_row in email_data.iterrows():
                month_name = email_row['Month']
                if month_name not in month_columns:
                    month_columns[month_name] = []

            # Populate summary data per client
            for _, client_row in client_df.iterrows():
                client_name = client_row['Client Name']
                summary_data['Client Name'].append(client_name)
                summary_data['Expected Monthly Reports'].append(client_row['Monthly Reports'])
                for month in month_columns.keys():
                    total_reports = sum(1 for entry in organized_data[client_name] if month in entry['Date'])
                    month_columns[month].append(total_reports)
            
            # Add dynamic month columns to summary data
            for month, values in month_columns.items():
                summary_data[f'Total Reports Submitted ({month})'] = values

            summary_df = pd.DataFrame(summary_data)

            # Determine dynamic report columns
            report_columns = [col for col in summary_df.columns if col.startswith("Total Reports Submitted")]
            if report_columns:
                styled_df = summary_df.style.apply(
                    lambda x: [highlight_reports(v, e) for v, e in zip(x, summary_df['Expected Monthly Reports'])],
                    subset=report_columns
                )
                st.header("📊 Report Summary")
                st.dataframe(styled_df)
            else:
                st.header("📊 Report Summary")
                st.dataframe(summary_df)

            # Ensure organized_data is not empty
            if organized_data:
                # Extract company names and add an option for 'All Companies'
                company_names = list(organized_data.keys())
                company_names.insert(0, 'All Companies')

                # Create a dropdown menu for company selection
                selected_company = st.selectbox("Select a company to view attachments:", company_names)

                # Add a dropdown to filter attachments
                filter_option = st.selectbox("Filter attachments by:", ["All", "Incident Reports", "Monthly Reports"])

                # Function to filter attachments
                def filter_attachments(attachments, filter_option):
                    att = []
                    if filter_option == "Incident Reports":
                        for attachment in attachments:
                            if "incident" in attachment.get("Attachment Name", "").lower():
                                att.append(attachment)
                        return att
                    elif filter_option == "Monthly Reports":
                        for attachment in attachments:
                            if "monthly" in attachment.get("Attachment Name", "").lower():
                                att.append(attachment)
                        return att
                    return attachments

                # Display attachments based on the selected company
                if selected_company == 'All Companies':
                    for company, attachments in organized_data.items():
                        filtered_attachments = filter_attachments(attachments, filter_option)
                        if filtered_attachments:
                            st.subheader(f"Client: {company}")
                            attachment_df = pd.DataFrame(filtered_attachments)
                            st.dataframe(attachment_df)
                        else:
                            st.subheader(f"Client: {company}")
                            st.write("No attachments matched the selected filter.")
                else:
                    attachments = organized_data[selected_company]
                    filtered_attachments = filter_attachments(attachments, filter_option)
                    if filtered_attachments:
                        st.subheader(f"Client: {selected_company}")
                        attachment_df = pd.DataFrame(filtered_attachments)
                        st.dataframe(attachment_df)
                    else:
                        st.subheader(f"Client: {selected_company}")
                        st.write("No attachments matched the selected filter.")
            else:
                st.warning("No organized attachment data available.")
