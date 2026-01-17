import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- Konfiguration ---
CREDENTIALS_FILE = r"C:\Users\Daniel\Dropbox\Mister Futsal\User-Auswertung\futsal-instagram-stats-credentioals.json"
SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"

st.set_page_config(page_title="Futsal Insta-Analytics", layout="wide")

# @st.cache_data(ttl=3600)
# def load_data_from_sheets():
#     scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
#     creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)

@st.cache_data(ttl=3600)
def load_data_from_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    client = gspread.authorize(creds)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Spaltennamen normalisieren
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    if 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE']).dt.date
    
    df['FOLLOWER'] = pd.to_numeric(df['FOLLOWER'], errors='coerce').fillna(0)
    df = df.sort_values(by=['CLUB_NAME', 'DATE'])
    df = df.drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
    
    return df

try:
    df = load_data_from_sheets()
    latest_date = df['DATE'].max()

    st.title("⚽ Futsal Instagram Dashboard")

    # --- DATEN-VORBEREITUNG ---
    # 1. Ranking
    df_latest = df[df['DATE'] == latest_date].sort_values(by='FOLLOWER', ascending=False).copy()
    df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))

    # 2. Trend (4 Wochen Fix)
    target_date_4w = latest_date - timedelta(weeks=4)
    available_dates = sorted(df['DATE'].unique())
    closest_old_date = min(available_dates, key=lambda x: abs(x - target_date_4w))
    
    df_now = df[df['DATE'] == latest_date][['CLUB_NAME', 'FOLLOWER', 'URL']]
    df_then = df[df['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
    
    df_trend = pd.merge(df_now, df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
    df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
    # Nur die Top 10 für die Trend-Kachel
    df_trend_top10 = df_trend.sort_values(by='Zuwachs', ascending=False).head(10).copy()
    df_trend_top10.insert(0, 'RANG', range(1, 11))

    # --- OBERER BEREICH: ZWEI SPALTEN ---
    col_rank, col_trend = st.columns(2, gap="medium")

    # Berechnung der Höhe für genau 10 Zeilen (ca. 35px pro Zeile + Header)
    fixed_height_10_rows = 35 * 10 + 38 

    with col_rank:
        st.subheader("🏆 Aktuelles Ranking")
        st.caption(f"Stand: {latest_date.strftime('%d.%m.%Y')} (10 Zeilen sichtbar, Rest scrollbar)")
        
        # Ranking-Tabelle: Feste Höhe erzwingt Scrollen nach 10 Zeilen
        selection = st.dataframe(
            df_latest[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER']],
            column_config={
                "RANG": st.column_config.NumberColumn("Rang", width="small"),
                "CLUB_NAME": "Verein",
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/(.*?)/"),
                "FOLLOWER": st.column_config.NumberColumn("Follower", format="%d")
            },
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            height=fixed_height_10_rows, 
            hide_index=True
        )

    with col_trend:
        st.subheader("📈 Top 10 Trends (4 Wochen)")
        st.caption(f"Vergleich mit {closest_old_date.strftime('%d.%m.%Y')}")
        
        # Trend-Tabelle: Zeigt nur Top 10, kein Scrollen nötig
        st.dataframe(
            df_trend_top10[['RANG', 'CLUB_NAME', 'URL', 'Zuwachs']],
            column_config={
                "RANG": st.column_config.NumberColumn("Rang", width="small"),
                "CLUB_NAME": "Verein",
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/(.*?)/"),
                "Zuwachs": st.column_config.NumberColumn("Zuwachs", format="+%d")
            },
            use_container_width=True,
            height=fixed_height_10_rows, # Gleiche Höhe wie links für Symmetrie
            hide_index=True
        )

    st.divider()

    # --- UNTERER BEREICH: INDIVIDUALANALYSE (VOLLE BREITE) ---
    st.subheader("🔍 Individualanalyse")
    
    selected_club = None
    if selection and selection.selection.rows:
        selected_index = selection.selection.rows[0]
        selected_club = df_latest.iloc[selected_index]['CLUB_NAME']
    
    if selected_club:
        st.info(f"Analysiere Verlauf von: **{selected_club}**")
        club_data = df[df['CLUB_NAME'] == selected_club].sort_values(by='DATE')

        fig_abs = px.line(
            club_data, x='DATE', y='FOLLOWER', 
            title=f"Follower-Gesamtverlauf",
            markers=True,
            color_discrete_sequence=['#00CC96']
        )
        # Achsen-Design optimieren
        fig_abs.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
        fig_abs.update_yaxes(title_text="Anzahl Follower")
        fig_abs.update_layout(hovermode="x unified")
        
        st.plotly_chart(fig_abs, use_container_width=True)
    else:
        st.info("💡 Klicke oben links in der Ranking-Tabelle auf eine Zeile, um den Verlauf hier anzuzeigen.")

except Exception as e:

    st.error(f"Fehler im Dashboard: {e}")

