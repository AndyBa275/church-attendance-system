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
        data = worksheet.get_all_records()
        
        if not data:
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
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error reading from {tab_name}: {str(e)}")
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

def get_home_cell_groups():
    """Get unique home cell groups from members"""
    members_df = get_sheet_data(MEMBERS_TAB)
    if not members_df.empty and 'Home_Cell_Group' in members_df.columns:
        return sorted(members_df['Home_Cell_Group'].dropna().unique().tolist())
    return []

def get_members_by_cell(home_cell):
    """Get members for a specific home cell"""
    members_df = get_sheet_data(MEMBERS_TAB)
    if not members_df.empty and 'Home_Cell_Group' in members_df.columns:
        cell_members = members_df[members_df['Home_Cell_Group'] == home_cell]
        if 'Member_Name' in cell_members.columns:
            return cell_members[['Member_Name', 'Phone', 'Home_Cell_Group']].dropna(subset=['Member_Name'])
    return pd.DataFrame()

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
                            present_count = sum(attendance_dict.values())
                            st.success(f"✅ Attendance saved! {present_count}/{len(members)} members present")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to save attendance. Please try again.")
        else:
            st.warning(f"No members found in {selected_cell}")

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
    """Search members page"""
    st.title("🔍 Search Members")
    
    search_term = st.text_input("Search by Name", placeholder="Enter member name...")
    
    if search_term:
        members_df = get_sheet_data(MEMBERS_TAB)
        
        if not members_df.empty:
            # Search in Member_Name column
            results = members_df[members_df['Member_Name'].str.contains(search_term, case=False, na=False)]
            
            if not results.empty:
                st.success(f"Found {len(results)} member(s)")
                
                # Display results
                for idx, row in results.iterrows():
                    with st.expander(f"👤 {row['Member_Name']}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Home Cell:** {row.get('Home_Cell_Group', 'N/A')}")
                            st.write(f"**Phone:** {row.get('Phone', 'N/A')}")
                            st.write(f"**Gender:** {row.get('Gender', 'N/A')}")
                            st.write(f"**Marital Status:** {row.get('Marital Status', 'N/A')}")
                        
                        with col2:
                            st.write(f"**Email:** {row.get('Email', 'N/A')}")
                            st.write(f"**Member Type:** {row.get('Member Type', 'N/A')}")
                            st.write(f"**City:** {row.get('City', 'N/A')}")
                            # Handle date of birth with trailing space
                            dob = row.get('Date of Birth ', row.get('Date of Birth', 'N/A'))
                            st.write(f"**Date of Birth:** {dob}")
            else:
                st.warning("No members found with that name")
        else:
            st.error("Could not load members data")
    else:
        # Show summary
        members_df = get_sheet_data(MEMBERS_TAB)
        if not members_df.empty:
            st.info(f"Total Members: {len(members_df)}")
            
            # Group by home cell
            if 'Home_Cell_Group' in members_df.columns:
                cell_counts = members_df['Home_Cell_Group'].value_counts()
                st.subheader("Members by Home Cell")
                st.bar_chart(cell_counts)

def announcements_page():
    """Announcements page"""
    st.title("📢 Announcements")
    
    # Post announcement (Admin only)
    if st.session_state.role == 'Admin':
        with st.expander("➕ Post New Announcement"):
            title = st.text_input("Title")
            message = st.text_area("Message")
            
            if st.button("Post Announcement"):
                if title and message:
                    with st.spinner("Posting announcement..."):
                        new_announcement = {
                            'Date': str(date.today()),
                            'Title': title,
                            'Message': message,
                            'Posted_By': st.session_state.username,
                            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        if append_sheet_data(ANNOUNCEMENTS_TAB, new_announcement):
                            st.success("✅ Announcement posted!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to post announcement. Please try again.")
                else:
                    st.warning("Please fill in both title and message")
    
    # Display announcements
    st.subheader("Recent Announcements")
    announcements_df = get_sheet_data(ANNOUNCEMENTS_TAB)
    
    if not announcements_df.empty:
        if 'Timestamp' in announcements_df.columns:
            announcements_df = announcements_df.sort_values('Timestamp', ascending=False)
        
        for idx, row in announcements_df.head(10).iterrows():
            with st.container():
                st.markdown(f"### 📌 {row['Title']}")
                st.write(row['Message'])
                st.caption(f"Posted on {row['Date']} by {row['Posted_By']}")
                st.divider()
    else:
        st.info("No announcements yet")

def admin_page():
    """Admin management page"""
    st.title("⚙️ Admin Panel")
    
    if st.session_state.role != 'Admin':
        st.warning("Admin access only")
        return
    
    tab1, tab2, tab3 = st.tabs(["Users Management", "Reports", "System Info"])
    
    with tab1:
        st.subheader("➕ Add New User")
        
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
        
        with col2:
            new_role = st.selectbox("Role", ["Home Cell Leader", "Accountant", "Admin"])
            
            if new_role == "Home Cell Leader":
                home_cells = get_home_cell_groups()
                if home_cells:
                    new_home_cell = st.selectbox("Home Cell Group", home_cells)
                else:
                    st.warning("No home cell groups found")
                    new_home_cell = "N/A"
            else:
                new_home_cell = "N/A"
        
        if st.button("Add User", type="primary"):
            if new_username and new_password:
                users_df = get_sheet_data(USERS_TAB)
                
                # Check if username exists
                if not users_df.empty and new_username in users_df['Username'].values:
                    st.error("❌ Username already exists!")
                # Check if home cell leader already exists for this cell
                elif new_role == "Home Cell Leader":
                    existing_leader = users_df[
                        (users_df['Role'] == 'Home Cell Leader') & 
                        (users_df['Home_Cell_Group'] == new_home_cell)
                    ]
                    if not existing_leader.empty:
                        st.error(f"❌ A Home Cell Leader already exists for {new_home_cell}: {existing_leader.iloc[0]['Username']}")
                        st.info("💡 You can edit the existing user below or choose a different home cell.")
                    else:
                        new_user = {
                            'Username': new_username,
                            'Password': new_password,
                            'Role': new_role,
                            'Home_Cell_Group': new_home_cell
                        }
                        
                        if append_sheet_data(USERS_TAB, new_user):
                            st.success(f"✅ User {new_username} added!")
                            time.sleep(1)
                            st.rerun()
                else:
                    new_user = {
                        'Username': new_username,
                        'Password': new_password,
                        'Role': new_role,
                        'Home_Cell_Group': new_home_cell
                    }
                    
                    if append_sheet_data(USERS_TAB, new_user):
                        st.success(f"✅ User {new_username} added!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("Please fill in all fields")
        
        st.divider()
        st.subheader("👥 Manage Existing Users")
        users_df = get_sheet_data(USERS_TAB)
        if not users_df.empty:
            
            # Select user to edit
            edit_username = st.selectbox(
                "Select User to Edit/Delete", 
                users_df['Username'].tolist(),
                key="edit_user_select"
            )
            
            if edit_username:
                user_data = users_df[users_df['Username'] == edit_username].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.info(f"**Editing:** {edit_username}")
                    new_pass = st.text_input("New Password (leave blank to keep current)", type="password", key="edit_pass")
                    
                    edit_role = st.selectbox(
                        "Role", 
                        ["Home Cell Leader", "Accountant", "Admin"],
                        index=["Home Cell Leader", "Accountant", "Admin"].index(user_data['Role']) if user_data['Role'] in ["Home Cell Leader", "Accountant", "Admin"] else 0,
                        key="edit_role"
                    )
                
                with col2:
                    st.write("")  # Spacing
                    st.write("")
                    if edit_role == "Home Cell Leader":
                        home_cells = get_home_cell_groups()
                        if home_cells and user_data['Home_Cell_Group'] in home_cells:
                            current_cell_idx = home_cells.index(user_data['Home_Cell_Group'])
                        else:
                            current_cell_idx = 0
                        edit_home_cell = st.selectbox(
                            "Home Cell Group", 
                            home_cells if home_cells else ["N/A"],
                            index=current_cell_idx,
                            key="edit_home_cell"
                        )
                    else:
                        edit_home_cell = "N/A"
                
                col_update, col_delete = st.columns(2)
                
                with col_update:
                    if st.button("💾 Update User", use_container_width=True, type="primary"):
                        # Check for duplicate home cell leader (if changing to different cell)
                        if edit_role == "Home Cell Leader" and edit_home_cell != user_data['Home_Cell_Group']:
                            existing_leader = users_df[
                                (users_df['Role'] == 'Home Cell Leader') & 
                                (users_df['Home_Cell_Group'] == edit_home_cell) &
                                (users_df['Username'] != edit_username)
                            ]
                            if not existing_leader.empty:
                                st.error(f"❌ A Home Cell Leader already exists for {edit_home_cell}")
                            else:
                                # Update user
                                users_df.loc[users_df['Username'] == edit_username, 'Role'] = edit_role
                                users_df.loc[users_df['Username'] == edit_username, 'Home_Cell_Group'] = edit_home_cell
                                if new_pass:
                                    users_df.loc[users_df['Username'] == edit_username, 'Password'] = new_pass
                                
                                if write_sheet_data(USERS_TAB, users_df):
                                    st.success(f"✅ User {edit_username} updated!")
                                    time.sleep(1)
                                    st.rerun()
                        else:
                            # Update user
                            users_df.loc[users_df['Username'] == edit_username, 'Role'] = edit_role
                            users_df.loc[users_df['Username'] == edit_username, 'Home_Cell_Group'] = edit_home_cell
                            if new_pass:
                                users_df.loc[users_df['Username'] == edit_username, 'Password'] = new_pass
                            
                            if write_sheet_data(USERS_TAB, users_df):
                                st.success(f"✅ User {edit_username} updated!")
                                time.sleep(1)
                                st.rerun()
                
                with col_delete:
                    if st.button("🗑️ Delete User", use_container_width=True, type="secondary"):
                        if edit_username == "admin":
                            st.error("❌ Cannot delete admin account!")
                        else:
                            # Confirm deletion
                            if st.session_state.get('confirm_delete') != edit_username:
                                st.session_state.confirm_delete = edit_username
                                st.warning("⚠️ Click again to confirm deletion")
                            else:
                                users_df = users_df[users_df['Username'] != edit_username]
                                if write_sheet_data(USERS_TAB, users_df):
                                    st.session_state.confirm_delete = None
                                    st.success(f"✅ User {edit_username} deleted!")
                                    time.sleep(1)
                                    st.rerun()
            
            st.divider()
            st.subheader("All Users")
            # Don't show passwords
            display_df = users_df[['Username', 'Role', 'Home_Cell_Group']]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("Attendance Reports")
        
        # Overall statistics
        attendance_df = get_sheet_data(ATTENDANCE_TAB)
        if not attendance_df.empty:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_records = len(attendance_df)
                st.metric("Total Records", total_records)
            
            with col2:
                present_count = len(attendance_df[attendance_df['Present'] == 'Yes'])
                st.metric("Total Present", present_count)
            
            with col3:
                if total_records > 0:
                    attendance_rate = (present_count / total_records) * 100
                    st.metric("Attendance Rate", f"{attendance_rate:.1f}%")
            
            # Recent attendance by cell
            st.subheader("Recent Attendance by Home Cell")
            if 'Date' in attendance_df.columns:
                recent_dates = attendance_df['Date'].unique()[-4:]  # Last 4 dates
                
                for date_val in sorted(recent_dates, reverse=True):
                    with st.expander(f"📅 {date_val}"):
                        date_data = attendance_df[attendance_df['Date'] == date_val]
                        cell_summary = date_data.groupby('Home_Cell_Group')['Present'].apply(
                            lambda x: f"{(x == 'Yes').sum()}/{len(x)}"
                        )
                        st.dataframe(cell_summary, use_container_width=True)
        else:
            st.info("No attendance data yet")
    
    with tab3:
        st.subheader("System Information")
        
        members_df = get_sheet_data(MEMBERS_TAB)
        if not members_df.empty:
            st.metric("Total Members", len(members_df))
        
        home_cells = get_home_cell_groups()
        st.metric("Total Home Cell Groups", len(home_cells))
        
        st.write("**Home Cell Groups:**")
        for cell in home_cells:
            st.write(f"- {cell}")
        
        st.divider()
        st.info("💾 **Data Storage:** All data is stored in Google Sheets and persists permanently!")

# Main App
def main():
    st.set_page_config(
        page_title="Church Attendance System",
        page_icon="🏛️",
        layout="wide"
    )
    
    # Check if logged in
    if not st.session_state.logged_in:
        login_page()
    else:
        # Sidebar
        with st.sidebar:
            st.title("🏛️ Church System")
            st.write(f"👤 **{st.session_state.username}**")
            st.write(f"Role: {st.session_state.role}")
            
            if st.session_state.home_cell and st.session_state.home_cell != "N/A":
                st.write(f"Cell: {st.session_state.home_cell}")
            
            st.divider()
            
            # Navigation
            page = st.radio("Navigation", [
                "📋 Attendance",
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
        
        # Main content
        if page == "📋 Attendance":
            attendance_page()
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