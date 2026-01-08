import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import time
import json

# Google Sheets Configuration
SPREADSHEET_ID = "1xj89TMBgyBnEByNQD6jluLGBt07AuPwFCEq0u0H1bO8"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Sheet names
MEMBERS_SHEET = "Members Master"
ATTENDANCE_SHEET = "Church Attendance"
OFFERINGS_SHEET = "Church Offerings"
USERS_SHEET = "Church Users"
ANNOUNCEMENTS_SHEET = "Church Announcements"

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.home_cell = None

# Google Sheets Helper Functions
@st.cache_resource
def get_google_sheets_client():
    """Initialize Google Sheets client with credentials"""
    try:
        # Try to get credentials from Streamlit secrets (for deployment)
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    except:
        # Fall back to credentials.json file (for local development)
        try:
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        except FileNotFoundError:
            st.error("❌ credentials.json not found! Please ensure it's in the same folder as this script.")
            st.stop()
    
    client = gspread.authorize(creds)
    return client

def get_sheet(sheet_name):
    """Get a specific sheet from the spreadsheet"""
    try:
        client = get_google_sheets_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet
    except Exception as e:
        st.error(f"Error accessing sheet '{sheet_name}': {str(e)}")
        return None

def read_sheet_as_dataframe(sheet_name):
    """Read a Google Sheet and return as pandas DataFrame"""
    try:
        worksheet = get_sheet(sheet_name)
        if worksheet:
            data = worksheet.get_all_records()
            if data:
                return pd.DataFrame(data)
            else:
                # Return empty DataFrame with headers
                headers = worksheet.row_values(1)
                return pd.DataFrame(columns=headers)
        return None
    except Exception as e:
        st.error(f"Error reading sheet '{sheet_name}': {str(e)}")
        return None

def write_dataframe_to_sheet(df, sheet_name):
    """Write pandas DataFrame to Google Sheet"""
    try:
        worksheet = get_sheet(sheet_name)
        if worksheet:
            # Clear existing data
            worksheet.clear()
            
            # Write headers and data
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        return False
    except Exception as e:
        st.error(f"Error writing to sheet '{sheet_name}': {str(e)}")
        return False

def append_to_sheet(data_dict, sheet_name):
    """Append a single row to a Google Sheet"""
    try:
        worksheet = get_sheet(sheet_name)
        if worksheet:
            # Get headers
            headers = worksheet.row_values(1)
            
            # Create row in correct order
            row = [data_dict.get(header, '') for header in headers]
            
            # Append row
            worksheet.append_row(row)
            return True
        return False
    except Exception as e:
        st.error(f"Error appending to sheet '{sheet_name}': {str(e)}")
        return False

def initialize_sheets():
    """Initialize all required sheets if they don't exist"""
    try:
        client = get_google_sheets_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        
        # Get existing sheet names
        existing_sheets = [ws.title for ws in spreadsheet.worksheets()]
        
        # Define required sheets and their headers
        required_sheets = {
            ATTENDANCE_SHEET: ['Date', 'Home_Cell_Group', 'Member_Name', 'Present', 'Recorded_By', 'Timestamp'],
            OFFERINGS_SHEET: ['Date', 'Amount_GHS', 'Meeting_Type', 'Description', 'Entered_By', 'Timestamp'],
            USERS_SHEET: ['Username', 'Password', 'Role', 'Home_Cell_Group'],
            ANNOUNCEMENTS_SHEET: ['Date', 'Title', 'Message', 'Posted_By', 'Timestamp']
        }
        
        # Create missing sheets
        for sheet_name, headers in required_sheets.items():
            if sheet_name not in existing_sheets:
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
                worksheet.update([headers])
                
                # Initialize Users sheet with default data
                if sheet_name == USERS_SHEET:
                    default_users = [
                        ['admin', 'admin123', 'Admin', 'All'],
                        ['accountant', 'account123', 'Accountant', 'N/A']
                    ]
                    worksheet.append_rows(default_users)
        
        return True
    except Exception as e:
        st.error(f"Error initializing sheets: {str(e)}")
        return False

def verify_login(username, password):
    """Verify user credentials"""
    users_df = read_sheet_as_dataframe(USERS_SHEET)
    if users_df is not None and not users_df.empty:
        user = users_df[(users_df['Username'] == username) & (users_df['Password'] == password)]
        if not user.empty:
            return True, user.iloc[0]['Role'], user.iloc[0]['Home_Cell_Group']
    return False, None, None

def get_home_cell_groups():
    """Get unique home cell groups from members sheet"""
    members_df = read_sheet_as_dataframe(MEMBERS_SHEET)
    if members_df is not None and 'Home_Cell_Group' in members_df.columns:
        return sorted(members_df['Home_Cell_Group'].dropna().unique().tolist())
    return []

def get_members_by_cell(home_cell):
    """Get members for a specific home cell"""
    members_df = read_sheet_as_dataframe(MEMBERS_SHEET)
    if members_df is not None and 'Home_Cell_Group' in members_df.columns:
        cell_members = members_df[members_df['Home_Cell_Group'] == home_cell]
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
                    time.sleep(1)
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
            st.warning("No home cell groups found. Please check Members Master sheet.")
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
            attendance_df = read_sheet_as_dataframe(ATTENDANCE_SHEET)
            existing_attendance = None
            if attendance_df is not None and not attendance_df.empty:
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
                if existing_attendance is not None and not existing_attendance.empty:
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
                    with st.spinner("Saving attendance..."):
                        # Read existing attendance
                        attendance_df = read_sheet_as_dataframe(ATTENDANCE_SHEET)
                        
                        # Remove existing records for this date and cell
                        if attendance_df is not None and not attendance_df.empty:
                            attendance_df = attendance_df[
                                ~((attendance_df['Date'] == str(attendance_date)) & 
                                  (attendance_df['Home_Cell_Group'] == selected_cell))
                            ]
                        else:
                            attendance_df = pd.DataFrame(columns=['Date', 'Home_Cell_Group', 'Member_Name', 'Present', 'Recorded_By', 'Timestamp'])
                        
                        # Add new records
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
                        
                        new_df = pd.DataFrame(new_records)
                        attendance_df = pd.concat([attendance_df, new_df], ignore_index=True)
                        
                        # Save to Google Sheets
                        if write_dataframe_to_sheet(attendance_df, ATTENDANCE_SHEET):
                            present_count = sum(attendance_dict.values())
                            st.success(f"✅ Attendance saved! {present_count}/{len(members)} members present")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to save attendance. Please try again.")
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
                
                if append_to_sheet(new_record, OFFERINGS_SHEET):
                    st.success(f"✅ Offering of GHS {amount:.2f} recorded!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to save offering. Please try again.")
        else:
            st.warning("Please enter an amount greater than 0")
    
    # Display recent offerings
    st.divider()
    st.subheader("Recent Offerings")
    
    offerings_df = read_sheet_as_dataframe(OFFERINGS_SHEET)
    if offerings_df is not None and not offerings_df.empty:
        recent = offerings_df.sort_values('Timestamp', ascending=False).head(10)
        st.dataframe(recent[['Date', 'Amount_GHS', 'Meeting_Type', 'Description', 'Entered_By']], 
                     use_container_width=True)
        
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
        members_df = read_sheet_as_dataframe(MEMBERS_SHEET)
        
        if members_df is not None and not members_df.empty:
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
                            dob = row.get('Date of Birth ', row.get('Date of Birth', 'N/A'))
                            st.write(f"**Date of Birth:** {dob}")
            else:
                st.warning("No members found with that name")
        else:
            st.error("Could not load members data")
    else:
        # Show summary
        members_df = read_sheet_as_dataframe(MEMBERS_SHEET)
        if members_df is not None and not members_df.empty:
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
                        
                        if append_to_sheet(new_announcement, ANNOUNCEMENTS_SHEET):
                            st.success("✅ Announcement posted!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to post announcement. Please try again.")
                else:
                    st.warning("Please fill in both title and message")
    
    # Display announcements
    st.subheader("Recent Announcements")
    announcements_df = read_sheet_as_dataframe(ANNOUNCEMENTS_SHEET)
    
    if announcements_df is not None and not announcements_df.empty:
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
                    st.warning("No home cell groups found in Members Master sheet")
                    new_home_cell = None
            else:
                new_home_cell = "N/A"
        
        if st.button("Add User", type="primary"):
            if new_username and new_password and (new_role != "Home Cell Leader" or new_home_cell):
                users_df = read_sheet_as_dataframe(USERS_SHEET)
                
                # Check if username exists
                if new_username in users_df['Username'].values:
                    st.error("❌ Username already exists!")
                elif new_role == "Home Cell Leader":
                    existing_leader = users_df[
                        (users_df['Role'] == 'Home Cell Leader') & 
                        (users_df['Home_Cell_Group'] == new_home_cell)
                    ]
                    if not existing_leader.empty:
                        st.error(f"❌ A Home Cell Leader already exists for {new_home_cell}")
                    else:
                        new_user = {
                            'Username': new_username,
                            'Password': new_password,
                            'Role': new_role,
                            'Home_Cell_Group': new_home_cell
                        }
                        
                        if append_to_sheet(new_user, USERS_SHEET):
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
                    
                    if append_to_sheet(new_user, USERS_SHEET):
                        st.success(f"✅ User {new_username} added!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("Please fill in all required fields")
        
        st.divider()
        st.subheader("👥 Existing Users")
        users_df = read_sheet_as_dataframe(USERS_SHEET)
        if users_df is not None and not users_df.empty:
            # Don't show passwords
            display_df = users_df[['Username', 'Role', 'Home_Cell_Group']]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("Attendance Reports")
        
        attendance_df = read_sheet_as_dataframe(ATTENDANCE_SHEET)
        if attendance_df is not None and not attendance_df.empty:
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
            
            st.subheader("Recent Attendance by Home Cell")
            recent_dates = sorted(attendance_df['Date'].unique(), reverse=True)[:4]
            
            for date_val in recent_dates:
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
        
        members_df = read_sheet_as_dataframe(MEMBERS_SHEET)
        if members_df is not None:
            st.metric("Total Members", len(members_df))
        
        home_cells = get_home_cell_groups()
        st.metric("Total Home Cell Groups", len(home_cells))
        
        if home_cells:
            st.write("**Home Cell Groups:**")
            for cell in home_cells:
                st.write(f"- {cell}")

# Main App
def main():
    st.set_page_config(
        page_title="Church Attendance System",
        page_icon="🏛️",
        layout="wide"
    )
    
    # Initialize sheets
    with st.spinner("Connecting to Google Sheets..."):
        initialize_sheets()
    
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