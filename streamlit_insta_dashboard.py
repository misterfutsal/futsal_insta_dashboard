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

    # --- Daten vorbereiten ---
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
    df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
    df_latest['STAND_STR'] = pd.to_datetime(df_latest['DATE']).dt.strftime('%d.%m.%Y')

    akt_datum = df['DATE'].max().strftime('%d.%m.%Y')
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    
    st.markdown(f"#### Aktuelle Follower aller Futsal-Clubs (Stand {akt_datum}): :yellow[**{summe_follower}**]")
    st.divider()

    # --- OBERE REIHE: Ranking & Detailanalyse ---
    row1_col1, row1_col2 = st.columns(2, gap="medium")
    h_tables = 400

    with row1_col1:
        st.subheader("🏆 Aktuelles Ranking")
        selection = st.dataframe(
            df_latest[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND_STR']],
            column_config={
                "RANG": st.column_config.NumberColumn("Rang", width="small"),
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"),
                "FOLLOWER": st.column_config.NumberColumn("Follower", format="%d")
            },
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            height=h_tables
        )

    with row1_col2:
        st.subheader("🔍 Detailanalyse")
        if selection and selection.selection.rows:
            sel_idx = selection.selection.rows[0]
            sel_club = df_latest.iloc[sel_idx]['CLUB_NAME']
            club_data = df[df['CLUB_NAME'] == sel_club].sort_values('DATE')
            fig_detail = px.line(club_data, x='DATE', y='FOLLOWER', title=f"Verlauf: {sel_club}", markers=True, color_discrete_sequence=['#00CC96'])
            st.plotly_chart(fig_detail, use_container_width=True)
        else:
            st.info("💡 Klicke links auf einen Verein für Details.")

    st.divider()

    # --- UNTERE REIHE: Trends & Gesamtverlauf ---
    row2_col1, row2_col2 = st.columns(2, gap="medium")

    with row2_col1:
        st.subheader("📈 Veränderung seit dem 15.01.2026")
        
        # Trend-Berechnung
        latest_date_global = df['DATE'].max()
        target_date_4w = latest_date_global - timedelta(weeks=4)
        available_dates = sorted(df['DATE'].unique())
        closest_old_date = min(available_dates, key=lambda x: abs(x - target_date_4w))
        
        df_then = df[df['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
        df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
        df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
        
        # Sortiert von Max nach Min und zeigt ALLE Clubs
        df_trend_all = df_trend.sort_values(by='Zuwachs', ascending=False).copy()
        df_trend_all.insert(0, 'RANG', range(1, len(df_trend_all) + 1))

        st.dataframe(
            df_trend_all[['RANG', 'CLUB_NAME', 'Zuwachs']],
            column_config={
                "RANG": st.column_config.NumberColumn("Rang", width="small"),
                "Zuwachs": st.column_config.NumberColumn("Zuwachs", format="+%d")
            },
            hide_index=True,
            use_container_width=True,
            height=h_tables # Macht die Liste scrollbar
        )

    with row2_col2:
        st.subheader("🌐 Gesamtentwicklung")
        df_total_history = df.groupby('DATE')['FOLLOWER'].sum().reset_index()
        fig_total = px.line(df_total_history, x='DATE', y='FOLLOWER', title="Summe aller Follower", markers=True, color_discrete_sequence=['#FFB200'])
        st.plotly_chart(fig_total, use_container_width=True)

except Exception as e:
    st.error(f"Fehler: {e}")


