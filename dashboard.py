import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
import extra_streamlit_components as stx
import datetime
import time

# --- SIDE OPSÆTNING ---
st.set_page_config(page_title="Sinful KPI Dashboard", layout="wide")
st.title("📧 Live Dashboard: Email Marketing")

# --- COOKIE MANAGER (SKAL LIGGE UDENFOR FUNKTIONER) ---
# Vi initialiserer den her, så den altid er en del af appen
cookie_manager = stx.CookieManager(key="init_cookie_manager")

# --- LOGIN LOGIK ---
def check_password():
    # 1. Hent cookie værdi
    cookie_val = cookie_manager.get("sinful_auth")

    # 2. Tjek Session State (Hvis vi lige har logget ind i denne session)
    if st.session_state.get("authenticated", False):
        return True

    # 3. Tjek Cookie (Hvis vi kommer tilbage efter reload)
    if cookie_val == "true":
        st.session_state["authenticated"] = True
        return True

    # 4. Hvis ingen af delene: Vis Login Formular
    st.markdown("### 🔒 Adgang påkrævet")
    with st.form("login_form"):
        password_input = st.text_input("Indtast kodeord:", type="password")
        submit_button = st.form_submit_button("Log Ind")

        if submit_button:
            if password_input == st.secrets["PASSWORD"]:
                # A. Sæt session state straks
                st.session_state["authenticated"] = True
                
                # B. Sæt cookie til 30 dage
                expires = datetime.datetime.now() + datetime.timedelta(days=30)
                cookie_manager.set("sinful_auth", "true", expires_at=expires)
                
                st.success("Login godkendt! Opdaterer...")
                # C. Vigtigt: Vent så browseren når at gemme cookien før reload
                time.sleep(1)
                st.rerun()
            else:
                st.error("😕 Forkert kodeord")
    return False

# Stop alt her, hvis ikke logget ind
if not check_password():
    st.stop()

# --- SIDEBAR: LOG UD ---
with st.sidebar:
    if st.button("Log Ud"):
        # Slet cookie og nulstil session
        cookie_manager.delete("sinful_auth")
        st.session_state["authenticated"] = False
        time.sleep(1) # Vent på at sletningen registreres
        st.rerun()

# --- 2. DATA INDLÆSNING ---
@st.cache_data(ttl=600)
def load_google_sheet_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(skiprows=1)
    except Exception:
        return pd.DataFrame()
    
    try:
        rename_map = {
            df.columns[0]: 'Send Year',
            df.columns[1]: 'Send Month',
            df.columns[2]: 'Send Day',
            df.columns[3]: 'Send Time',
            df.columns[4]: 'Number',
            df.columns[5]: 'Campaign Name',
            df.columns[6]: 'Email Type',
            df.columns[7]: 'Message',
            df.columns[8]: 'Variant',
            df.columns[9]: 'Total_Received',
            df.columns[10]: 'Total_Opens_Raw',
            df.columns[11]: 'Unique_Opens',
            df.columns[12]: 'Total_Clicks_Raw',
            df.columns[13]: 'Unique_Clicks',
            df.columns[14]: 'Unsubscribed'
        }
        df = df.rename(columns=rename_map)
    except Exception:
        return pd.DataFrame()

    # Opret Dato
    df['Date'] = pd.to_datetime(
        df['Send Year'].astype(str) + '-' + 
        df['Send Month'].astype(str) + '-' + 
        df['Send Day'].astype(str), 
        errors='coerce'
    )
    df = df.dropna(subset=['Date'])

    # Rens tal
    numeric_cols = ['Total_Received', 'Unique_Opens', 'Unique_Clicks', 'Unsubscribed']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.replace('"', '').str.replace('.', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Beregn Rater
    df['Open Rate %'] = df.apply(lambda x: (x['Unique_Opens'] / x['Total_Received'] * 100) if x['Total_Received'] > 0 else 0, axis=1)
    df['Click Rate %'] = df.apply(lambda x: (x['Unique_Clicks'] / x['Total_Received'] * 100) if x['Total_Received'] > 0 else 0, axis=1)
    
    return df

# Hent data
try:
    with st.spinner('Henter data...'):
        df = load_google_sheet_data()
    if df.empty:
        st.error("Kunne ikke hente data.")
        st.stop()
except Exception as e:
    st.error(f"Fejl: {e}")
    st.stop()


# --- 3. DATO LOGIK ---
st.sidebar.header("📅 Periode")

date_options = [
    "Denne måned til dato",
    "Denne uge til dato",
    "Sidste 7 dage",
    "Sidste 30 dage",
    "Sidste måned",
    "Dette kvartal til dato",
    "Sidste kvartal",
    "Hele året (YTD)",
    "Brugerdefineret"
]

selected_range = st.sidebar.selectbox("Vælg tidsperiode", date_options)

today = datetime.date.today()

if selected_range == "Denne måned til dato":
    start_date = today.replace(day=1)
    end_date = today
elif selected_range == "Denne uge til dato":
    start_date = today - datetime.timedelta(days=today.weekday())
    end_date = today
elif selected_range == "Sidste 7 dage":
    start_date = today - datetime.timedelta(days=7)
    end_date = today
elif selected_range == "Sidste 30 dage":
    start_date = today - datetime.timedelta(days=30)
    end_date = today
elif selected_range == "Sidste måned":
    first_of_this_month = today.replace(day=1)
    end_date = first_of_this_month - datetime.timedelta(days=1)
    start_date = end_date.replace(day=1)
elif selected_range == "Dette kvartal til dato":
    current_q_start_month = 3 * ((today.month - 1) // 3) + 1
    start_date = today.replace(month=current_q_start_month, day=1)
    end_date = today
elif selected_range == "Sidste kvartal":
    current_q_start_month = 3 * ((today.month - 1) // 3) + 1
    curr_q_start = today.replace(month=current_q_start_month, day=1)
    end_date = curr_q_start - datetime.timedelta(days=1)
    prev_q_start_month = 3 * ((end_date.month - 1) // 3) + 1
    start_date = end_date.replace(month=prev_q_start_month, day=1)
elif selected_range == "Hele året (YTD)":
    start_date = today.replace(month=1, day=1)
    end_date = today
else: # Brugerdefineret
    start_date = st.sidebar.date_input("Start dato", df['Date'].min())
    end_date = st.sidebar.date_input("Slut dato", df['Date'].max())

# Beregn forrige periode
delta = end_date - start_date
prev_end_date = start_date - datetime.timedelta(days=1)
prev_start_date = prev_end_date - delta

# --- 4. AVANCEREDE FILTRE ---
st.sidebar.divider()
st.sidebar.header("🔍 Filtre")

all_numbers = sorted(df['Number'].astype(str).unique())
all_emails = sorted(df['Email Type'].astype(str).unique())
all_messages = sorted(df['Message'].astype(str).unique())
all_variants = sorted(df['Variant'].astype(str).unique())
all_campaigns = sorted(df['Campaign Name'].astype(str).unique())

sel_campaigns = st.sidebar.multiselect("Kampagne Navn", all_campaigns, default=[])
sel_numbers = st.sidebar.multiselect("Number (ID)", all_numbers, default=[])
sel_emails = st.sidebar.multiselect("Email Type", all_emails, default=[])
sel_messages = st.sidebar.multiselect("Message", all_messages, default=[])
sel_variants = st.sidebar.multiselect("Variant (A/B)", all_variants, default=[])

# --- 5. FILTRERING AF DATA ---
def filter_data(dataset, start, end):
    mask = (dataset['Date'] >= pd.to_datetime(start)) & (dataset['Date'] <= pd.to_datetime(end))
    temp_df = dataset.loc[mask]
    
    if sel_campaigns:
        temp_df = temp_df[temp_df['Campaign Name'].astype(str).isin(sel_campaigns)]
    if sel_numbers:
        temp_df = temp_df[temp_df['Number'].astype(str).isin(sel_numbers)]
    if sel_emails:
        temp_df = temp_df[temp_df['Email Type'].astype(str).isin(sel_emails)]
    if sel_messages:
        temp_df = temp_df[temp_df['Message'].astype(str).isin(sel_messages)]
    if sel_variants:
        temp_df = temp_df[temp_df['Variant'].astype(str).isin(sel_variants)]
        
    return temp_df

current_df = filter_data(df, start_date, end_date)
prev_df = filter_data(df, prev_start_date, prev_end_date)

# --- 6. KPI KORT ---
st.subheader(f"Overblik: {start_date} - {end_date}")
if selected_range != "Brugerdefineret":
    st.caption(f"Sammenlignet med forrige periode: {prev_start_date} - {prev_end_date}")

col1, col2, col3, col4 = st.columns(4)

def show_metric(col, label, current_val, prev_val, format_str, is_percent=False):
    delta = 0
    if prev_val > 0:
        delta = current_val - prev_val
    
    if is_percent:
        val_fmt = f"{current_val:.1f}%"
        delta_fmt = f"{delta:.1f}%"
    else:
        val_fmt = f"{current_val:,.0f}"
        delta_fmt = f"{delta:,.0f}"

    col.metric(label, val_fmt, delta=delta_fmt)

cur_sent = current_df['Total_Received'].sum()
prev_sent = prev_df['Total_Received'].sum()

cur_opens = current_df['Unique_Opens'].sum()
prev_opens = prev_df['Unique_Opens'].sum()

cur_or = current_df['Open Rate %'].mean() if not current_df.empty else 0
prev_or = prev_df['Open Rate %'].mean() if not prev_df.empty else 0

cur_cr = current_df['Click Rate %'].mean() if not current_df.empty else 0
prev_cr = prev_df['Click Rate %'].mean() if not prev_df.empty else 0

show_metric(col1, "Emails Sendt", cur_sent, prev_sent, "{:,.0f}")
show_metric(col2, "Unikke Opens", cur_opens, prev_opens, "{:,.0f}")
show_metric(col3, "Gns. Open Rate", cur_or, prev_or, "{:.1f}%", is_percent=True)
show_metric(col4, "Gns. Click Rate", cur_cr, prev_cr, "{:.2f}%", is_percent=True)

st.divider()

# --- 7. GRAFER ---
col_graph1, col_graph2 = st.columns(2)

with col_graph1:
    st.subheader("📈 Udvikling over tid")
    if not current_df.empty:
        graph_df = current_df.sort_values('Date')
        fig_line = px.line(graph_df, x='Date', y='Open Rate %', 
                           hover_data=['Message', 'Campaign Name'], 
                           markers=True)
        fig_line.update_traces(line_color='#E74C3C')
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("Ingen data i valgte periode.")

with col_graph2:
    st.subheader("🎯 Klik vs. Opens (Matrix)")
    if not current_df.empty:
        fig_scatter = px.scatter(
            current_df, 
            x='Open Rate %', 
            y='Click Rate %', 
            size='Total_Received', 
            color='Campaign Name', 
            hover_name='Message'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# --- 8. DATA TABEL ---
st.subheader("📋 Detaljeret Data")

if not current_df.empty:
    display_df = current_df.copy()
    display_df['Date'] = display_df['Date'].dt.date
    
    cols_to_show = [
        'Date', 'Number', 'Campaign Name', 'Email Type', 'Message', 'Variant',
        'Total_Received', 'Unique_Opens', 'Unique_Clicks', 'Open Rate %', 'Click Rate %'
    ]
    
    st.dataframe(
        display_df[cols_to_show].sort_values(by='Date', ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Open Rate %": st.column_config.NumberColumn(format="%.1f%%"),
            "Click Rate %": st.column_config.NumberColumn(format="%.2f%%"),
            "Total_Received": st.column_config.NumberColumn(format="%d"),
            "Unique_Opens": st.column_config.NumberColumn(format="%d"),
            "Unique_Clicks": st.column_config.NumberColumn(format="%d"),
        }
    )
else:
    st.warning("Ingen data at vise for de valgte filtre.")

if st.button('🔄 Opdater Data'):
    st.cache_data.clear()
    st.rerun()
