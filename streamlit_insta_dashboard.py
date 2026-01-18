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
    st.title("Mister Futsal - Instagram Dashboard")

    # --- DATEN-VORBEREITUNG ---
    
    # 1. Ranking: Letzter Stand pro Club
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    df_latest['STAND'] = pd.to_datetime(df_latest['DATE']).dt.strftime('%d.%m.%Y')
    
    df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False).copy()
    df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))

    # 2. Trend (4 Wochen Vergleich)
    latest_date_global = df['DATE'].max()
    target_date_4w = latest_date_global - timedelta(weeks=4)
    available_dates = sorted(df['DATE'].unique())
    closest_old_date = min(available_dates, key=lambda x: abs(x - target_date_4w))
    
    df_now = df_latest[['CLUB_NAME', 'FOLLOWER', 'URL']]
    df_then = df[df['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
    
    df_trend = pd.merge(df_now, df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
    df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
    
    df_trend_top10 = df_trend.sort_values(by='Zuwachs', ascending=False).head(10).copy()
    df_trend_top10.insert(0, 'RANG', range(1, len(df_trend_top10) + 1))

    # --- OBERER BEREICH ---
    col_rank, col_trend = st.columns(2, gap="medium")
    fixed_height_10_rows = 35 * 10 + 38 

    # Tabellen-Design: Wir nutzen TextColumn für Linksbündigkeit
    with col_rank:
        st.subheader("🏆 Aktuelles Ranking")
        st.caption("Alle Spalten sind linksbündig ausgerichtet")
        
        selection = st.dataframe(
            df_latest[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND']],
            column_config={
                "RANG": st.column_config.TextColumn("Rang", width="small"),
                "CLUB_NAME": st.column_config.TextColumn("Verein"),
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/(.*?)/"),
                "FOLLOWER": st.column_config.TextColumn("Follower"),
                "STAND": st.column_config.TextColumn("Stand")
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
        
        st.dataframe(
            df_trend_top10[['RANG', 'CLUB_NAME', 'URL', 'Zuwachs']],
            column_config={
                "RANG": st.column_config.TextColumn("Rang", width="small"),
                "CLUB_NAME": st.column_config.TextColumn("Verein"),
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/(.*?)/"),
                "Zuwachs": st.column_config.TextColumn("Zuwachs")
            },
            use_container_width=True,
            height=fixed_height_10_rows,
            hide_index=True
        )

    st.divider()

    # --- UNTERER BEREICH: INDIVIDUALANALYSE ---
    st.subheader("🔍 Detailansicht täglich für ausgewählten Club")
    
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
        fig_abs.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
        fig_abs.update_yaxes(title_text="Anzahl Follower")
        fig_abs.update_layout(hovermode="x unified")
        
        st.plotly_chart(fig_abs, use_container_width=True)
    else:
        st.info("💡 Klicke oben links in die Ranking-Tabelle, um Details zu sehen.")

except Exception as e:
    st.error(f"Fehler im Dashboard: {e}")

