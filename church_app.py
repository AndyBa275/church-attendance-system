import streamlit as st
import pandas as pd
import os
from datetime import datetime, date, timedelta
import time
import gspread
from google.oauth2.service_account import Credentials
import json

# Google Sheets Configuration
SPREADSHEET_ID = "1xj89TMBgyBnEByNQD6jluLGBt07AuPwFCEq0u0H1bO8"
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# Tab names in Google Sheet
ATTENDANCE_TAB = "Church Attendance"
OFFERINGS_TAB = "Church Offerings"
USERS_TAB = "Church Users"
ANNOUNCEMENTS_TAB = "Church Announcements"
MEMBERS_TAB = "Members Master"
WELFARE_TAB = "Welfare Records"
ATTENDANCE_SUMMARY_TAB = "Attendance Summary"

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.home_cell = None

@st.cache_resource
def get_google_sheets_client():
    """Initialize Google Sheets client"""
    try:
        # Try to load from Streamlit secrets first (for cloud deployment)
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            credentials_dict = dict(st.secrets['gcp_service_account'])
        else:
            # Load from local credentials.json file
            creds_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
            with open(creds_path, 'r') as f:
                credentials_dict = json.load(f)
        
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=SCOPE)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

def get_sheet_data(tab_name):
    """Read data from Google Sheet tab"""
    try:
        client = get_google_sheets_client()
        if client is None:
            return pd.DataFrame()
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(tab_name)
        
        # Get all values including headers
        all_values = worksheet.get_all_values()
        
        # Check if sheet has data (more than just headers)
        if not all_values or len(all_values) <= 1:
            # Return empty dataframe with expected columns
            if tab_name == MEMBERS_TAB:
                return pd.DataFrame(columns=['Member_Name', 'Home_Cell_Group', 'Phone', 'Email', 'Gender', 
                                            'Date of Birth', 'Marital Status', 'Member Type', 'City'])
            elif tab_name == ATTENDANCE_TAB:
                return pd.DataFrame(columns=['Date', 'Home_Cell_Group', 'Member_Name', 'Present', 
                                            'Recorded_By', 'Timestamp'])
            elif tab_name == OFFERINGS_TAB:
                return pd.DataFrame(columns=['Date', 'Amount_GHS', 'Meeting_Type', 'Description', 
                                            'Entered_By', 'Timestamp'])
            elif tab_name == USERS_TAB:
                return pd.DataFrame(columns=['Username', 'Password', 'Role', 'Home_Cell_Group'])
            elif tab_name == ANNOUNCEMENTS_TAB:
                return pd.DataFrame(columns=['Date', 'Title', 'Message', 'Posted_By', 'Timestamp'])
            elif tab_name == WELFARE_TAB:
                return pd.DataFrame(columns=['Date', 'Member_Name', 'Home_Cell_Group', 'Amount_GHS', 
                                            'Collected_By', 'Timestamp'])
            elif tab_name == ATTENDANCE_SUMMARY_TAB:
                return pd.DataFrame(columns=['Member_Name', 'Home_Cell_Group', 'Last_3_Attendances', 
                                            'Missed_Count', 'Status', 'Last_Updated'])
            return pd.DataFrame()
        
        # Get data as records (skips header row)
        data = worksheet.get_all_records()
        
        if not data:
            # Return empty dataframe with headers from sheet
            return pd.DataFrame(columns=all_values[0])
        
        return pd.DataFrame(data)
    except Exception as e:
        # Return empty dataframe on error instead of showing error
        if tab_name == MEMBERS_TAB:
            return pd.DataFrame(columns=['Member_Name', 'Home_Cell_Group', 'Phone', 'Email', 'Gender', 
                                        'Date of Birth', 'Marital Status', 'Member Type', 'City'])
        elif tab_name == ATTENDANCE_TAB:
            return pd.DataFrame(columns=['Date', 'Home_Cell_Group', 'Member_Name', 'Present', 
                                        'Recorded_By', 'Timestamp'])
        elif tab_name == OFFERINGS_TAB:
            return pd.DataFrame(columns=['Date', 'Amount_GHS', 'Meeting_Type', 'Description', 
                                        'Entered_By', 'Timestamp'])
        elif tab_name == USERS_TAB:
            return pd.DataFrame(columns=['Username', 'Password', 'Role', 'Home_Cell_Group'])
        elif tab_name == ANNOUNCEMENTS_TAB:
            return pd.DataFrame(columns=['Date', 'Title', 'Message', 'Posted_By', 'Timestamp'])
        elif tab_name == WELFARE_TAB:
            return pd.DataFrame(columns=['Date', 'Member_Name', 'Home_Cell_Group', 'Amount_GHS', 
                                        'Collected_By', 'Timestamp'])
        elif tab_name == ATTENDANCE_SUMMARY_TAB:
            return pd.DataFrame(columns=['Member_Name', 'Home_Cell_Group', 'Last_3_Attendances', 
                                        'Missed_Count', 'Status', 'Last_Updated'])
        return pd.DataFrame()

def write_sheet_data(tab_name, df):
    """Write data to Google Sheet tab"""
    try:
        client = get_google_sheets_client()
        if client is None:
            return False
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(tab_name)
        
        # Clear existing data
        worksheet.clear()
        
        # Write headers and data
        if not df.empty:
            # Convert dataframe to list of lists
            data = [df.columns.tolist()] + df.values.tolist()
            worksheet.update('A1', data)
        else:
            # Just write headers
            worksheet.update('A1', [df.columns.tolist()])
        
        return True
    except Exception as e:
        st.error(f"Error writing to {tab_name}: {str(e)}")
        return False

def append_sheet_data(tab_name, new_data):
    """Append new row(s) to Google Sheet tab"""
    try:
        client = get_google_sheets_client()
        if client is None:
            return False
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(tab_name)
        
        # Convert to list format
        if isinstance(new_data, pd.DataFrame):
            rows = new_data.values.tolist()
        elif isinstance(new_data, dict):
            rows = [list(new_data.values())]
        else:
            rows = [new_data]
        
        worksheet.append_rows(rows)
        return True
    except Exception as e:
        st.error(f"Error appending to {tab_name}: {str(e)}")
        return False

def verify_login(username, password):
    """Verify user credentials"""
    users_df = get_sheet_data(USERS_TAB)
    if not users_df.empty:
        user = users_df[(users_df['Username'] == username) & (users_df['Password'] == password)]
        if not user.empty:
            return True, user.iloc[0]['Role'], user.iloc[0]['Home_Cell_Group']
    return False, None, None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_members_master():
    """Get Members Master sheet - cached to avoid repeated slow fetches"""
    return get_sheet_data(MEMBERS_TAB)

def get_home_cell_groups():
    """Get unique home cell groups from members"""
    members_df = get_cached_members_master()
    if not members_df.empty and 'Home_Cell_Group' in members_df.columns:
        return sorted(members_df['Home_Cell_Group'].dropna().unique().tolist())
    return []

def get_members_by_cell(home_cell):
    """Get members for a specific home cell - with caching"""
    members_df = get_cached_members_master()
    if not members_df.empty and 'Home_Cell_Group' in members_df.columns:
        cell_members = members_df[members_df['Home_Cell_Group'] == home_cell]
        if 'Member_Name' in cell_members.columns:
            return cell_members[['Member_Name', 'Phone', 'Home_Cell_Group']].dropna(subset=['Member_Name'])
    return pd.DataFrame()

def update_attendance_summary():
    """Update the attendance summary with members at risk"""
    try:
        # Get attendance records
        attendance_df = get_sheet_data(ATTENDANCE_TAB)
        members_df = get_cached_members_master()
        
        if attendance_df.empty or members_df.empty:
            return False
        
        # Get unique dates (last 3 church services)
        if 'Date' in attendance_df.columns:
            unique_dates = sorted(attendance_df['Date'].unique(), reverse=True)[:3]
            
            if len(unique_dates) < 3:
                # Not enough data yet
                return False
            
            summary_records = []
            
            # Process each member
            for _, member in members_df.iterrows():
                member_name = member['Member_Name']
                home_cell = member['Home_Cell_Group']
                
                # Get member's last 3 attendance records
                member_attendance = attendance_df[
                    (attendance_df['Member_Name'] == member_name) & 
                    (attendance_df['Date'].isin(unique_dates))
                ]
                
                # Count attendance
                attendance_status = []
                missed_count = 0
                
                for date_val in unique_dates:
                    date_record = member_attendance[member_attendance['Date'] == date_val]
                    if not date_record.empty:
                        status = date_record.iloc[0]['Present']
                        attendance_status.append(status)
                        if status == 'No':
                            missed_count += 1
                    else:
                        # No record = assumed absent
                        attendance_status.append('No')
                        missed_count += 1
                
                # Determine risk status
                if missed_count >= 2:
                    status = "⚠️ DANGER - Contact Member"
                    
                    summary_records.append({
                        'Member_Name': member_name,
                        'Home_Cell_Group': home_cell,
                        'Last_3_Attendances': ' | '.join(attendance_status),
                        'Missed_Count': missed_count,
                        'Status': status,
                        'Last_Updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            # Create summary dataframe (only members at risk)
            if summary_records:
                summary_df = pd.DataFrame(summary_records)
                return write_sheet_data(ATTENDANCE_SUMMARY_TAB, summary_df)
            else:
                # No members at risk - clear the sheet but keep headers
                empty_df = pd.DataFrame(columns=['Member_Name', 'Home_Cell_Group', 'Last_3_Attendances', 
                                                'Missed_Count', 'Status', 'Last_Updated'])
                return write_sheet_data(ATTENDANCE_SUMMARY_TAB, empty_df)
        
        return False
    except Exception as e:
        st.error(f"Error updating attendance summary: {str(e)}")
        return False

# Page Functions
def login_page():
    """Login page"""
    st.title("🏛️ Church Attendance System")
    st.subheader("Please Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", use_container_width=True):
            if username and password:
                success, role, home_cell = verify_login(username, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = role
                    st.session_state.home_cell = home_cell
                    st.success(f"Welcome {username}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
                    # Debug info for troubleshooting
                    with st.expander("🔍 Debug Info (Admin Only)"):
                        users_df = get_sheet_data(USERS_TAB)
                        if not users_df.empty:
                            st.write("Available usernames:", users_df['Username'].tolist())
                            st.caption("Check spelling and case sensitivity")
            else:
                st.warning("Please enter both username and password")
        
        st.divider()
        st.info("📱 This system works on mobile phones! Access via browser.")

def attendance_page():
    """Attendance marking page"""
    st.title("📋 Mark Attendance")
    
    # Check role
    if st.session_state.role not in ['Home Cell Leader', 'Admin']:
        st.warning("You don't have permission to mark attendance.")
        st.info(f"💡 Your current role is: '{st.session_state.role}' - it should be 'Admin' or 'Home Cell Leader'")
        return
    
    # Select date
    attendance_date = st.date_input("Select Date", value=date.today())
    
    # Get home cell
    if st.session_state.role == 'Admin':
        home_cells = get_home_cell_groups()
        if not home_cells:
            st.warning("No home cell groups found in Members Master sheet.")
            return
        selected_cell = st.selectbox("Select Home Cell Group", home_cells)
    else:
        selected_cell = st.session_state.home_cell
        st.info(f"Your Home Cell: **{selected_cell}**")
    
    if selected_cell:
        # Add refresh button for members
        col_title, col_refresh = st.columns([3, 1])
        with col_title:
            pass
        with col_refresh:
            if st.button("🔄 Refresh Members", help="Reload members from Google Sheets"):
                # Clear the cache
                st.cache_data.clear()
                st.rerun()
        
        # Get members
        members = get_members_by_cell(selected_cell)
        
        if not members.empty:
            st.subheader(f"Members in {selected_cell}")
            st.write(f"Total Members: {len(members)}")
            
            # Check if attendance already marked for this date and cell
            attendance_df = get_sheet_data(ATTENDANCE_TAB)
            existing_attendance = pd.DataFrame()
            if not attendance_df.empty:
                existing_attendance = attendance_df[
                    (attendance_df['Date'] == str(attendance_date)) & 
                    (attendance_df['Home_Cell_Group'] == selected_cell)
                ]
            
            # Create attendance form
            attendance_dict = {}
            
            for idx, row in members.iterrows():
                member_name = row['Member_Name']
                
                # Check if already marked
                default_value = False
                if not existing_attendance.empty:
                    member_record = existing_attendance[existing_attendance['Member_Name'] == member_name]
                    if not member_record.empty:
                        default_value = member_record.iloc[0]['Present'] == 'Yes'
                
                # Use unique key with index to handle duplicate names
                unique_key = f"attendance_{selected_cell}_{idx}_{member_name}"
                attendance_dict[member_name] = st.checkbox(
                    f"{member_name}", 
                    value=default_value,
                    key=unique_key
                )
            
            st.divider()
            
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col2:
                if st.button("💾 Submit Attendance", use_container_width=True, type="primary"):
                    with st.spinner("Saving attendance..."):
                        # Prepare attendance records
                        new_records = []
                        for member_name, present in attendance_dict.items():
                            new_records.append({
                                'Date': str(attendance_date),
                                'Home_Cell_Group': selected_cell,
                                'Member_Name': member_name,
                                'Present': 'Yes' if present else 'No',
                                'Recorded_By': st.session_state.username,
                                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            })
                        
                        # Read existing attendance
                        attendance_df = get_sheet_data(ATTENDANCE_TAB)
                        
                        # Remove existing records for this date and cell (to update)
                        if not attendance_df.empty:
                            attendance_df = attendance_df[
                                ~((attendance_df['Date'] == str(attendance_date)) & 
                                  (attendance_df['Home_Cell_Group'] == selected_cell))
                            ]
                        
                        # Append new records
                        new_df = pd.DataFrame(new_records)
                        attendance_df = pd.concat([attendance_df, new_df], ignore_index=True)
                        
                        # Save to Google Sheets
                        if write_sheet_data(ATTENDANCE_TAB, attendance_df):
                            # Update attendance summary
                            update_attendance_summary()
                            
                            present_count = sum(attendance_dict.values())
                            st.success(f"✅ Attendance saved! {present_count}/{len(members)} members present")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to save attendance. Please try again.")
        else:
            st.warning(f"No members found in {selected_cell}")
            
            # Debug information
            with st.expander("🔍 Debug Info - Why are members not showing?"):
                st.write(f"**Selected Cell:** `{selected_cell}`")
                
                # Try to fetch again and show what we get
                all_members = get_cached_members_master()
                
                if all_members.empty:
                    st.error("❌ Cannot read Members Master sheet from Google Sheets!")
                    st.info("Check that the 'Members Master' tab exists and has data.")
                else:
                    st.success(f"✅ Members Master sheet loaded: {len(all_members)} total members")
                    
                    if 'Home_Cell_Group' in all_members.columns:
                        unique_cells = all_members['Home_Cell_Group'].unique()
                        st.write(f"**Available Home Cell Groups:** {list(unique_cells)}")
                        
                        # Check for close matches
                        exact_match = all_members[all_members['Home_Cell_Group'] == selected_cell]
                        st.write(f"**Exact matches for '{selected_cell}':** {len(exact_match)}")
                        
                        if len(exact_match) == 0:
                            st.warning("⚠️ No exact matches found. Check spelling in Google Sheet!")
                    else:
                        st.error("❌ 'Home_Cell_Group' column not found in Members Master sheet!")
                        st.write("Available columns:", list(all_members.columns))
                
                if st.button("Clear Cache & Retry", key="debug_retry"):
                    st.cache_data.clear()
                    st.rerun()

def welfare_page():
    """Welfare contribution collection page"""
    st.title("💝 Welfare Contributions")
    
    st.info("💡 Search for members and record their welfare contributions")
    
    # Search for members
    search_term = st.text_input("🔍 Search Member Name", placeholder="Type member name...")
    
    members_df = get_cached_members_master()
    
    if search_term and not members_df.empty:
        # Search in Member_Name column
        results = members_df[members_df['Member_Name'].str.contains(search_term, case=False, na=False)]
        
        if not results.empty:
            st.success(f"Found {len(results)} member(s)")
            
            # Multi-select members
            selected_members = st.multiselect(
                "Select Members (can select multiple)",
                options=results['Member_Name'].tolist(),
                format_func=lambda x: f"{x} - {results[results['Member_Name']==x]['Home_Cell_Group'].iloc[0]}"
            )
            
            if selected_members:
                st.divider()
                st.subheader("Enter Welfare Contributions")
                
                # Collect contributions
                contributions = {}
                
                col1, col2 = st.columns(2)
                
                with col1:
                    contribution_date = st.date_input("Date", value=date.today())
                
                with col2:
                    # Option for single amount or individual amounts
                    amount_type = st.radio("Amount Entry", ["Same for all", "Individual amounts"])
                
                if amount_type == "Same for all":
                    common_amount = st.number_input("Amount (GHS) for all selected", min_value=0.0, step=5.0)
                    for member in selected_members:
                        contributions[member] = common_amount
                else:
                    for member in selected_members:
                        member_cell = results[results['Member_Name']==member]['Home_Cell_Group'].iloc[0]
                        contributions[member] = st.number_input(
                            f"Amount (GHS) for {member} ({member_cell})", 
                            min_value=0.0, 
                            step=5.0,
                            key=f"welfare_{member}"
                        )
                
                st.divider()
                
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("💾 Submit Contributions", use_container_width=True, type="primary"):
                        # Validate at least one amount entered
                        if all(amount == 0 for amount in contributions.values()):
                            st.warning("Please enter at least one contribution amount")
                        else:
                            with st.spinner("Saving contributions..."):
                                new_records = []
                                total_amount = 0
                                
                                for member_name, amount in contributions.items():
                                    if amount > 0:  # Only save non-zero contributions
                                        member_cell = results[results['Member_Name']==member_name]['Home_Cell_Group'].iloc[0]
                                        new_records.append({
                                            'Date': str(contribution_date),
                                            'Member_Name': member_name,
                                            'Home_Cell_Group': member_cell,
                                            'Amount_GHS': amount,
                                            'Collected_By': st.session_state.username,
                                            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        })
                                        total_amount += amount
                                
                                if new_records:
                                    # Append to welfare sheet
                                    new_df = pd.DataFrame(new_records)
                                    if append_sheet_data(WELFARE_TAB, new_df):
                                        st.success(f"✅ {len(new_records)} contribution(s) recorded! Total: GHS {total_amount:.2f}")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error("❌ Failed to save contributions. Please try again.")
        else:
            st.warning("No members found with that name")
    
    # Display recent contributions
    st.divider()
    st.subheader("Recent Welfare Contributions")
    
    welfare_df = get_sheet_data(WELFARE_TAB)
    if not welfare_df.empty:
        # Sort by timestamp
        if 'Timestamp' in welfare_df.columns:
            welfare_df = welfare_df.sort_values('Timestamp', ascending=False)
        
        # Show recent records
        recent = welfare_df.head(20)
        st.dataframe(
            recent[['Date', 'Member_Name', 'Home_Cell_Group', 'Amount_GHS', 'Collected_By']], 
            use_container_width=True, 
            hide_index=True
        )
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_welfare = welfare_df['Amount_GHS'].sum()
            st.metric("Total Welfare Collected", f"GHS {total_welfare:,.2f}")
        
        with col2:
            unique_contributors = welfare_df['Member_Name'].nunique()
            st.metric("Unique Contributors", unique_contributors)
        
        with col3:
            if 'Date' in welfare_df.columns:
                # Today's collection
                today_welfare = welfare_df[welfare_df['Date'] == str(date.today())]
                today_total = today_welfare['Amount_GHS'].sum() if not today_welfare.empty else 0
                st.metric("Today's Collection", f"GHS {today_total:.2f}")
    else:
        st.info("No welfare contributions recorded yet")

def attendance_summary_page():
    """Attendance summary - members at risk"""
    st.title("⚠️ Attendance Summary - Members at Risk")
    
    # Check role - only cell leaders and admin
    if st.session_state.role not in ['Home Cell Leader', 'Admin']:
        st.warning("Only Home Cell Leaders and Admins can view this page.")
        return
    
    st.info("📞 Members who missed 2 or more out of the last 3 church services")
    
    # Add refresh button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh Summary"):
            with st.spinner("Updating attendance summary..."):
                if update_attendance_summary():
                    st.success("Summary updated!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Not enough attendance data yet (need at least 3 services)")
    
    # Get summary data
    summary_df = get_sheet_data(ATTENDANCE_SUMMARY_TAB)
    
    if not summary_df.empty:
        # Filter by home cell if not admin
        if st.session_state.role == 'Home Cell Leader':
            summary_df = summary_df[summary_df['Home_Cell_Group'] == st.session_state.home_cell]
            st.subheader(f"Your Cell: {st.session_state.home_cell}")
        
        if not summary_df.empty:
            st.metric("Members Needing Contact", len(summary_df))
            
            st.divider()
            
            # Display members at risk
            for idx, row in summary_df.iterrows():
                with st.expander(f"⚠️ {row['Member_Name']} - {row['Home_Cell_Group']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Last 3 Attendances:** {row['Last_3_Attendances']}")
                        st.write(f"**Missed Count:** {row['Missed_Count']} out of 3")
                        st.write(f"**Status:** {row['Status']}")
                    
                    with col2:
                        # Get member phone from members master
                        members_df = get_cached_members_master()
                        if not members_df.empty:
                            member_info = members_df[members_df['Member_Name'] == row['Member_Name']]
                            if not member_info.empty:
                                phone = member_info.iloc[0].get('Phone', 'N/A')
                                st.write(f"**Phone:** {phone}")
                                if phone != 'N/A':
                                    st.markdown(f"📱 [Call {phone}](tel:{phone})")
                    
                    st.caption(f"Last Updated: {row['Last_Updated']}")
        else:
            st.success("✅ Great! No members at risk in your cell!")
    else:
        st.info("No attendance summary available yet. Mark attendance for at least 3 services to generate the summary.")
        
        # Show instruction
        with st.expander("ℹ️ How does this work?"):
            st.write("""
            **Attendance Summary tracks members who need pastoral care:**
            
            1. System tracks the last 3 church services
            2. Members who missed 2 or more services are flagged as "⚠️ DANGER"
            3. Cell leaders can see their at-risk members with contact information
            4. Summary updates automatically when attendance is marked
            5. Call or visit these members to ensure they're okay!
            
            **Benefits:**
            - Early identification of members drifting away
            - Easy access to contact information
            - Helps maintain strong fellowship
            """)

def offerings_page():
    """Offerings entry page"""
    st.title("💰 Offerings & Tithes")
    
    # Check role
    if st.session_state.role not in ['Accountant', 'Admin']:
        st.warning("You don't have permission to enter offerings.")
        return
    
    st.subheader("Enter Offering")
    
    col1, col2 = st.columns(2)
    
    with col1:
        offering_date = st.date_input("Date", value=date.today())
        amount = st.number_input("Amount (GHS)", min_value=0.0, step=10.0)
    
    with col2:
        meeting_type = st.selectbox("Meeting Type", [
            "Sunday Service",
            "Weekday Meeting",
            "Special Offering",
            "Tithe",
            "Thanksgiving",
            "Other"
        ])
        description = st.text_input("Description (Optional)")
    
    if st.button("💾 Save Offering", type="primary"):
        if amount > 0:
            with st.spinner("Saving offering..."):
                new_record = {
                    'Date': str(offering_date),
                    'Amount_GHS': amount,
                    'Meeting_Type': meeting_type,
                    'Description': description,
                    'Entered_By': st.session_state.username,
                    'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Append to sheet
                if append_sheet_data(OFFERINGS_TAB, new_record):
                    st.success(f"✅ Offering of GHS {amount:.2f} recorded!")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ Failed to save offering. Please try again.")
        else:
            st.warning("Please enter an amount greater than 0")
    
    # Display recent offerings
    st.divider()
    st.subheader("Recent Offerings")
    
    offerings_df = get_sheet_data(OFFERINGS_TAB)
    if not offerings_df.empty:
        # Sort by timestamp if available
        if 'Timestamp' in offerings_df.columns:
            offerings_df = offerings_df.sort_values('Timestamp', ascending=False)
        recent = offerings_df.head(10)
        st.dataframe(recent[['Date', 'Amount_GHS', 'Meeting_Type', 'Description', 'Entered_By']], 
                     use_container_width=True, hide_index=True)
        
        # Total
        total = offerings_df['Amount_GHS'].sum()
        st.metric("Total Offerings", f"GHS {total:,.2f}")
    else:
        st.info("No offerings recorded yet")
def search_members_page():
    """Search and view members page"""
    st.title("🔍 Search Members")
    
    st.info("💡 Search for members and view their information")
    
    # Search options
    search_type = st.radio("Search By", ["Name", "Home Cell Group", "View All"], horizontal=True)
    
    members_df = get_cached_members_master()
    
    if members_df.empty:
        st.warning("No members found in Members Master sheet")
        return
    
    filtered_members = members_df
    
    if search_type == "Name":
        search_term = st.text_input("🔍 Enter member name", placeholder="Type name...")
        if search_term:
            filtered_members = members_df[members_df['Member_Name'].str.contains(search_term, case=False, na=False)]
    
    elif search_type == "Home Cell Group":
        home_cells = get_home_cell_groups()
        if home_cells:
            selected_cell = st.selectbox("Select Home Cell Group", home_cells)
            filtered_members = members_df[members_df['Home_Cell_Group'] == selected_cell]
    
    # Display results
    if not filtered_members.empty:
        st.success(f"Found {len(filtered_members)} member(s)")
        
        # Display as cards
        for idx, row in filtered_members.iterrows():
            with st.expander(f"👤 {row['Member_Name']} - {row.get('Home_Cell_Group', 'N/A')}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Phone:** {row.get('Phone', 'N/A')}")
                    st.write(f"**Email:** {row.get('Email', 'N/A')}")
                    st.write(f"**Gender:** {row.get('Gender', 'N/A')}")
                    st.write(f"**Date of Birth:** {row.get('Date of Birth', 'N/A')}")
                
                with col2:
                    st.write(f"**Marital Status:** {row.get('Marital Status', 'N/A')}")
                    st.write(f"**Member Type:** {row.get('Member Type', 'N/A')}")
                    st.write(f"**City:** {row.get('City', 'N/A')}")
                    st.write(f"**Home Cell:** {row.get('Home_Cell_Group', 'N/A')}")
        
        # Download option
        st.divider()
        csv = filtered_members.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"members_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("No members found matching your search")


def announcements_page():
    """Announcements page"""
    st.title("📢 Announcements")
    
    # Display existing announcements first
    st.subheader("Recent Announcements")
    
    announcements_df = get_sheet_data(ANNOUNCEMENTS_TAB)
    
    if not announcements_df.empty:
        # Sort by timestamp
        if 'Timestamp' in announcements_df.columns:
            announcements_df = announcements_df.sort_values('Timestamp', ascending=False)
        
        # Display announcements
        for idx, row in announcements_df.head(10).iterrows():
            with st.container():
                st.markdown(f"### 📌 {row['Title']}")
                st.write(row['Message'])
                st.caption(f"Posted by {row['Posted_By']} on {row['Date']}")
                st.divider()
    else:
        st.info("No announcements yet")
    
    # Add new announcement (Admin only)
    if st.session_state.role == 'Admin':
        st.divider()
        st.subheader("➕ Post New Announcement")
        
        with st.form("new_announcement"):
            title = st.text_input("Announcement Title")
            message = st.text_area("Message", height=150)
            announcement_date = st.date_input("Date", value=date.today())
            
            submitted = st.form_submit_button("📤 Post Announcement", type="primary")
            
            if submitted:
                if title and message:
                    with st.spinner("Posting announcement..."):
                        new_record = {
                            'Date': str(announcement_date),
                            'Title': title,
                            'Message': message,
                            'Posted_By': st.session_state.username,
                            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        if append_sheet_data(ANNOUNCEMENTS_TAB, new_record):
                            st.success("✅ Announcement posted!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to post announcement")
                else:
                    st.warning("Please fill in all fields")


def admin_page():
    """Admin page for user management"""
    st.title("⚙️ Admin Settings")
    
    if st.session_state.role != 'Admin':
        st.warning("You don't have admin permissions")
        return
    
    tab1, tab2, tab3 = st.tabs(["👥 User Management", "📊 Reports", "🔧 System"])
    
    # Tab 1: User Management
    with tab1:
        st.subheader("User Management")
        
        # Display existing users
        users_df = get_sheet_data(USERS_TAB)
        
        if not users_df.empty:
            st.write("**Existing Users:**")
            st.dataframe(
                users_df[['Username', 'Role', 'Home_Cell_Group']], 
                use_container_width=True, 
                hide_index=True
            )
        
        st.divider()
        
        # Add new user
        st.subheader("➕ Add New User")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
        
        with col2:
            new_role = st.selectbox("Role", [
                "Admin",
                "Home Cell Leader",
                "Accountant",
                "Member"
            ])
            
            home_cells = get_home_cell_groups()
            new_home_cell = st.selectbox("Home Cell Group", ["N/A"] + home_cells)
        
        if st.button("➕ Create User", type="primary"):
            if new_username and new_password:
                # Check if username already exists
                if not users_df.empty and new_username in users_df['Username'].values:
                    st.error("❌ Username already exists!")
                else:
                    new_user = {
                        'Username': new_username,
                        'Password': new_password,
                        'Role': new_role,
                        'Home_Cell_Group': new_home_cell
                    }
                    
                    if append_sheet_data(USERS_TAB, new_user):
                        st.success(f"✅ User '{new_username}' created!")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Failed to create user")
            else:
                st.warning("Please fill in username and password")
    
    # Tab 2: Reports
    with tab2:
        st.subheader("📊 System Reports")
        
        col1, col2, col3 = st.columns(3)
        
        # Get data
        members_df = get_cached_members_master()
        attendance_df = get_sheet_data(ATTENDANCE_TAB)
        offerings_df = get_sheet_data(OFFERINGS_TAB)
        welfare_df = get_sheet_data(WELFARE_TAB)
        
        with col1:
            st.metric("Total Members", len(members_df) if not members_df.empty else 0)
            st.metric("Home Cell Groups", len(get_home_cell_groups()))
        
        with col2:
            if not offerings_df.empty:
                total_offerings = offerings_df['Amount_GHS'].sum()
                st.metric("Total Offerings", f"GHS {total_offerings:,.2f}")
            else:
                st.metric("Total Offerings", "GHS 0.00")
            
            if not welfare_df.empty:
                total_welfare = welfare_df['Amount_GHS'].sum()
                st.metric("Total Welfare", f"GHS {total_welfare:,.2f}")
            else:
                st.metric("Total Welfare", "GHS 0.00")
        
        with col3:
            if not attendance_df.empty:
                total_records = len(attendance_df)
                st.metric("Attendance Records", total_records)
            else:
                st.metric("Attendance Records", 0)
            
            users_df = get_sheet_data(USERS_TAB)
            st.metric("System Users", len(users_df) if not users_df.empty else 0)
        
        st.divider()
        
        # Date range filter for reports
        st.subheader("Generate Reports")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From Date", value=date.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("To Date", value=date.today())
        
        # Attendance Report
        if st.button("📊 Generate Attendance Report"):
            if not attendance_df.empty:
                filtered = attendance_df[
                    (attendance_df['Date'] >= str(start_date)) & 
                    (attendance_df['Date'] <= str(end_date))
                ]
                
                if not filtered.empty:
                    st.write(f"**Attendance Records: {len(filtered)}**")
                    st.dataframe(filtered, use_container_width=True, hide_index=True)
                    
                    # Download
                    csv = filtered.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Attendance Report",
                        csv,
                        f"attendance_report_{start_date}_to_{end_date}.csv",
                        "text/csv"
                    )
                else:
                    st.info("No attendance records in selected date range")
        
        # Financial Report
        if st.button("💰 Generate Financial Report"):
            financial_data = []
            
            if not offerings_df.empty:
                offerings_filtered = offerings_df[
                    (offerings_df['Date'] >= str(start_date)) & 
                    (offerings_df['Date'] <= str(end_date))
                ]
                offerings_total = offerings_filtered['Amount_GHS'].sum() if not offerings_filtered.empty else 0
            else:
                offerings_total = 0
            
            if not welfare_df.empty:
                welfare_filtered = welfare_df[
                    (welfare_df['Date'] >= str(start_date)) & 
                    (welfare_df['Date'] <= str(end_date))
                ]
                welfare_total = welfare_filtered['Amount_GHS'].sum() if not welfare_filtered.empty else 0
            else:
                welfare_total = 0
            
            st.metric("Total Offerings", f"GHS {offerings_total:,.2f}")
            st.metric("Total Welfare", f"GHS {welfare_total:,.2f}")
            st.metric("Grand Total", f"GHS {(offerings_total + welfare_total):,.2f}")
    
    # Tab 3: System
    with tab3:
        st.subheader("🔧 System Utilities")
        
        st.warning("⚠️ Use these tools carefully!")
        
        if st.button("🔄 Update Attendance Summary Now"):
            with st.spinner("Updating attendance summary..."):
                if update_attendance_summary():
                    st.success("✅ Attendance summary updated!")
                else:
                    st.error("❌ Failed to update summary")
        
        st.divider()
        
        if st.button("🗑️ Clear Cache"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("✅ Cache cleared!")
        
        st.divider()
        
        st.info("📱 **Google Sheets Connection Status**")
        client = get_google_sheets_client()
        if client:
            st.success("✅ Connected to Google Sheets")
        else:
            st.error("❌ Not connected to Google Sheets")


def main():
    """Main application function"""
    
    # Page config
    st.set_page_config(
        page_title="Church Attendance System",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
        }
        .stMetric {
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 5px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Check login status
    if not st.session_state.logged_in:
        login_page()
    else:
        # Sidebar navigation
        with st.sidebar:
            st.title("🏛️ Church System")
            st.write(f"👤 **User:** {st.session_state.username}")
            st.write(f"🎭 **Role:** {st.session_state.role}")
            if st.session_state.home_cell:
                st.write(f"📍 **Cell:** {st.session_state.home_cell}")
            
            st.divider()
            
            # Navigation menu
            menu_options = {
                "📢 Announcements": "announcements",
                "🔍 Search Members": "search"
            }
            
            # Role-based menu options
            if st.session_state.role in ['Home Cell Leader', 'Admin']:
                menu_options["📋 Mark Attendance"] = "attendance"
                menu_options["⚠️ Attendance Summary"] = "summary"
            
            if st.session_state.role in ['Accountant', 'Admin']:
                menu_options["💰 Offerings"] = "offerings"
            
            # Welfare accessible to all
            menu_options["💝 Welfare"] = "welfare"
            
            if st.session_state.role == 'Admin':
                menu_options["⚙️ Admin Settings"] = "admin"
            
            # Menu selection
            selected_page = st.radio("Navigation", list(menu_options.keys()))
            page = menu_options[selected_page]
            
            st.divider()
            
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.username = None
                st.session_state.role = None
                st.session_state.home_cell = None
                st.rerun()
        
        # Main content area
        if page == "attendance":
            attendance_page()
        elif page == "offerings":
            offerings_page()
        elif page == "welfare":
            welfare_page()
        elif page == "search":
            search_members_page()
        elif page == "announcements":
            announcements_page()
        elif page == "summary":
            attendance_summary_page()
        elif page == "admin":
            admin_page()


# Run the app
if __name__ == "__main__":
    main()
