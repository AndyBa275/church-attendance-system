import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
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
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            credentials_dict = dict(st.secrets['gcp_service_account'])
        else:
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
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) <= 1:
            if tab_name == MEMBERS_TAB:
                return pd.DataFrame(columns=['Member_Name', 'Home_Cell_Group', 'Phone', 'Email', 'Gender'])
            elif tab_name == ATTENDANCE_TAB:
                return pd.DataFrame(columns=['Date', 'Home_Cell_Group', 'Member_Name', 'Present', 'Recorded_By', 'Timestamp'])
            elif tab_name == OFFERINGS_TAB:
                return pd.DataFrame(columns=['Date', 'Amount_GHS', 'Meeting_Type', 'Description', 'Entered_By', 'Timestamp'])
            elif tab_name == USERS_TAB:
                return pd.DataFrame(columns=['Username', 'Password', 'Role', 'Home_Cell_Group'])
            elif tab_name == ANNOUNCEMENTS_TAB:
                return pd.DataFrame(columns=['Date', 'Title', 'Message', 'Posted_By', 'Timestamp'])
            elif tab_name == WELFARE_TAB:
                return pd.DataFrame(columns=['Date', 'Member_Name', 'Home_Cell_Group', 'Amount_GHS', 'Collected_By', 'Timestamp'])
            elif tab_name == ATTENDANCE_SUMMARY_TAB:
                return pd.DataFrame(columns=['Member_Name', 'Home_Cell_Group', 'Last_3_Attendances', 'Missed_Count', 'Status', 'Last_Updated'])
            return pd.DataFrame()
        
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=all_values[0])
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def write_sheet_data(tab_name, df):
    """Write data to Google Sheet tab"""
    try:
        client = get_google_sheets_client()
        if client is None:
            return False
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.clear()
        
        if not df.empty:
            data = [df.columns.tolist()] + df.values.tolist()
            worksheet.update('A1', data)
        else:
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

@st.cache_data(ttl=300)
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
    """Get members for a specific home cell"""
    members_df = get_cached_members_master()
    if not members_df.empty and 'Home_Cell_Group' in members_df.columns:
        cell_members = members_df[members_df['Home_Cell_Group'] == home_cell]
        if 'Member_Name' in cell_members.columns:
            return cell_members[['Member_Name', 'Phone', 'Home_Cell_Group']].dropna(subset=['Member_Name'])
    return pd.DataFrame()

def update_attendance_summary():
    """Update attendance summary with members at risk"""
    try:
        attendance_df = get_sheet_data(ATTENDANCE_TAB)
        members_df = get_cached_members_master()
        
        if attendance_df.empty or members_df.empty:
            return False
        
        if 'Date' in attendance_df.columns:
            unique_dates = sorted(attendance_df['Date'].unique(), reverse=True)[:3]
            
            if len(unique_dates) < 3:
                return False
            
            summary_records = []
            
            for _, member in members_df.iterrows():
                member_name = member['Member_Name']
                home_cell = member['Home_Cell_Group']
                
                member_attendance = attendance_df[
                    (attendance_df['Member_Name'] == member_name) & 
                    (attendance_df['Date'].isin(unique_dates))
                ]
                
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
                        attendance_status.append('No')
                        missed_count += 1
                
                if missed_count >= 2:
                    summary_records.append({
                        'Member_Name': member_name,
                        'Home_Cell_Group': home_cell,
                        'Last_3_Attendances': ' | '.join(attendance_status),
                        'Missed_Count': missed_count,
                        'Status': "⚠️ DANGER - Contact Member",
                        'Last_Updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            if summary_records:
                summary_df = pd.DataFrame(summary_records)
                return write_sheet_data(ATTENDANCE_SUMMARY_TAB, summary_df)
            else:
                empty_df = pd.DataFrame(columns=['Member_Name', 'Home_Cell_Group', 'Last_3_Attendances', 
                                                'Missed_Count', 'Status', 'Last_Updated'])
                return write_sheet_data(ATTENDANCE_SUMMARY_TAB, empty_df)
        return False
    except:
        return False

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
            else:
                st.warning("Please enter both username and password")
        
        st.divider()
        st.info("📱 This system works on mobile phones! Access via browser.")

def attendance_page():
    """Attendance marking page"""
    st.title("📋 Mark Attendance")
    
    if st.session_state.role not in ['Home Cell Leader', 'Admin']:
        st.warning("You don't have permission to mark attendance.")
        return
    
    attendance_date = st.date_input("Select Date", value=date.today())
    
    if st.session_state.role == 'Admin':
        home_cells = get_home_cell_groups()
        if not home_cells:
            st.warning("No home cell groups found.")
            return
        selected_cell = st.selectbox("Select Home Cell Group", home_cells)
    else:
        selected_cell = st.session_state.home_cell
        st.info(f"Your Home Cell: **{selected_cell}**")
    
    if selected_cell:
        col_title, col_refresh = st.columns([3, 1])
        with col_refresh:
            if st.button("🔄 Refresh"):
                st.cache_data.clear()
                st.rerun()
        
        members = get_members_by_cell(selected_cell)
        
        if not members.empty:
            st.subheader(f"Members in {selected_cell}")
            st.write(f"Total Members: {len(members)}")
            
            attendance_df = get_sheet_data(ATTENDANCE_TAB)
            existing_attendance = pd.DataFrame()
            if not attendance_df.empty:
                existing_attendance = attendance_df[
                    (attendance_df['Date'] == str(attendance_date)) & 
                    (attendance_df['Home_Cell_Group'] == selected_cell)
                ]
            
            attendance_dict = {}
            
            for idx, row in members.iterrows():
                member_name = row['Member_Name']
                default_value = False
                if not existing_attendance.empty:
                    member_record = existing_attendance[existing_attendance['Member_Name'] == member_name]
                    if not member_record.empty:
                        default_value = member_record.iloc[0]['Present'] == 'Yes'
                
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
                    with st.spinner("Saving..."):
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
                        
                        attendance_df = get_sheet_data(ATTENDANCE_TAB)
                        if not attendance_df.empty:
                            attendance_df = attendance_df[
                                ~((attendance_df['Date'] == str(attendance_date)) & 
                                  (attendance_df['Home_Cell_Group'] == selected_cell))
                            ]
                        
                        new_df = pd.DataFrame(new_records)
                        attendance_df = pd.concat([attendance_df, new_df], ignore_index=True)
                        
                        if write_sheet_data(ATTENDANCE_TAB, attendance_df):
                            update_attendance_summary()
                            present_count = sum(attendance_dict.values())
                            st.success(f"✅ Saved! {present_count}/{len(members)} present")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to save")
        else:
            st.warning(f"No members found in {selected_cell}")

def welfare_page():
    """Welfare contribution collection"""
    st.title("💝 Welfare Contributions")
    st.info("💡 Search members and record their welfare contributions")
    
    search_term = st.text_input("🔍 Search Member Name", placeholder="Type name...")
    members_df = get_cached_members_master()
    
    if search_term and not members_df.empty:
        results = members_df[members_df['Member_Name'].str.contains(search_term, case=False, na=False)]
        
        if not results.empty:
            st.success(f"Found {len(results)} member(s)")
            
            selected_members = st.multiselect(
                "Select Members (can select multiple)",
                options=results['Member_Name'].tolist(),
                format_func=lambda x: f"{x} - {results[results['Member_Name']==x]['Home_Cell_Group'].iloc[0]}"
            )
            
            if selected_members:
                st.divider()
                st.subheader("Enter Welfare Contributions")
                
                contributions = {}
                col1, col2 = st.columns(2)
                
                with col1:
                    contribution_date = st.date_input("Date", value=date.today())
                with col2:
                    amount_type = st.radio("Amount Entry", ["Same for all", "Individual amounts"])
                
                if amount_type == "Same for all":
                    common_amount = st.number_input("Amount (GHS) for all", min_value=0.0, step=5.0)
                    for member in selected_members:
                        contributions[member] = common_amount
                else:
                    for member in selected_members:
                        member_cell = results[results['Member_Name']==member]['Home_Cell_Group'].iloc[0]
                        contributions[member] = st.number_input(
                            f"Amount for {member} ({member_cell})", 
                            min_value=0.0, 
                            step=5.0,
                            key=f"welfare_{member}"
                        )
                
                st.divider()
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("💾 Submit", use_container_width=True, type="primary"):
                        if all(amount == 0 for amount in contributions.values()):
                            st.warning("Enter at least one amount")
                        else:
                            with st.spinner("Saving..."):
                                new_records = []
                                total_amount = 0
                                
                                for member_name, amount in contributions.items():
                                    if amount > 0:
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
                                    new_df = pd.DataFrame(new_records)
                                    if append_sheet_data(WELFARE_TAB, new_df):
                                        st.success(f"✅ {len(new_records)} recorded! Total: GHS {total_amount:.2f}")
                                        time.sleep(2)
                                        st.rerun()
        else:
            st.warning("No members found")
    
    st.divider()
    st.subheader("Recent Welfare Contributions")
    
    welfare_df = get_sheet_data(WELFARE_TAB)
    if not welfare_df.empty:
        if 'Timestamp' in welfare_df.columns:
            welfare_df = welfare_df.sort_values('Timestamp', ascending=False)
        
        recent = welfare_df.head(20)
        st.dataframe(
            recent[['Date', 'Member_Name', 'Home_Cell_Group', 'Amount_GHS', 'Collected_By']], 
            use_container_width=True, 
            hide_index=True
        )
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Collected", f"GHS {welfare_df['Amount_GHS'].sum():,.2f}")
        with col2:
            st.metric("Contributors", welfare_df['Member_Name'].nunique())
        with col3:
            today_welfare = welfare_df[welfare_df['Date'] == str(date.today())]
            today_total = today_welfare['Amount_GHS'].sum() if not today_welfare.empty else 0
            st.metric("Today", f"GHS {today_total:.2f}")
    else:
        st.info("No contributions recorded yet")

def attendance_summary_page():
    """Attendance summary - members at risk"""
    st.title("⚠️ Members at Risk")
    
    if st.session_state.role not in ['Home Cell Leader', 'Admin']:
        st.warning("Only Cell Leaders and Admins can view this.")
        return
    
    st.info("📞 Members who missed 2+ out of last 3 services")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh"):
            with st.spinner("Updating..."):
                if update_attendance_summary():
                    st.success("Updated!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Need at least 3 services")
    
    summary_df = get_sheet_data(ATTENDANCE_SUMMARY_TAB)
    
    if not summary_df.empty:
        if st.session_state.role == 'Home Cell Leader':
            summary_df = summary_df[summary_df['Home_Cell_Group'] == st.session_state.home_cell]
            st.subheader(f"Your Cell: {st.session_state.home_cell}")
        
        if not summary_df.empty:
            st.metric("Members Needing Contact", len(summary_df))
            st.divider()
            
            for idx, row in summary_df.iterrows():
                with st.expander(f"⚠️ {row['Member_Name']} - {row['Home_Cell_Group']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Last 3:** {row['Last_3_Attendances']}")
                        st.write(f"**Missed:** {row['Missed_Count']} of 3")
                        st.write(f"**Status:** {row['Status']}")
                    
                    with col2:
                        members_df = get_cached_members_master()
                        if not members_df.empty:
                            member_info = members_df[members_df['Member_Name'] == row['Member_Name']]
                            if not member_info.empty:
                                phone = member_info.iloc[0].get('Phone', 'N/A')
                                st.write(f"**Phone:** {phone}")
                                if phone != 'N/A':
                                    st.markdown(f"📱 [Call](tel:{phone})")
                    
                    st.caption(f"Updated: {row['Last_Updated']}")
        else:
            st.success("✅ No members at risk in your cell!")
    else:
        st.info("No summary yet. Need at least 3 services.")

def offerings_page():
    """Offerings entry"""
    st.title("💰 Offerings & Tithes")
    
    if st.session_state.role not in ['Accountant', 'Admin']:
        st.warning("You don't have permission.")
        return
    
    st.subheader("Enter Offering")
    
    col1, col2 = st.columns(2)
    with col1:
        offering_date = st.date_input("Date", value=date.today())
        amount = st.number_input("Amount (GHS)", min_value=0.0, step=10.0)
    with col2:
        meeting_type = st.selectbox("Type", [
            "Sunday Service", "Weekday Meeting", "Special Offering", 
            "Tithe", "Thanksgiving", "Other"
        ])
        description = st.text_input("Description (Optional)")
    
    if st.button("💾 Save", type="primary"):
        if amount > 0:
            with st.spinner("Saving..."):
                new_record = {
                    'Date': str(offering_date),
                    'Amount_GHS': amount,
                    'Meeting_Type': meeting_type,
                    'Description': description,
                    'Entered_By': st.session_state.username,
                    'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                if append_sheet_data(OFFERINGS_TAB, new_record):
                    st.success(f"✅ GHS {amount:.2f} recorded!")
                    time.sleep(2)
                    st.rerun()
        else:
            st.warning("Enter amount > 0")
    
    st.divider()
    st.subheader("Recent Offerings")
    
    offerings_df = get_sheet_data(OFFERINGS_TAB)
    if not offerings_df.empty:
        if 'Timestamp' in offerings_df.columns:
            offerings_df = offerings_df.sort_values('Timestamp', ascending=False)
        recent = offerings_df.head(10)
        st.dataframe(recent[['Date', 'Amount_GHS', 'Meeting_Type', 'Description', 'Entered_By']], 
                     use_container_width=True, hide_index=True)
        st.metric("Total", f"GHS {offerings_df['Amount_GHS'].sum():,.2f}")
    else:
        st.info("No offerings yet")

def search_members_page():
    """Search members"""
    st.title("🔍 Search Members")
    
    search_term = st.text_input("Search by Name", placeholder="Enter name...")
    
    if search_term:
        members_df = get_cached_members_master()
        
        if not members_df.empty:
            results = members_df[members_df['Member_Name'].str.contains(search_term, case=False, na=False)]
            
            if not results.empty:
                st.success(f"Found {len(results)} member(s)")
                
                for idx, row in results.iterrows():
                    with st.expander(f"👤 {row['Member_Name']}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Home Cell:** {row.get('Home_Cell_Group', 'N/A')}")
                            st.write(f"**Phone:** {row.get('Phone', 'N/A')}")
                            st.write(f"**Gender:** {row.get('Gender', 'N/A')}")
                        
                        with col2:
                            st.write(f"**Email:** {row.get('Email', 'N/A')}")
                            st.write(f"**Member Type:** {row.get('Member Type', 'N/A')}")
            else:
                st.warning("No members found")
    else:
        members_df = get_cached_members_master()
        if not members_df.empty:
            st.info(f"Total Members: {len(members_df)}")
            
            if 'Home_Cell_Group' in members_df.columns:
                cell_counts = members_df['Home_Cell_Group'].value_counts()
                st.subheader("Members by Cell")
                st.bar_chart(cell_counts)

def announcements_page():
    """Announcements"""
    st.title("📢 Announcements")
    
    if st.session_state.role == 'Admin':
        with st.expander("➕ Post New"):
            title = st.text_input("Title")
            message = st.text_area("Message")
            
            if st.button("Post"):
                if title and message:
                    with st.spinner("Posting..."):
                        new_announcement = {
                            'Date': str(date.today()),
                            'Title': title,
                            'Message': message,
                            'Posted_By': st.session_state.username,
                            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        if append_sheet_data(ANNOUNCEMENTS_TAB, new_announcement):
                            st.success("✅ Posted!")
                            time.sleep(2)
                            st.rerun()
    
    st.subheader("Recent Announcements")
    announcements_df = get_sheet_data(ANNOUNCEMENTS_TAB)
    
    if not announcements_df.empty:
        if 'Timestamp' in announcements_df.columns:
            announcements_df = announcements_df.sort_values('Timestamp', ascending=False)
        
        for idx, row in announcements_df.head(10).iterrows():
            st.markdown(f"### 📌 {row['Title']}")
            st.write(row['Message'])
            st.caption(f"Posted on {row['Date']} by {row['Posted_By']}")
            st.divider()
    else:
        st.info("No announcements yet")

def admin_page():
    """Admin panel"""
    st.title("⚙️ Admin Panel")
    
    if st.session_state.role != 'Admin':
        st.warning("Admin only")
        return
    
    tab1, tab2, tab3 = st.tabs(["Users", "Reports", "System"])
    
    with tab1:
        st.subheader("➕ Add User")
        
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
        with col2:
            new_role = st.selectbox("Role", ["Home Cell Leader", "Accountant", "Admin"])
            if new_role == "Home Cell Leader":
                home_cells = get_home_cell_groups()
                new_home_cell = st.selectbox("Cell", home_cells) if home_cells else "N/A"
            else:
                new_home_cell = "N/A"
        
        if st.button("Add", type="primary"):
            if new_username and new_password:
                users_df = get_sheet_data(USERS_TAB)
                if not users_df.empty and new_username in users_df['Username'].values:
                    st.error("Username exists!")
                else:
                    new_user = {
                        'Username': new_username,
                        'Password': new_password,
                        'Role': new_role,
                        'Home_Cell_Group': new_home_cell
                    }
                    if append_sheet_data(USERS_TAB, new_user):
                        st.success(f"✅ Added {new_username}!")
                        time.sleep(1)
                        st.rerun()
        
        st.divider()
        st.subheader("Existing Users")
        users_df = get_sheet_data(USERS_TAB)
        if not users_df.empty:
            display_df = users_df[['Username', 'Role', 'Home_Cell_Group']]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("Attendance Reports")
        attendance_df = get_sheet_data(ATTENDANCE_TAB)
        if not attendance_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", len(attendance_df))
            with col2:
                present_count = len(attendance_df[attendance_df['Present'] == 'Yes'])
                st.metric("Present", present_count)
            with col3:
                rate = (present_count / len(attendance_df)) * 100
                st.metric("Rate", f"{rate:.1f}%")
        else:
            st.info("No data yet")
    
    with tab3:
        st.subheader("System Info")
        members_df = get_cached_members_master()
        if not members_df.empty:
            st.metric("Total Members", len(members_df))
        
        home_cells = get_home_cell_groups()
        st.metric("Home Cells", len(home_cells))
        
        st.write("**Cells:**")
        for cell in home_cells:
            st.write(f"- {cell}")
        
        st.divider()
        if st.button("🔄 Clear Cache"):
            st.cache_data.clear()
            st.success("Cleared!")
            time.sleep(1)
            st.rerun()

def main():
    st.set_page_config(
        page_title="Church System",
        page_icon="🏛️",
        layout="wide"
    )
    
    if not st.session_state.logged_in:
        login_page()
    else:
        with st.sidebar:
            st.title("🏛️ Church System")
            st.write(f"👤 **{st.session_state.username}**")
            st.write(f"Role: {st.session_state.role}")
            
            if st.session_state.home_cell and st.session_state.home_cell != "N/A":
                st.write(f"Cell: {st.session_state.home_cell}")
            
            st.divider()
            
            page = st.radio("Navigation", [
                "📋 Attendance",
                "💝 Welfare",
                "⚠️ At Risk Members",
                "💰 Offerings",
                "🔍 Search Members",
                "📢 Announcements",
                "⚙️ Admin Panel"
            ])
            
            st.divider()
            
            if st.button("🚪 Logout"):
                st.session_state.logged_in = False
                st.session_state.username = None
                st.session_state.role = None
                st.session_state.home_cell = None
                st.rerun()
        
        if page == "📋 Attendance":
            attendance_page()
        elif page == "💝 Welfare":
            welfare_page()
        elif page == "⚠️ At Risk Members":
            attendance_summary_page()
        elif page == "💰 Offerings":
            offerings_page()
        elif page == "🔍 Search Members":
            search_members_page()
        elif page == "📢 Announcements":
            announcements_page()
        elif page == "⚙️ Admin Panel":
            admin_page()

if __name__ == "__main__":
    main()