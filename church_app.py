import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
import io
from supabase import create_client, Client
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

# ─────────────────────────────────────────────
# Supabase Configuration
# ─────────────────────────────────────────────
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

# ─────────────────────────────────────────────
# Session State
# ─────────────────────────────────────────────
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.home_cell = None

# ─────────────────────────────────────────────
# Database Helpers
# ─────────────────────────────────────────────
def get_all(table: str) -> pd.DataFrame:
    try:
        supabase = get_supabase_client()
        response = supabase.table(table).select("*").execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error reading {table}: {str(e)}")
        return pd.DataFrame()

def insert_row(table: str, data: dict) -> bool:
    try:
        supabase = get_supabase_client()
        supabase.table(table).insert(data).execute()
        return True
    except Exception as e:
        st.error(f"❌ Error inserting into {table}: {str(e)}")
        return False

def insert_rows(table: str, data: list) -> bool:
    try:
        supabase = get_supabase_client()
        supabase.table(table).insert(data).execute()
        return True
    except Exception as e:
        st.error(f"❌ Error inserting into {table}: {str(e)}")
        return False

def delete_rows(table: str, filters: dict) -> bool:
    try:
        supabase = get_supabase_client()
        query = supabase.table(table).delete()
        for col, val in filters.items():
            query = query.eq(col, val)
        query.execute()
        return True
    except Exception as e:
        st.error(f"❌ Error deleting from {table}: {str(e)}")
        return False

# ─────────────────────────────────────────────
# Cached Data
# ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_cached_members():
    return get_all("members")

@st.cache_data(ttl=60)
def get_cached_attendance():
    return get_all("attendance")

@st.cache_data(ttl=60)
def get_cached_welfare():
    return get_all("welfare")

def get_home_cell_groups():
    members_df = get_cached_members()
    if not members_df.empty and 'Home_Cell_Group' in members_df.columns:
        return sorted(members_df['Home_Cell_Group'].dropna().unique().tolist())
    return []

def get_members_by_cell(home_cell):
    members_df = get_cached_members()
    if not members_df.empty:
        return members_df[members_df['Home_Cell_Group'] == home_cell].copy()
    return pd.DataFrame()

# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────
def verify_login(username, password):
    try:
        supabase = get_supabase_client()
        response = supabase.table("users")\
            .select("*")\
            .eq("Username", username)\
            .eq("Password", password)\
            .execute()
        if response.data:
            user = response.data[0]
            return True, user['Role'], user['Home_Cell_Group']
    except Exception as e:
        st.error(f"❌ Login error: {str(e)}")
    return False, None, None

# ─────────────────────────────────────────────
# PDF Generators
# ─────────────────────────────────────────────
def generate_attendance_pdf(home_cell: str) -> bytes:
    """Generate attendance summary PDF for a home cell — all months"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=6)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10,
                                    textColor=colors.grey, spaceAfter=20)

    story.append(Paragraph("Attendance Report", title_style))
    story.append(Paragraph(f"Home Cell: {home_cell}", subtitle_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}", subtitle_style))
    story.append(Spacer(1, 0.5*cm))

    # Get attendance data
    attendance_df = get_cached_attendance()
    members = get_members_by_cell(home_cell)

    if attendance_df.empty or members.empty:
        story.append(Paragraph("No attendance data available.", styles['Normal']))
        doc.build(story)
        return buffer.getvalue()

    # Filter to this cell
    cell_att = attendance_df[attendance_df['Home_Cell_Group'] == home_cell].copy()
    if cell_att.empty:
        story.append(Paragraph("No attendance records for this cell yet.", styles['Normal']))
        doc.build(story)
        return buffer.getvalue()

    # Parse dates and get months
    cell_att['Date'] = pd.to_datetime(cell_att['Date'], errors='coerce')
    cell_att['Month'] = cell_att['Date'].dt.to_period('M')
    months = sorted(cell_att['Month'].dropna().unique())

    for month in months:
        month_label = pd.Timestamp(str(month)).strftime('%B %Y')
        story.append(Paragraph(f"Month: {month_label}", styles['Heading2']))
        story.append(Spacer(1, 0.3*cm))

        month_data = cell_att[cell_att['Month'] == month]

        # Build table data
        table_data = [['Member Name', 'Present', 'Absent']]

        for _, member in members.iterrows():
            name = member['Member_Name']
            member_records = month_data[month_data['Member_Name'] == name]
            present = len(member_records[member_records['Present'] == 'Yes'])
            absent = len(member_records[member_records['Present'] == 'No'])
            table_data.append([name, str(present), str(absent)])

        # Create table
        col_widths = [10*cm, 3*cm, 3*cm]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            # Alternating rows
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(t)
        story.append(Spacer(1, 0.8*cm))

    doc.build(story)
    return buffer.getvalue()


def generate_welfare_pdf(home_cell: str) -> bytes:
    """Generate welfare contributions PDF for a home cell"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, spaceAfter=6)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10,
                                    textColor=colors.grey, spaceAfter=20)

    story.append(Paragraph("Welfare Contributions Report", title_style))
    story.append(Paragraph(f"Home Cell: {home_cell}", subtitle_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}", subtitle_style))
    story.append(Spacer(1, 0.5*cm))

    welfare_df = get_cached_welfare()

    if welfare_df.empty:
        story.append(Paragraph("No welfare data available.", styles['Normal']))
        doc.build(story)
        return buffer.getvalue()

    cell_welfare = welfare_df[welfare_df['Home_Cell_Group'] == home_cell].copy()

    if cell_welfare.empty:
        story.append(Paragraph("No welfare records for this cell yet.", styles['Normal']))
        doc.build(story)
        return buffer.getvalue()

    # Sort by date
    cell_welfare = cell_welfare.sort_values('Date', ascending=False)

    # Summary metrics
    total = cell_welfare['Amount_GHS'].sum()
    contributors = cell_welfare['Member_Name'].nunique()

    summary_data = [
        ['Total Collected', 'Total Contributors'],
        [f"GHS {total:,.2f}", str(contributors)]
    ]
    summary_table = Table(summary_data, colWidths=[8*cm, 8*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.8*cm))

    # Detailed records
    story.append(Paragraph("Payment Details", styles['Heading2']))
    story.append(Spacer(1, 0.3*cm))

    table_data = [['Member Name', 'Amount (GHS)', 'Date']]
    for _, row in cell_welfare.iterrows():
        table_data.append([
            row['Member_Name'],
            f"GHS {float(row['Amount_GHS']):,.2f}",
            str(row['Date'])
        ])

    col_widths = [9*cm, 4*cm, 3.5*cm]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (1, 1), (2, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)

    # Per member summary
    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph("Summary Per Member", styles['Heading2']))
    story.append(Spacer(1, 0.3*cm))

    member_summary = cell_welfare.groupby('Member_Name')['Amount_GHS'].sum().reset_index()
    member_summary = member_summary.sort_values('Amount_GHS', ascending=False)

    summary_rows = [['Member Name', 'Total Contributed (GHS)']]
    for _, row in member_summary.iterrows():
        summary_rows.append([row['Member_Name'], f"GHS {float(row['Amount_GHS']):,.2f}"])

    s_table = Table(summary_rows, colWidths=[10*cm, 6.5*cm])
    s_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e7d32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(s_table)

    doc.build(story)
    return buffer.getvalue()

# ─────────────────────────────────────────────
# Attendance Summary Logic
# ─────────────────────────────────────────────
def update_attendance_summary():
    try:
        attendance_df = get_cached_attendance()
        members_df = get_cached_members()

        if attendance_df.empty or members_df.empty:
            st.warning("Not enough data to update summary")
            return False

        unique_dates = sorted(attendance_df['Date'].unique(), reverse=True)[:3]
        if len(unique_dates) < 3:
            st.info(f"Need at least 3 services. Currently have {len(unique_dates)}")
            return False

        supabase = get_supabase_client()
        supabase.table("attendance_summary").delete().neq("id", 0).execute()

        summary_records = []
        for _, member in members_df.iterrows():
            member_name = member['Member_Name']
            home_cell = member['Home_Cell_Group']

            member_att = attendance_df[
                (attendance_df['Member_Name'] == member_name) &
                (attendance_df['Date'].isin(unique_dates))
            ]

            attendance_status = []
            missed_count = 0
            has_attended_recently = False

            for d in unique_dates:
                rec = member_att[member_att['Date'] == d]
                if not rec.empty:
                    status = rec.iloc[0]['Present']
                    attendance_status.append(status)
                    if status == 'Yes':
                        has_attended_recently = True
                    elif status == 'No':
                        missed_count += 1
                else:
                    attendance_status.append('No')
                    missed_count += 1

            if missed_count >= 2 and not has_attended_recently:
                summary_records.append({
                    'Member_Name': member_name,
                    'Home_Cell_Group': home_cell,
                    'Last_3_Attendances': ' | '.join(attendance_status),
                    'Missed_Count': missed_count,
                    'Status': '⚠️ DANGER - Contact Member',
                    'Last_Updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

        if summary_records:
            insert_rows("attendance_summary", summary_records)
            st.success(f"✅ Updated summary with {len(summary_records)} at-risk members")
        else:
            st.success("✅ No at-risk members found!")

        # Clear attendance cache so next load is fresh
        get_cached_attendance.clear()
        return True

    except Exception as e:
        st.error(f"❌ Error updating summary: {str(e)}")
        return False

# ─────────────────────────────────────────────
# Pages
# ─────────────────────────────────────────────
def login_page():
    st.title("🏛️ Church Attendance System")
    st.subheader("Please Login")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            if username and password:
                with st.spinner("Verifying..."):
                    success, role, home_cell = verify_login(username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = role
                        st.session_state.home_cell = home_cell
                        st.success(f"✅ Welcome {username}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
            else:
                st.warning("⚠️ Please enter both username and password")

        st.divider()
        st.info("📱 This system works on mobile phones!")


def attendance_page():
    st.title("📋 Mark Attendance")

    if st.session_state.role not in ['Home Cell Leader', 'Admin']:
        st.warning("⚠️ You don't have permission to mark attendance.")
        return

    attendance_date = st.date_input("Select Date", value=date.today())

    if st.session_state.role == 'Admin':
        home_cells = get_home_cell_groups()
        if not home_cells:
            st.warning("❌ No home cell groups found.")
            return
        selected_cell = st.selectbox("Select Home Cell Group", home_cells)
    else:
        selected_cell = st.session_state.home_cell
        st.info(f"📌 Your Home Cell: **{selected_cell}**")

    if selected_cell:
        col_title, col_refresh = st.columns([3, 1])
        with col_refresh:
            if st.button("🔄 Refresh"):
                get_cached_members.clear()
                get_cached_attendance.clear()
                st.rerun()

        # Load members from cache (no DB call on checkbox click!)
        members = get_members_by_cell(selected_cell)

        if not members.empty:
            st.subheader(f"Members in {selected_cell}")
            st.write(f"📊 Total: {len(members)}")

            # Load existing attendance from cache
            attendance_df = get_cached_attendance()
            existing_df = pd.DataFrame()
            if not attendance_df.empty:
                existing_df = attendance_df[
                    (attendance_df['Date'] == str(attendance_date)) &
                    (attendance_df['Home_Cell_Group'] == selected_cell)
                ]

            attendance_dict = {}
            st.write("---")
            st.write("### ✅ Mark Attendance (Check = Present)")

            for idx, row in members.iterrows():
                member_name = row['Member_Name']
                default_value = False
                if not existing_df.empty:
                    rec = existing_df[existing_df['Member_Name'] == member_name]
                    if not rec.empty:
                        default_value = rec.iloc[0]['Present'] == 'Yes'

                attendance_dict[member_name] = st.checkbox(
                    member_name,
                    value=default_value,
                    key=f"att_{idx}_{member_name}"
                )

            st.divider()
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("💾 Submit Attendance", use_container_width=True, type="primary"):
                    with st.spinner("Saving..."):
                        delete_rows("attendance", {
                            "Date": str(attendance_date),
                            "Home_Cell_Group": selected_cell
                        })

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

                        if insert_rows("attendance", new_records):
                            present_count = sum(attendance_dict.values())
                            st.success(f"✅ Saved! {present_count}/{len(members)} present")
                            get_cached_attendance.clear()
                            update_attendance_summary()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to save")

            # ── PDF Download Section ──
            st.divider()
            st.subheader("📄 Download Attendance Report")
            st.caption("Full attendance report for all months — your cell only")

            if st.button("📥 Generate PDF Report", use_container_width=True):
                with st.spinner("Generating PDF..."):
                    pdf_bytes = generate_attendance_pdf(selected_cell)
                    filename = f"Attendance_{selected_cell.replace(' ', '_')}_{date.today()}.pdf"
                    st.download_button(
                        label="⬇️ Download Attendance PDF",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        use_container_width=True
                    )
        else:
            st.warning(f"⚠️ No members found in {selected_cell}")


def welfare_page():
    st.title("💝 Welfare Contributions")
    st.info("💡 Select your home cell then enter amounts for contributing members")

    col1, col2 = st.columns([3, 1])
    with col1:
        contribution_date = st.date_input("Date", value=date.today())
    with col2:
        if st.button("🔄 Refresh"):
            get_cached_members.clear()
            get_cached_welfare.clear()
            st.rerun()

    # ── Home Cell Selection ──
    if st.session_state.role == 'Admin':
        home_cells = get_home_cell_groups()
        if not home_cells:
            st.warning("❌ No home cell groups found.")
            return
        selected_cell = st.selectbox("Select Home Cell Group", home_cells)
    else:
        selected_cell = st.session_state.home_cell
        st.info(f"📌 Your Home Cell: **{selected_cell}**")

    if not selected_cell:
        st.warning("⚠️ No home cell assigned to your account.")
        return

    st.divider()

    search_term = st.text_input("🔍 Search to filter list (optional)")

    # Load members for selected cell only
    members_df = get_members_by_cell(selected_cell)

    if members_df.empty:
        st.warning(f"⚠️ No members found in {selected_cell}")
        return

    members_df = members_df.sort_values('Member_Name')
    if search_term:
        members_df = members_df[members_df['Member_Name'].str.contains(search_term, case=False, na=False)]

    st.info(f"📊 Showing {len(members_df)} members from **{selected_cell}**")

    if 'welfare_amounts' not in st.session_state:
        st.session_state.welfare_amounts = {}

    col1, col2, col3 = st.columns([3, 2, 2])
    with col1: st.markdown("**Member Name**")
    with col2: st.markdown("**Home Cell**")
    with col3: st.markdown("**Amount (GHS)**")
    st.markdown("---")

    welfare_inputs = {}
    for idx, row in members_df.iterrows():
        member_name = row['Member_Name']
        home_cell = row.get('Home_Cell_Group', selected_cell)

        col1, col2, col3 = st.columns([3, 2, 2])
        with col1: st.write(member_name)
        with col2: st.caption(home_cell)
        with col3:
            amount = st.number_input(
                f"Amount for {member_name}",
                min_value=0.0, step=5.0,
                value=st.session_state.welfare_amounts.get(member_name, 0.0),
                key=f"welfare_{member_name}_{idx}",
                label_visibility="collapsed"
            )
            welfare_inputs[member_name] = {'amount': amount, 'home_cell': home_cell}
            st.session_state.welfare_amounts[member_name] = amount

    st.divider()
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("💾 Submit All Entries", use_container_width=True, type="primary"):
            contributing = {n: d for n, d in welfare_inputs.items() if d['amount'] > 0}
            if not contributing:
                st.warning("⚠️ No amounts entered.")
            else:
                with st.spinner("Saving..."):
                    new_records = []
                    total = 0
                    for member_name, data in contributing.items():
                        new_records.append({
                            'Date': str(contribution_date),
                            'Member_Name': member_name,
                            'Home_Cell_Group': data['home_cell'],
                            'Amount_GHS': data['amount'],
                            'Collected_By': st.session_state.username,
                            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        total += data['amount']

                    if insert_rows("welfare", new_records):
                        st.success(f"✅ {len(new_records)} entries recorded! Total: GHS {total:.2f}")
                        st.session_state.welfare_amounts = {}
                        get_cached_welfare.clear()
                        time.sleep(2)
                        st.rerun()

    # ── Recent Welfare for this cell ──
    st.divider()
    st.subheader(f"Recent Contributions — {selected_cell}")
    welfare_df = get_cached_welfare()
    if not welfare_df.empty:
        cell_welfare = welfare_df[welfare_df['Home_Cell_Group'] == selected_cell]
        if not cell_welfare.empty:
            cell_welfare = cell_welfare.sort_values('Timestamp', ascending=False)
            st.dataframe(
                cell_welfare[['Date', 'Member_Name', 'Amount_GHS', 'Collected_By']].head(20),
                use_container_width=True, hide_index=True
            )
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Total Collected", f"GHS {cell_welfare['Amount_GHS'].sum():,.2f}")
            with col2: st.metric("Contributors", cell_welfare['Member_Name'].nunique())
            with col3:
                today_total = cell_welfare[cell_welfare['Date'] == str(date.today())]['Amount_GHS'].sum()
                st.metric("Today", f"GHS {today_total:.2f}")
        else:
            st.info("No contributions yet for this cell")
    else:
        st.info("No contributions recorded yet")

    # ── PDF Download Section ──
    st.divider()
    st.subheader("📄 Download Welfare Report")
    st.caption("Full welfare contributions report — your cell only")

    if st.button("📥 Generate Welfare PDF", use_container_width=True):
        with st.spinner("Generating PDF..."):
            pdf_bytes = generate_welfare_pdf(selected_cell)
            filename = f"Welfare_{selected_cell.replace(' ', '_')}_{date.today()}.pdf"
            st.download_button(
                label="⬇️ Download Welfare PDF",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True
            )


def attendance_summary_page():
    st.title("⚠️ Members at Risk")

    if st.session_state.role not in ['Home Cell Leader', 'Admin']:
        st.warning("⚠️ Only Cell Leaders and Admins can view this.")
        return

    st.info("📞 Members who missed 2+ of last 3 services and have NOT attended recently")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh & Update"):
            with st.spinner("Updating..."):
                update_attendance_summary()
                time.sleep(1)
                st.rerun()

    summary_df = get_all("attendance_summary")

    if not summary_df.empty:
        if st.session_state.role == 'Home Cell Leader':
            summary_df = summary_df[summary_df['Home_Cell_Group'] == st.session_state.home_cell]

        if not summary_df.empty:
            st.metric("Members Needing Contact", len(summary_df))
            st.divider()

            for _, row in summary_df.iterrows():
                with st.expander(f"⚠️ {row['Member_Name']} - {row['Home_Cell_Group']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Last 3 Services:** {row['Last_3_Attendances']}")
                        st.write(f"**Missed:** {row['Missed_Count']} of 3")
                        st.write(f"**Status:** {row['Status']}")
                    with col2:
                        members_df = get_cached_members()
                        if not members_df.empty:
                            info = members_df[members_df['Member_Name'] == row['Member_Name']]
                            if not info.empty:
                                phone = info.iloc[0].get('Phone', 'N/A')
                                st.write(f"**Phone:** {phone}")
                                if phone and phone != 'N/A':
                                    st.markdown(f"📱 [Call {phone}](tel:{phone})")
                    st.caption(f"Last Updated: {row['Last_Updated']}")
        else:
            st.success("✅ No members at risk in your cell!")
    else:
        st.info("ℹ️ No summary yet. Need at least 3 services recorded.")


def offerings_page():
    st.title("💰 Offerings & Tithes")

    if st.session_state.role not in ['Accountant', 'Admin']:
        st.warning("⚠️ You don't have permission.")
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
                if insert_row("offerings", {
                    'Date': str(offering_date),
                    'Amount_GHS': amount,
                    'Meeting_Type': meeting_type,
                    'Description': description,
                    'Entered_By': st.session_state.username,
                    'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }):
                    st.success(f"✅ GHS {amount:.2f} recorded!")
                    time.sleep(2)
                    st.rerun()
        else:
            st.warning("⚠️ Enter amount > 0")

    st.divider()
    st.subheader("Recent Offerings")
    offerings_df = get_all("offerings")
    if not offerings_df.empty:
        offerings_df = offerings_df.sort_values('Timestamp', ascending=False)
        st.dataframe(offerings_df[['Date', 'Amount_GHS', 'Meeting_Type', 'Description', 'Entered_By']].head(10),
                     use_container_width=True, hide_index=True)
        st.metric("Total", f"GHS {offerings_df['Amount_GHS'].sum():,.2f}")
    else:
        st.info("ℹ️ No offerings recorded yet")


def search_members_page():
    st.title("🔍 Search Members")
    search_term = st.text_input("Search by Name", placeholder="Enter name...")

    members_df = get_cached_members()

    if search_term:
        if not members_df.empty:
            results = members_df[members_df['Member_Name'].str.contains(search_term, case=False, na=False)]
            if not results.empty:
                st.success(f"✅ Found {len(results)} member(s)")
                for _, row in results.iterrows():
                    with st.expander(f"👤 {row['Member_Name']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Home Cell:** {row.get('Home_Cell_Group', 'N/A')}")
                            st.write(f"**Phone:** {row.get('Phone', 'N/A')}")
                            st.write(f"**Gender:** {row.get('Gender', 'N/A')}")
                        with col2:
                            st.write(f"**Email:** {row.get('Email', 'N/A')}")
            else:
                st.warning("⚠️ No members found")
    else:
        if not members_df.empty:
            st.info(f"📊 Total Members: {len(members_df)}")
            if 'Home_Cell_Group' in members_df.columns:
                st.subheader("Members by Cell")
                st.bar_chart(members_df['Home_Cell_Group'].value_counts())


def announcements_page():
    st.title("📢 Announcements")

    if st.session_state.role == 'Admin':
        with st.expander("➕ Post New Announcement"):
            title = st.text_input("Title")
            message = st.text_area("Message")
            if st.button("Post", type="primary"):
                if title and message:
                    with st.spinner("Posting..."):
                        if insert_row("announcements", {
                            'Date': str(date.today()),
                            'Title': title,
                            'Message': message,
                            'Posted_By': st.session_state.username,
                            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }):
                            st.success("✅ Posted!")
                            time.sleep(2)
                            st.rerun()
                else:
                    st.warning("⚠️ Please enter both title and message")

    announcements_df = get_all("announcements")
    if not announcements_df.empty:
        announcements_df = announcements_df.sort_values('Timestamp', ascending=False)
        for _, row in announcements_df.head(10).iterrows():
            st.markdown(f"### 📌 {row['Title']}")
            st.write(row['Message'])
            st.caption(f"Posted on {row['Date']} by {row['Posted_By']}")
            st.divider()
    else:
        st.info("ℹ️ No announcements yet")


def admin_page():
    st.title("⚙️ Admin Panel")

    if st.session_state.role != 'Admin':
        st.warning("⚠️ Admin only")
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

        if st.button("Add User", type="primary"):
            if new_username and new_password:
                supabase = get_supabase_client()
                existing = supabase.table("users").select("Username").eq("Username", new_username).execute()
                if existing.data:
                    st.error("❌ Username already exists!")
                else:
                    if insert_row("users", {
                        'Username': new_username,
                        'Password': new_password,
                        'Role': new_role,
                        'Home_Cell_Group': new_home_cell
                    }):
                        st.success(f"✅ Added {new_username}!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("⚠️ Please enter username and password")

        st.divider()
        st.subheader("Existing Users")
        users_df = get_all("users")
        if not users_df.empty:
            st.dataframe(users_df[['Username', 'Role', 'Home_Cell_Group']], use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Attendance Reports")
        attendance_df = get_cached_attendance()
        if not attendance_df.empty:
            col1, col2, col3 = st.columns(3)
            present_count = len(attendance_df[attendance_df['Present'] == 'Yes'])
            rate = (present_count / len(attendance_df)) * 100
            with col1: st.metric("Total Records", len(attendance_df))
            with col2: st.metric("Present", present_count)
            with col3: st.metric("Attendance Rate", f"{rate:.1f}%")
            st.divider()
            st.dataframe(attendance_df.sort_values('Timestamp', ascending=False)
                         [['Date', 'Home_Cell_Group', 'Member_Name', 'Present', 'Recorded_By']].head(20),
                         use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ No attendance data yet")

        st.divider()
        st.subheader("Welfare Reports")
        welfare_df = get_cached_welfare()
        if not welfare_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Total Collected", f"GHS {welfare_df['Amount_GHS'].sum():,.2f}")
            with col2: st.metric("Contributors", welfare_df['Member_Name'].nunique())
            with col3: st.metric("Records", len(welfare_df))
        else:
            st.info("ℹ️ No welfare data yet")

    with tab3:
        st.subheader("System Information")
        members_df = get_cached_members()
        col1, col2 = st.columns(2)
        with col1: st.metric("Total Members", len(members_df) if not members_df.empty else 0)
        with col2: st.metric("Home Cell Groups", len(get_home_cell_groups()))

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Clear Cache", use_container_width=True):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("✅ Cache cleared!")
                time.sleep(1)
                st.rerun()
        with col2:
            if st.button("📊 Update Summary", use_container_width=True):
                with st.spinner("Updating..."):
                    update_attendance_summary()
                    time.sleep(1)
                    st.rerun()


# ─────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────
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
            st.write(f"Role: **{st.session_state.role}**")
            if st.session_state.home_cell and st.session_state.home_cell != "N/A":
                st.write(f"Cell: **{st.session_state.home_cell}**")
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
            if st.button("🚪 Logout", use_container_width=True):
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