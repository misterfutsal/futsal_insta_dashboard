import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- Konfiguration ---
INSTA_SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"
ZUSCHAUER_SHEET_ID = "14puepYtteWGPD1Qv89gCpZijPm5Yrgr8glQnGBh3PXM"

st.set_page_config(page_title="Futsal Statistik Dashboard", layout="wide")

# --- SESSION STATE INITIALISIEREN (Das Gedächtnis für Klicks) ---
if 'clicked_club' not in st.session_state:
    st.session_state.clicked_club = None

# --- STYLING ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; padding-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { height: 30px; background-color: #FFFFFF; border: 2px solid #D3D3D3; border-radius: 0px; padding: 0px 10px; color: #31333F; font-weight: 100; transition: all 0.3s ease; }
    .stTabs [data-baseweb="tab"]:hover { border-color: #0047AB; background-color: #E8F0FE; color: #0047AB; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #0047AB; border: 2px solid #0047AB; color: #FFFFFF !important; box-shadow: 0px 4px 6px rgba(0, 71, 171, 0.3); }
    .stTabs [data-baseweb="tab"][aria-selected="true"] p { color: #FFFFFF !important; font-size: 18px; font-weight: bold; }
    div[data-baseweb="select"] > div { background-color: #FDFDFD; border: 2px solid #0047AB; border-radius: 8px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); }
    div[data-baseweb="select"] * { color: #0047AB !important;}
    .stSelectbox label p { font-size: 18px !important; color: #0047AB !important; font-weight: 800 !important; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- DATEN LADEN FUNKTION ---
@st.cache_data(ttl=3600)
def load_data(sheet_id, secret_key):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets[secret_key]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df.columns = [str(c).strip().upper() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")
        return pd.DataFrame()

# ==========================================
# 1. DATEN-VORBEREITUNG (INSTAGRAM)
# ==========================================
df_insta = load_data(INSTA_SHEET_ID, "gcp_service_account")

if not df_insta.empty:
    if 'DATE' in df_insta.columns: 
        df_insta['DATE'] = pd.to_datetime(df_insta['DATE']).dt.date
    df_insta['FOLLOWER'] = pd.to_numeric(df_insta['FOLLOWER'], errors='coerce').fillna(0)
    df_insta = df_insta.sort_values(by=['CLUB_NAME', 'DATE']).drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
    
    df_latest = df_insta.sort_values('DATE').groupby('CLUB_NAME').last().reset_index().sort_values(by='FOLLOWER', ascending=False)
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    akt_datum = df_insta['DATE'].max().strftime('%d.%m.%Y')
else:
    summe_follower, akt_datum = "0", "-"

# Header-Bereich
try: 
    st.image("banner_statistik_dashboard.png", width=450)
except: 
    st.title("⚽ Futsal Dashboard") 

st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")
st.divider()

# ==========================================
# 2. REITER / TABS
# ==========================================
tab_insta, tab_zuschauer = st.tabs(["📸 Instagram Follower", "🏟️ Bundesliga Zuschauer"])

# --- TAB 1: INSTAGRAM ---
with tab_insta:
    if not df_insta.empty:
        df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        df_latest_display = df_latest.copy()
        df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
        df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_latest_display['STAND'] = df_latest_display['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))
        
        row1_col1, row1_col2 = st.columns(2, gap="medium")
        h_tables = 2150
        
        with row1_col1:
            st.subheader("# Aktuelles Ranking")
            st.markdown("👇 :yellow[Hier Vereine für Detailanalyse selektieren]")
            selection = st.dataframe(
                df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND']], 
                column_config={
                    "RANG": st.column_config.TextColumn("Rang"),
                    "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"),
                    "FOLLOWER": st.column_config.TextColumn("Follower"),
                    "STAND": st.column_config.TextColumn("Stand")
                },
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                use_container_width=True,
                height=h_tables
            )
            
        with row1_col2:
            st.subheader("🔍 Detailanalyse")
            
            # --- LOGIK FÜR DIE AUSWAHL ---
            sel_clubs = []
            
            # Prio 1: Wenn unten im Chart geklickt wurde
            if st.session_state.clicked_club:
                sel_clubs = [st.session_state.clicked_club]
                # Resetten, damit man danach wieder die Tabelle nutzen kann
                st.session_state.clicked_club = None 
                
            # Prio 2: Wenn in der Tabelle ausgewählt wurde
            elif selection and selection.selection.rows:
                sel_clubs = df_latest.iloc[selection.selection.rows]['CLUB_NAME'].tolist()
            
            # Chart zeichnen
            if sel_clubs:
                plot_data = df_insta[df_insta['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                fig_detail = px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', title="Vergleich der Vereine", markers=True)
                st.plotly_
