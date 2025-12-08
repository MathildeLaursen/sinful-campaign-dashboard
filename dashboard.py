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

# --- LOGIN LOGIK (ROBUST VERSION) ---
def check_password():
    # Initialiser cookie manageren
    cookie_manager = stx.CookieManager(key="cookie_manager")
    
    # Hent cookie værdi
    cookie_val = cookie_manager.get(cookie="sinful_auth")

    # 1. Tjek: Er vi allerede logget ind i denne session? (Hurtigst)
    if st.session_state.get("authenticated", False):
        return True

    # 2. Tjek: Har brugeren en gyldig cookie fra sidst?
    if cookie_val == "true":
        st.session_state["authenticated"] = True
        st.rerun() # Genstart for at opdatere siden med det samme
        return True

    # 3. Vis Login Formular
    st.markdown("### 🔒 Adgang påkrævet")
    
    with st.form("login_form"):
        password_input = st.text_input("Indtast kodeord:", type="password")
        submit_button = st.form_submit_button("Log Ind")

        if submit_button:
            if password_input == st.secrets["PASSWORD"]:
                # A. Log brugeren ind med det samme i sessionen
                st.session_state["authenticated"] = True
                
                # B. Sæt cookie til at huske brugeren i 24 timer
                expires = datetime.datetime.now() + datetime.timedelta(days=1)
                cookie_manager.set("sinful_auth", "true", expires_at=expires)
                
                # C. VIGTIGT: Vent lidt så browseren når at gemme cookien
                st.success("Logger ind...")
                time.sleep(1) 
                
                # D. Genstart appen
                st.rerun()
            else:
                st.error("😕 Forkert kodeord")
    
    return False

# Stop koden her, hvis man ikke er logget ind
if not check_password():
    st.stop()

# --- HERUNDER ER DASHBOARDET (KUN SYNLIGT NÅR LOGGET IND) ---

# Log ud knap i menuen
with st.sidebar:
    st.write("Logget ind ✅")
    if st.button("Log Ud"):
        # Slet cookie og session state
        cookie_manager = stx.CookieManager(key="logout_manager")
        cookie_manager.delete("sinful_auth")
        st.session_state["authenticated"] = False
        st.rerun()

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
    except Exception as e:
        st.error(f"Kunne ikke genkende kolonnerne. Fejl: {e}")
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
    with st.spinner('Henter data...'):
        df = load_google_sheet_data()
    
    if df.empty:
        st.error("Kunne ikke hente data. Tjek Secrets.")
        st.stop()

    st.sidebar.header("🔍 Filtre")
    min_date = df['Date'].min()
    max_date = df['Date'].max()
    start_date, end_date = st.sidebar.date_input("Vælg periode", [min_date, max_date], min_value=min_date, max_value=max_date)
    
    all_campaigns = sorted(df['Campaign Name'].astype(str).unique())
    campaign_filter = st.sidebar.multiselect("Kampagne Navn", options=all_campaigns, default=all_campaigns)

    mask = (df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date)) & (df['Campaign Name'].astype(str).isin(campaign_filter))
    filtered_df = df.loc[mask]

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Emails Sendt", f"{filtered_df['Total_Received'].sum():,.0f}")
    kpi2.metric("Unikke Opens", f"{filtered_df['Unique_Opens'].sum():,.0f}")
    kpi3.metric("Gns. Open Rate", f"{filtered_df['Open Rate %'].mean():.1f}%")
    kpi4.metric("Gns. Click Rate", f"{filtered_df['Click Rate %'].mean():.2f}%")
    
    st.divider()

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
    st.error(f"Fejl: {e}")
