import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- Konfiguration ---
SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"

st.set_page_config(page_title="Futsal Insta-Analytics", layout="wide")

@st.cache_data(ttl=3600)
def load_data_from_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = [str(c).strip().upper() for c in df.columns]
    if 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE']).dt.date
    df['FOLLOWER'] = pd.to_numeric(df['FOLLOWER'], errors='coerce').fillna(0)
    df = df.sort_values(by=['CLUB_NAME', 'DATE'])
    df = df.drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
    return df

try:
    df = load_data_from_sheets()

    # --- DATEN VORBEREITEN ---
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
    df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
    
    df_latest_display = df_latest.copy()
    df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
    df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))

    akt_datum = df['DATE'].max().strftime('%d.%m.%Y')
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")

    # --- KOPFZEILE ---
    st.image("logo_instagram_dashboard.png", width=350)

    st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
    st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")
    st.divider()

    # --- OBERE REIHE ---
    row1_col1, row1_col2 = st.columns(2, gap="medium")
    h_tables = 2150

    with row1_col1:
        st.subheader("🏆 Aktuelles Ranking")
        st.markdown("**:yellow[👇 Wähle hier einen oder mehrere Vereine aus!]**")
        selection = st.dataframe(
            df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER']],
            column_config={
                "RANG": st.column_config.TextColumn("Rang"),
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"),
                "FOLLOWER": st.column_config.TextColumn("Follower")
            },
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row", # GEÄNDERT: Mehrere Zeilen erlaubt
            use_container_width=True,
            height=h_tables
        )
