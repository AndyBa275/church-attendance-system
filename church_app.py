import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
import time
from pathlib import Path
import threading

# File paths - works both locally and on Streamlit Cloud
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MEMBERS_FILE = os.path.join(BASE_PATH, "Members.xlsx")
ATTENDANCE_FILE = os.path.join(BASE_PATH, "Attendance.xlsx")
OFFERINGS_FILE = os.path.join(BASE_PATH, "Offerings.xlsx")
USERS_FILE = os.path.join(BASE_PATH, "Users.xlsx")
ANNOUNCEMENTS_FILE = os.path.join(BASE_PATH, "Announcements.xlsx")

# File lock
file_lock = threading.Lock()

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.home_cell = None

# Helper Functions
def safe_read_excel(file_path):
    """Safely read Excel file with lock"""
    with file_lock:
        if os.path.exists(file_path):
            return pd.read_excel(file_path)
        return None

def safe_write_excel(df, file_path):
    """Safely write to Excel file with lock"""
    with file_lock:
        df.to_excel(file_path, index=False)
        time.sleep(0.1)  # Small delay to ensure file is written

def initialize_files():
    """Create necessary files if they don't exist"""
    
    # Create Attendance file if doesn't exist
    if not os.path.exists(ATTENDANCE_FILE):
        attendance_df = pd.DataFrame(columns=[
            'Date', 'Home_Cell_Group', 'Member_Name', 'Present', 'Recorded_By', 'Timestamp'
        ])
        safe_write_excel(attendance_df, ATTENDANCE_FILE)
    
    # Create Offerings file if doesn't exist
    if not os.path.exists(OFFERINGS_FILE):
        offerings_df = pd.DataFrame(columns=[
            'Date', 'Amount_GHS', 'Meeting_Type', 'Description', 'Entered_By', 'Timestamp'
        ])
        safe_write_excel(offerings_df, OFFERINGS_FILE)
    
    # Create Users file if doesn't exist
    if not os.path.exists(USERS_FILE):
        users_df = pd.DataFrame({
            'Username': ['admin', 'accountant'],
            'Password': ['admin123', 'account123'],
            'Role': ['Admin', 'Accountant'],
            'Home_Cell_Group': ['All', 'N/A']
        })
        safe_write_excel(users_df, USERS_FILE)
    
    # Create Announcements file if doesn't exist
    if not os.path.exists(ANNOUNCEMENTS_FILE):
        announcements_df = pd.DataFrame(columns=[
            'Date', 'Title', 'Message', 'Posted_By', 'Timestamp'
        ])
        safe_write_excel(announcements_df, ANNOUNCEMENTS_FILE)

def verify_login(username, password):
    """Verify user credentials"""
    users_df = safe_read_excel(USERS_FILE)
    if users_df is not None:
        user = users_df[(users_df['Username'] == username) & (users_df['Password'] == password)]
        if not user.empty:
            return True, user.iloc[0]['Role'], user.iloc[0]['Home_Cell_Group']
    return False, None, None

def get_home_cell_groups():
    """Get unique home cell groups from members file"""
    members_df = safe_read_excel(MEMBERS_FILE)
    if members_df is not None and 'Home_Cell_Group' in members_df.columns:
        # Get last Home_Cell_Group column (there seem to be duplicates in headers)
        return sorted(members_df['Home_Cell_Group'].dropna().unique().tolist())
    return []

def get_members_by_cell(home_cell):
    """Get members for a specific home cell"""
    members_df = safe_read_excel(MEMBERS_FILE)
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
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
                    # Debug info for troubleshooting
                    with st.expander("🔍 Debug Info (Admin Only)"):
                        users_df = safe_read_excel(USERS_FILE)
                        if users_df is not None:
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
            attendance_df = safe_read_excel(ATTENDANCE_FILE)
            existing_attendance = None
            if attendance_df is not None:
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
                    attendance_df = safe_read_excel(ATTENDANCE_FILE)
                    
                    # Remove existing records for this date and cell (to update)
                    if attendance_df is not None:
                        attendance_df = attendance_df[
                            ~((attendance_df['Date'] == str(attendance_date)) & 
                              (attendance_df['Home_Cell_Group'] == selected_cell))
                        ]
                    else:
                        attendance_df = pd.DataFrame()
                    
                    # Append new records
                    new_df = pd.DataFrame(new_records)
                    attendance_df = pd.concat([attendance_df, new_df], ignore_index=True)
                    
                    # Save
                    safe_write_excel(attendance_df, ATTENDANCE_FILE)
                    
                    present_count = sum(attendance_dict.values())
                    st.success(f"✅ Attendance saved! {present_count}/{len(members)} members present")
                    time.sleep(1)
                    st.rerun()
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
            offerings_df = safe_read_excel(OFFERINGS_FILE)
            
            new_record = {
                'Date': str(offering_date),
                'Amount_GHS': amount,
                'Meeting_Type': meeting_type,
                'Description': description,
                'Entered_By': st.session_state.username,
                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            new_df = pd.DataFrame([new_record])
            if offerings_df is not None:
                offerings_df = pd.concat([offerings_df, new_df], ignore_index=True)
            else:
                offerings_df = new_df
            
            safe_write_excel(offerings_df, OFFERINGS_FILE)
            st.success(f"✅ Offering of GHS {amount:.2f} recorded!")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("Please enter an amount greater than 0")
    
    # Display recent offerings
    st.divider()
    st.subheader("Recent Offerings")
    
    offerings_df = safe_read_excel(OFFERINGS_FILE)
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
        members_df = safe_read_excel(MEMBERS_FILE)
        
        if members_df is not None:
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
        members_df = safe_read_excel(MEMBERS_FILE)
        if members_df is not None:
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
                    announcements_df = safe_read_excel(ANNOUNCEMENTS_FILE)
                    
                    new_announcement = {
                        'Date': str(date.today()),
                        'Title': title,
                        'Message': message,
                        'Posted_By': st.session_state.username,
                        'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    new_df = pd.DataFrame([new_announcement])
                    if announcements_df is not None:
                        announcements_df = pd.concat([announcements_df, new_df], ignore_index=True)
                    else:
                        announcements_df = new_df
                    
                    safe_write_excel(announcements_df, ANNOUNCEMENTS_FILE)
                    st.success("✅ Announcement posted!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Please fill in both title and message")
    
    # Display announcements
    st.subheader("Recent Announcements")
    announcements_df = safe_read_excel(ANNOUNCEMENTS_FILE)
    
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
                new_home_cell = st.selectbox("Home Cell Group", home_cells)
            else:
                new_home_cell = "N/A"
        
        if st.button("Add User", type="primary"):
            if new_username and new_password:
                users_df = safe_read_excel(USERS_FILE)
                
                # Check if username exists
                if new_username in users_df['Username'].values:
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
                        
                        users_df = pd.concat([users_df, pd.DataFrame([new_user])], ignore_index=True)
                        safe_write_excel(users_df, USERS_FILE)
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
                    
                    users_df = pd.concat([users_df, pd.DataFrame([new_user])], ignore_index=True)
                    safe_write_excel(users_df, USERS_FILE)
                    st.success(f"✅ User {new_username} added!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("Please fill in all fields")
        
        st.divider()
        st.subheader("👥 Manage Existing Users")
        users_df = safe_read_excel(USERS_FILE)
        if users_df is not None and not users_df.empty:
            
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
                        current_cell_idx = home_cells.index(user_data['Home_Cell_Group']) if user_data['Home_Cell_Group'] in home_cells else 0
                        edit_home_cell = st.selectbox(
                            "Home Cell Group", 
                            home_cells,
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
                                
                                safe_write_excel(users_df, USERS_FILE)
                                st.success(f"✅ User {edit_username} updated!")
                                time.sleep(1)
                                st.rerun()
                        else:
                            # Update user
                            users_df.loc[users_df['Username'] == edit_username, 'Role'] = edit_role
                            users_df.loc[users_df['Username'] == edit_username, 'Home_Cell_Group'] = edit_home_cell
                            if new_pass:
                                users_df.loc[users_df['Username'] == edit_username, 'Password'] = new_pass
                            
                            safe_write_excel(users_df, USERS_FILE)
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
                                safe_write_excel(users_df, USERS_FILE)
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
        attendance_df = safe_read_excel(ATTENDANCE_FILE)
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
            
            # Recent attendance by cell
            st.subheader("Recent Attendance by Home Cell")
            recent_dates = attendance_df['Date'].unique()[-4:]  # Last 4 dates
            
            for date in sorted(recent_dates, reverse=True):
                with st.expander(f"📅 {date}"):
                    date_data = attendance_df[attendance_df['Date'] == date]
                    cell_summary = date_data.groupby('Home_Cell_Group')['Present'].apply(
                        lambda x: f"{(x == 'Yes').sum()}/{len(x)}"
                    )
                    st.dataframe(cell_summary, use_container_width=True)
        else:
            st.info("No attendance data yet")
    
    with tab3:
        st.subheader("System Information")
        
        members_df = safe_read_excel(MEMBERS_FILE)
        if members_df is not None:
            st.metric("Total Members", len(members_df))
        
        home_cells = get_home_cell_groups()
        st.metric("Total Home Cell Groups", len(home_cells))
        
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
    
    # Initialize files
    initialize_files()
    
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