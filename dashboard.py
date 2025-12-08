import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# --- SIDE OPSÆTNING ---
st.set_page_config(page_title="Sinful KPI Dashboard", layout="wide")

# --- SIKKERHED (KODEORD) ---
def check_password():
    """Returnerer True hvis brugeren har indtastet rigtigt kodeord."""
    def password_entered():
        if st.session_state["password"] == st.secrets["PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 Indtast kodeord for at se dashboardet:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 Indtast kodeord for at se dashboardet:", type="password", on_change=password_entered, key="password")
        st.error("😕 Forkert kodeord")
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- DASHBOARD LOGIK ---

st.title("📧 Live Dashboard: Email Marketing")

@st.cache_data(ttl=600)
def load_google_sheet_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Læs data
    try:
        df = conn.read(skiprows=1)
    except Exception:
        # Hvis den fejler her, er det oftest en netværksfejl eller rettigheder
        return pd.DataFrame()
    
    # RENSNING
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
    except Exception as e:
        st.error(f"Kunne ikke genkende kolonnerne i arket. Har strukturen ændret sig? Fejl: {e}")
        return pd.DataFrame()

    df['Date'] = pd.to_datetime(
        df['Send Year'].astype(str) + '-' + 
        df['Send Month'].astype(str) + '-' + 
        df['Send Day'].astype(str), 
        errors='coerce'
    )
    df = df.dropna(subset=['Date'])

    numeric_cols = ['Total_Received', 'Unique_Opens', 'Unique_Clicks', 'Unsubscribed']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '').str.replace('"', '').str.replace('.', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df['Open Rate %'] = df.apply(lambda x: (x['Unique_Opens'] / x['Total_Received'] * 100) if x['Total_Received'] > 0 else 0, axis=1)
    df['Click Rate %'] = df.apply(lambda x: (x['Unique_Clicks'] / x['Total_Received'] * 100) if x['Total_Received'] > 0 else 0, axis=1)
    
    return df

try:
    with st.spinner('Henter nyeste data fra Google...'):
        df = load_google_sheet_data()
    
    if df.empty:
        st.error("Kunne ikke hente data. Tjek at Google Sheet linket er korrekt i Secrets.")
        st.stop()

    st.sidebar.header("🔍 Filtre")
    min_date = df['Date'].min()
    max_date = df['Date'].max()
    start_date, end_date = st.sidebar.date_input("Vælg periode", [min_date, max_date], min_value=min_date, max_value=max_date)
    
    all_campaigns = sorted(df['Campaign Name'].astype(str).unique())
    campaign_filter = st.sidebar.multiselect("Kampagne Navn", options=all_campaigns, default=all_campaigns)

    mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date)) & (df['Campaign Name'].astype(str).isin(campaign_filter))
    filtered_df = df.loc[mask]

    # KPI'er
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Emails Sendt", f"{filtered_df['Total_Received'].sum():,.0f}")
    kpi2.metric("Unikke Opens", f"{filtered_df['Unique_Opens'].sum():,.0f}")
    kpi3.metric("Gns. Open Rate", f"{filtered_df['Open Rate %'].mean():.1f}%")
    kpi4.metric("Gns. Click Rate", f"{filtered_df['Click Rate %'].mean():.2f}%")
    
    st.divider()

    # Grafer
    col_graph1, col_graph2 = st.columns(2)
    with col_graph1:
        st.subheader("📈 Open Rate Udvikling")
        if not filtered_df.empty:
            fig_line = px.line(filtered_df.sort_values('Date'), x='Date', y='Open Rate %', hover_data=['Message'])
            fig_line.update_traces(line_color='#E74C3C')
            st.plotly_chart(fig_line, use_container_width=True)

    with col_graph2:
        st.subheader("🎯 Klik vs. Opens")
        if not filtered_df.empty:
            fig_scatter = px.scatter(filtered_df, x='Open Rate %', y='Click Rate %', size='Total_Received', color='Campaign Name', hover_name='Message')
            st.plotly_chart(fig_scatter, use_container_width=True)

    # Tabel
    st.subheader("🏆 Top Performers (Kliks)")
    if not filtered_df.empty:
        top_performers = filtered_df.sort_values(by='Unique_Clicks', ascending=False).head(10)
        st.dataframe(top_performers[['Date', 'Campaign Name', 'Message', 'Unique_Opens', 'Unique_Clicks', 'Open Rate %', 'Click Rate %']].style.format({
            'Unique_Opens': '{:,.0f}',
            'Unique_Clicks': '{:,.0f}',
            'Open Rate %': '{:.1f}%',
            'Click Rate %': '{:.2f}%'
        }), use_container_width=True)
    
    if st.button('🔄 Opdater Data'):
        st.cache_data.clear()
        st.rerun()

except Exception as e:
    st.error(f"Der opstod en uventet fejl: {e}")
