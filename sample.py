import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
import plotly.graph_objects as go
import warnings
import os
import json
import io
import tempfile

warnings.filterwarnings('ignore')

# ========== CONFIGURATION (with fallback credentials) ==========
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSOERBZB4TXUBp_QmForDmyGaMcb8gyRAftJMXqp_ymZusgYs67zF4koOegfsnZcUxpKE8j1yzAWB38/pub?gid=1105229130&single=true&output=csv"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Try to read secrets, but fallback to hardcoded values
SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "chauhandeesingh@gmail.com")
SENDER_PASSWORD = st.secrets.get("SENDER_PASSWORD", "empxwcwfvmbphvsw")

# Multiple primary recipients (as a list)
DEFAULT_PRIMARY = [
    "emurugesan.padget@dixoninfo.com",
    "prateek.padget60@dixoninfo.com"
]
PRIMARY_RECIPIENTS = st.secrets.get("PRIMARY_RECIPIENTS", DEFAULT_PRIMARY)

# CC recipients (list)
DEFAULT_CC = [
    "chauhandeesingh@gmail.com",
    "ramnaresh.padget@dixoninfo.com",
    "charlesk.padget@dixoninfo.com",
    "soban.padget@dixoninfo.com",
    "gajanand.padget60@dixoninfo.com"
]
CC_RECIPIENTS = st.secrets.get("CC_RECIPIENTS", DEFAULT_CC)

# Ensure both are lists
if isinstance(PRIMARY_RECIPIENTS, str):
    PRIMARY_RECIPIENTS = [PRIMARY_RECIPIENTS]
if isinstance(CC_RECIPIENTS, str):
    CC_RECIPIENTS = [CC_RECIPIENTS]

EMAIL_CONFIGURED = all([SENDER_EMAIL, SENDER_PASSWORD, PRIMARY_RECIPIENTS])

# Auto email settings
AUTO_EMAIL_HOUR = 9
AUTO_EMAIL_MINUTE = 0
AUTO_EMAIL_ENABLED = True

# Persistent state file – uses system temp directory (works on Windows/Linux/macOS)
STATE_FILE = os.path.join(tempfile.gettempdir(), "golden_sample_email_state.json")
# ===================================

st.set_page_config(
    page_title="Golden Sample Tracker",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Professional CSS Styling (unchanged)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 0.8rem 2rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        font-size: 1.5rem !important;
        margin: 0 !important;
        padding: 0 !important;
        font-weight: 600 !important;
    }
    .metric-card {
        background: white;
        padding: 0.6rem;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
        text-align: center;
        transition: all 0.2s;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }
    .metric-label {
        font-size: 0.7rem;
        color: #6c757d;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    .alert-success {
        background: linear-gradient(135deg, #f0fdf4 0%, #f3fef7 100%);
        border-left: 3px solid #10b981;
        padding: 0.5rem 0.8rem;
        border-radius: 6px;
        margin: 0.5rem 0;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .control-bar {
        background: #f8f9fa;
        padding: 0.8rem 1rem;
        border-radius: 10px;
        margin: 0.5rem 0 1rem 0;
        border: 1px solid #e9ecef;
    }
    .stButton button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        padding: 0.4rem 0.8rem !important;
        font-size: 0.8rem !important;
        transition: all 0.2s !important;
    }
    .stSelectbox label, .stTextInput label {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.2rem !important;
    }
    .stSelectbox, .stTextInput {
        font-size: 0.85rem !important;
    }
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e9ecef;
        margin-top: 0.5rem;
    }
    .chart-container {
        background: white;
        padding: 0.5rem;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        margin-bottom: 0.5rem;
    }
    hr {
        margin: 0.5rem 0;
        border-color: #e9ecef;
    }
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        margin: 0.5rem 0;
        color: #1f2937;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'email_sent_today' not in st.session_state:
    st.session_state.email_sent_today = False
if 'last_email_date' not in st.session_state:
    st.session_state.last_email_date = None
if 'primary_recipients' not in st.session_state:
    st.session_state.primary_recipients = PRIMARY_RECIPIENTS.copy()
if 'cc_recipients' not in st.session_state:
    st.session_state.cc_recipients = CC_RECIPIENTS.copy() if isinstance(CC_RECIPIENTS, list) else []
if 'df' not in st.session_state:
    st.session_state.df = None

# ─────────────────────────────────────────────────────────────
#  PERSISTENT STATE
# ─────────────────────────────────────────────────────────────
def _load_state() -> dict:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"last_sent_date": None, "last_sent_time": None}

def _save_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def _should_send_email_today() -> bool:
    state = _load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    return state.get("last_sent_date") != today

def _mark_email_sent():
    state = _load_state()
    now = datetime.now()
    state["last_sent_date"] = now.strftime("%Y-%m-%d")
    state["last_sent_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
    _save_state(state)
    st.session_state.email_sent_today = True
    st.session_state.last_email_date = now

# ─────────────────────────────────────────────────────────────
#  DATA HELPERS
# ─────────────────────────────────────────────────────────────
def parse_date_safe(date_str):
    if pd.isna(date_str) or date_str == '' or date_str is None:
        return None
    try:
        date_str = str(date_str).strip()
        for sep in ['-', '/', '.']:
            if sep in date_str:
                parts = date_str.split(sep)
                if len(parts) == 3:
                    day, month, year = parts
                    if day.isdigit() and month.isdigit() and year.isdigit():
                        if len(year) == 2:
                            year = '20' + year
                        return datetime(int(year), int(month), int(day))
        return pd.to_datetime(date_str, dayfirst=True, errors='coerce')
    except Exception:
        return None

@st.cache_data(ttl=300)
def fetch_data():
    try:
        df = pd.read_csv(CSV_URL)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

def process_data(df):
    if df is None:
        return None
    df = df.copy()
    df.columns = df.columns.str.strip()
    
    required_cols = ['Validation Date', 'Staus', 'Model']
    for col in required_cols:
        if col not in df.columns:
            st.error(f"Missing column: {col}")
            return None

    def clean_status(s):
        if pd.isna(s) or s == '':
            return 'Unknown'
        s = str(s).strip().lower()
        if 'ok' in s or s == 'good':
            return 'OK'
        elif 'ng' in s or 'fail' in s or 'not' in s:
            return 'NG'
        elif 'pending' in s or 'validation' in s:
            return 'Pending'
        else:
            return 'Other'
    
    df['Staus'] = df['Staus'].apply(clean_status)
    df['Validation Date Parsed'] = df['Validation Date'].apply(parse_date_safe)
    df = df.dropna(subset=['Validation Date Parsed'])
   
    if df.empty:
        return None
    
    validation_dates = pd.Series(df['Validation Date Parsed'])
    revalidation_dates = validation_dates + pd.Timedelta(days=45)
    today = datetime.now().date()
    
    df['Days Left'] = [
        (r.date() - today).days if pd.notna(r) else None for r in revalidation_dates
    ]
    df['Validation Date Display'] = validation_dates.dt.strftime('%d-%m-%Y')
    df['Revalidation Due Display'] = revalidation_dates.dt.strftime('%d-%m-%Y')

    def get_alert_status(row):
        d = row['Days Left']
        s = str(row.get('Staus', '')).lower()
        if pd.isna(d):
            return 'Unknown'
        if s == 'ok':
            return 'Completed'
        if d < 0:
            return 'Overdue'
        if d <= 3:
            return 'Urgent'
        if d <= 7:
            return 'Due Soon'
        return 'On Track'
    
    df['Alert Status'] = df.apply(get_alert_status, axis=1)
   
    df = df.dropna(subset=['Model', 'Staus', 'Validation Date Display'])
    df = df[df['Model'].astype(str).str.strip() != '']
    df = df[df['Staus'].astype(str).str.strip() != '']

    return df

def get_due_records(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df[(df['Days Left'] <= 3) & (df['Days Left'] >= 0) & (df['Staus'].str.lower() != 'ok')]

def get_overdue_records(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df[(df['Days Left'] < 0) & (df['Staus'].str.lower() != 'ok')]

# ─────────────────────────────────────────────────────────────
#  EMAIL (with CSV attachment, supports multiple primary recipients)
# ─────────────────────────────────────────────────────────────
def send_email_alert(df, primary_recipients, cc_recipients):
    if not EMAIL_CONFIGURED:
        return False, "Email credentials not configured."

    due_records = get_due_records(df)
    overdue_records = get_overdue_records(df)

    if due_records.empty and overdue_records.empty:
        return False, "No records requiring immediate attention"

    # Clean up lists
    primary_list = [p.strip() for p in primary_recipients if p and p.strip()]
    cc_list = [c.strip() for c in cc_recipients if c and c.strip()]

    if not primary_list:
        return False, "No valid primary recipients"

    try:
        # Generate HTML body
        email_body = generate_email_html(due_records, overdue_records)

        # Create message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ', '.join(primary_list)          # Multiple primary recipients
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)

        total = len(due_records) + len(overdue_records)
        msg['Subject'] = f"🚨 Golden Sample Alert: {total} Sample(s) Need Attention"
        msg.attach(MIMEText(email_body, 'html'))

        # --- Attach CSV report of the alert records ---
        alert_records = pd.concat([due_records, overdue_records])
        if not alert_records.empty:
            csv_buffer = io.StringIO()
            alert_records[['Model', 'Validation Date Display', 'Revalidation Due Display',
                           'Days Left', 'Staus', 'Incharge', 'Alert Status']].to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()

            part = MIMEBase('application', 'octet-stream')
            part.set_payload(csv_data.encode('utf-8'))
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename=golden_sample_alert_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
            )
            msg.attach(part)

        # Send – include all recipients (primary + CC) in the envelope
        all_recipients = primary_list + cc_list
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg, to_addrs=all_recipients)

        return True, f"Alert sent to {len(primary_list)} primary and {len(cc_list)} CC recipients with CSV attachment."
    except Exception as e:
        return False, f"Email failed: {e}"

def generate_email_html(due_records, overdue_records):
    total = len(due_records) + len(overdue_records)
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Inter', Arial, sans-serif; margin: 0; padding: 20px; background: #f8fafc; }}
            .header {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 20px; text-align: center; border-radius: 12px; }}
            .alert {{ background: #fef3f2; border-left: 5px solid #ef4444; padding: 15px; margin: 15px 0; border-radius: 8px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 15px 0; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            th {{ background: #1e40af; color: white; padding: 12px 8px; text-align: left; }}
            td {{ padding: 10px 8px; border-bottom: 1px solid #e2e8f0; }}
            tr:hover {{ background: #f1f5f9; }}
            .overdue {{ background: #fee2e2 !important; }}
            .urgent {{ background: #fef3c7 !important; }}
            .footer {{ text-align: center; margin-top: 20px; color: #64748b; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>Golden Sample Revalidation Tracker</h2>
            <p>🚨 Urgent Action Required - {total} Sample(s)</p>
        </div>
        
        <div class="alert">
            <strong>⚠️ ALERT SUMMARY:</strong><br>
            🔴 {len(overdue_records)} Overdue Samples<br>
            ⚡ {len(due_records)} Samples Due Within 3 Days
        </div>
    """

    if not overdue_records.empty:
        html += "<h3 style='color:#ef4444;'>🔴 Overdue Samples</h3>"
        html += overdue_records[['Model', 'Validation Date Display', 'Revalidation Due Display', 
                               'Days Left', 'Staus', 'Incharge']].to_html(index=False, escape=False, classes="table")
    
    if not due_records.empty:
        html += "<h3 style='color:#f59e0b;'>⚠️ Samples Due Within 3 Days</h3>"
        html += due_records[['Model', 'Validation Date Display', 'Revalidation Due Display', 
                           'Days Left', 'Staus', 'Incharge']].to_html(index=False, escape=False, classes="table")

    html += f"""
        <div class="footer">
            Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')} | 
            Revalidation Cycle: 45 Days
        </div>
    </body>
    </html>
    """
    return html

def check_and_send_auto_email(df):
    if not AUTO_EMAIL_ENABLED or not EMAIL_CONFIGURED:
        return False, "Auto email disabled or not configured"
    
    now = datetime.now()
    if now.hour == AUTO_EMAIL_HOUR and now.minute == AUTO_EMAIL_MINUTE:
        if not _should_send_email_today():
            return False, "Email already sent today"
        
        due = get_due_records(df)
        over = get_overdue_records(df)
        
        if due.empty and over.empty:
            _mark_email_sent()
            return False, "No urgent samples"
        
        success, msg = send_email_alert(df, st.session_state.primary_recipients, st.session_state.cc_recipients)
        if success:
            _mark_email_sent()
            return True, "✅ Auto email sent"
        return False, msg
    
    return False, ""

# ─────────────────────────────────────────────────────────────
#  CHARTS
# ─────────────────────────────────────────────────────────────
def create_status_chart(df):
    if df.empty:
        fig = go.Figure()
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        return fig

    counts = df['Staus'].value_counts()
    colors = {
        'OK': '#10b981',
        'Pending': '#f59e0b',
        'NG': '#ef4444',
        'Other': '#6b7280'
    }

    fig = go.Figure(data=[go.Pie(
        labels=counts.index.tolist(),
        values=counts.values.tolist(),
        hole=0.60,
        marker_colors=[colors.get(status, '#6b7280') for status in counts.index],
        textinfo='label+percent',
        textposition='outside',
        textfont=dict(family='Inter', size=11),
        hoverinfo='label+value+percent'
    )])

    fig.update_layout(
        title=dict(text="Status Distribution", font=dict(family='Inter', size=14, weight='bold')),
        height=280,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=50, b=80),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def create_urgency_chart(df):
    alert_df = df[df['Staus'].str.lower() != 'ok'].copy()
   
    if alert_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No pending samples", x=0.5, y=0.5, showarrow=False,
                          font=dict(size=14, color="#64748b"))
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        return fig

    def cat(d):
        if pd.isna(d): return 'Unknown'
        if d < 0: return 'Overdue'
        if d <= 3: return 'Urgent (0-3)'
        if d <= 7: return 'Due Soon (4-7)'
        return 'On Track'
    
    alert_df['Category'] = alert_df['Days Left'].apply(cat)
    counts = alert_df['Category'].value_counts().reindex(
        ['Overdue', 'Urgent (0-3)', 'Due Soon (4-7)', 'On Track'], fill_value=0
    )

    colors = {
        'Overdue': '#ef4444',
        'Urgent (0-3)': '#f59e0b',
        'Due Soon (4-7)': '#3b82f6',
        'On Track': '#10b981'
    }

    fig = go.Figure(data=[go.Bar(
        x=counts.index,
        y=counts.values,
        marker_color=[colors.get(c, '#6b7280') for c in counts.index],
        text=counts.values,
        textposition='auto',
        textfont=dict(size=13, color='white', family='Inter'),
        hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
    )])

    fig.update_layout(
        title=dict(text="Samples by Urgency", font=dict(size=14, weight='bold')),
        xaxis=dict(title="", tickfont=dict(size=11)),
        yaxis=dict(title="Count", title_font=dict(size=12), tickfont=dict(size=11)),
        height=280,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# Styling Functions
def style_status(val):
    val = str(val).lower().strip()
    if val == 'ok':
        return 'background-color: #d1fae5; color: #065f46; font-weight: 600; border-radius: 20px; padding: 2px 8px; display: inline-block;'
    elif val == 'pending':
        return 'background-color: #fed7aa; color: #92400e; font-weight: 600; border-radius: 20px; padding: 2px 8px; display: inline-block;'
    elif val == 'ng':
        return 'background-color: #fee2e2; color: #991b1b; font-weight: 600; border-radius: 20px; padding: 2px 8px; display: inline-block;'
    return ''

def style_days(val):
    if val != '-':
        try:
            days = int(str(val).replace('d', ''))
            if days < 0:
                return 'background-color: #fee2e2; color: #991b1b; font-weight: 600;'
            elif days <= 3:
                return 'background-color: #fed7aa; color: #92400e; font-weight: 600;'
        except:
            pass
    return ''

# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────
def main():
    st.markdown('<div class="main-header"><h1 style="color:white;">🏭 Golden Sample Revalidation Tracker</h1></div>', unsafe_allow_html=True)
   
    with st.spinner("Loading latest data..."):
        df_raw = fetch_data()
        df = process_data(df_raw)
   
    if df is None or df.empty:
        st.error("No valid data available. Please check the data source.")
        return

    st.session_state.df = df

    # Auto email
    auto_sent, auto_msg = check_and_send_auto_email(df)
    if auto_sent:
        st.toast(auto_msg, icon="✅")

    # Metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    total = len(df)
    ok_count = len(df[df['Staus'].str.lower() == 'ok'])
    pending_count = len(df[df['Staus'].str.lower() == 'pending'])
    ng_count = len(df[df['Staus'].str.lower() == 'ng'])
    urgent_count = len(get_due_records(df))
    overdue_count = len(get_overdue_records(df))

    metric_style = """
    <div style="background:white;padding:12px 8px;border-radius:12px;
                box-shadow:0 2px 8px rgba(0,0,0,0.08);text-align:center;">
        <div style="font-size:1.8rem;font-weight:700;margin-bottom:4px;">{}</div>
        <div style="font-size:0.75rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">{}</div>
    </div>
    """

    st.caption(f"**Last Updated:** {datetime.now().strftime('%d-%m-%Y %I:%M %p')}")

    with col1: st.markdown(metric_style.format(total, "TOTAL"), unsafe_allow_html=True)
    with col2: st.markdown(metric_style.format(ok_count, "✅ OK"), unsafe_allow_html=True)
    with col3: st.markdown(metric_style.format(pending_count, "⏳ PENDING"), unsafe_allow_html=True)
    with col4: st.markdown(metric_style.format(ng_count, "❌ NG"), unsafe_allow_html=True)
    with col5: st.markdown(metric_style.format(urgent_count, "🔴 URGENT"), unsafe_allow_html=True)
    with col6: st.markdown(metric_style.format(overdue_count, "⚠️ OVERDUE"), unsafe_allow_html=True)

    # Charts
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.plotly_chart(create_status_chart(df), use_container_width=True, config={'displayModeBar': False})
    with col_chart2:
        st.plotly_chart(create_urgency_chart(df), use_container_width=True, config={'displayModeBar': False})

    st.markdown("### 📋 Sample Details")

    # Filters
    c1, c2, c3, c4, c5, c6 = st.columns([1.4, 1.4, 2, 1, 1, 1])

    with c1:
        status_filter = st.selectbox("Status", ['All', 'Ok', 'Pending', 'Ng'], index=0, key="status_filter")
    with c2:
        urgency_filter = st.selectbox("Urgency", ['All', 'Overdue', 'Urgent', 'Due Soon', 'On Track'], key="urgency_filter")
    with c3:
        search_model = st.text_input("🔍 Search Model", "", placeholder="Enter model name...", key="search_model")

    with c4:
        if st.button("📥 Export CSV", use_container_width=True):
            csv = df.to_csv(index=False)
            st.download_button("Download Report", csv, f"golden_sample_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")
    with c5:
        if st.button("📧 Send Alert", use_container_width=True, type="primary"):
            with st.spinner("Sending email..."):
                success, msg = send_email_alert(df, st.session_state.primary_recipients, st.session_state.cc_recipients)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
    with c6:
        if st.button("Clear Filters"):
            st.session_state.status_filter = 'All'
            st.session_state.urgency_filter = 'All'
            st.rerun()

    # Filtering
    filtered_df = df.copy()

    if status_filter != 'All':
        filtered_df = filtered_df[filtered_df['Staus'] == status_filter]

    if urgency_filter != 'All':
        if urgency_filter == 'Overdue':
            filtered_df = filtered_df[filtered_df['Days Left'] < 0]
        elif urgency_filter == 'Urgent':
            filtered_df = filtered_df[(filtered_df['Days Left'] <= 3) & (filtered_df['Days Left'] >= 0)]
        elif urgency_filter == 'Due Soon':
            filtered_df = filtered_df[(filtered_df['Days Left'] <= 7) & (filtered_df['Days Left'] > 3)]
        elif urgency_filter == 'On Track':
            filtered_df = filtered_df[filtered_df['Days Left'] > 7]

    if search_model:
        filtered_df = filtered_df[filtered_df['Model'].str.contains(search_model, case=False, na=False)]

    # Display Table
    if filtered_df.empty:
        st.warning("🔍 No records found matching your filters.")
    else:
        display_df = filtered_df[['Model', 'Validation Date Display', 'Revalidation Due Display',
                                 'Days Left', 'Staus', 'Incharge', 'Alert Status']].copy()
        display_df = display_df.fillna('-')
        
        def format_days(row):
            if str(row['Staus']).lower() == 'ng':
                return '-'
            try:
                d = float(row['Days Left'])
                return f"{int(d)}d" if not pd.isna(d) else '-'
            except:
                return '-'
        
        display_df['Days Left'] = display_df.apply(format_days, axis=1)
        
        def highlight_row(row):
            styles = [''] * len(row)
            status = str(row['Staus']).lower()
            days_val = str(row['Days Left'])
            
            if status == 'ng' or (days_val != '-' and '-' in days_val and 'overdue' in days_val.lower()):
                styles = ['background-color: #fee2e2; color: #991b1b'] * len(row)
            elif days_val != '-' and 'd' in days_val:
                try:
                    days = int(days_val.replace('d',''))
                    if days < 0:
                        styles = ['background-color: #fee2e2'] * len(row)
                    elif days <= 3:
                        styles = ['background-color: #fef3c7'] * len(row)
                except:
                    pass
            return styles

        styled_df = (display_df.style
                     .apply(highlight_row, axis=1)
                     .applymap(style_status, subset=['Staus'])
                     .set_properties(**{'font-size': '14px'}))
        
        st.dataframe(styled_df, use_container_width=True, height=500, hide_index=True)

    # Settings
    with st.expander("⚙️ Email & Settings"):
        col_set1, col_set2 = st.columns(2)
        with col_set1:
            # Multi-line input for primary recipients
            primary_text = st.text_area("Primary Recipients (one per line)", 
                                       "\n".join(st.session_state.primary_recipients), height=100)
            if st.button("Save Primary"):
                st.session_state.primary_recipients = [e.strip() for e in primary_text.splitlines() if e.strip()]
                st.success("Primary recipients updated!")
        with col_set2:
            cc_text = st.text_area("CC Recipients (one per line)", 
                                  "\n".join(st.session_state.cc_recipients), height=100)
            if st.button("Save CC"):
                st.session_state.cc_recipients = [e.strip() for e in cc_text.splitlines() if e.strip()]
                st.success("CC recipients updated!")

if __name__ == "__main__":
    main()
