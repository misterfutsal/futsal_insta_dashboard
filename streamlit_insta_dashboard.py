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
    # Rang-Spalte erstellen
    df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
    df_latest['STAND_STR'] = pd.to_datetime(df_latest['DATE']).dt.strftime('%d.%m.%Y')

    # --- Die neue große Überschrift ---
    akt_datum = df['DATE'].max().strftime('%d.%m.%Y')
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    
    st.markdown(f"#### Aktuelle Anzahl von Instagram-Followern von deutschen Futsal-Club-Seiten (Stand {akt_datum}): **{summe_follower}**")
    st.divider()

    # Trend 4 Wochen
    latest_date_global = df['DATE'].max()
    target_date_4w = latest_date_global - timedelta(weeks=4)
    available_dates = sorted(df['DATE'].unique())
    closest_old_date = min(available_dates, key=lambda x: abs(x - target_date_4w))
    df_then = df[df['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
    df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER', 'URL']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
    df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
    df_trend_top10 = df_trend.sort_values(by='Zuwachs', ascending=False).head(10).copy()
    df_trend_top10.insert(0, 'RANG', range(1, len(df_trend_top10) + 1))

    # --- Tabellen-Anzeige ---
    col1, col2 = st.columns(2, gap="medium")
    h = 400

    with col1:
        st.subheader("🏆 Aktuelles Ranking")
        st.caption("👈 Auswahl für Detailanalyse (Kästchen anklicken)")
        selection = st.dataframe(
            df_latest[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND_STR']],
            column_config={
                "RANG": st.column_config.NumberColumn("Rang", width="small"),
                "CLUB_NAME": "Verein",
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"),
                "FOLLOWER": st.column_config.NumberColumn("Follower", format="%d"),
                "STAND_STR": "Stand"
            },
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            height=h
        )

    with col2:
        st.subheader("📈 Top 10 Trends (4 Wochen)")
        st.caption(f"Vergleich mit dem {closest_old_date.strftime('%d.%m.%Y')}")
        st.dataframe(
            df_trend_top10[['RANG', 'CLUB_NAME', 'Zuwachs']],
            column_config={
                "RANG": st.column_config.NumberColumn("Rang", width="small"),
                "Zuwachs": st.column_config.NumberColumn("Zuwachs", format="+%d")
            },
            hide_index=True,
            use_container_width=True,
            height=h
        )

    st.divider()

    # --- Diagramm ---
    st.subheader("🔍 Detailanalyse")
    if selection and selection.selection.rows:
        sel_idx = selection.selection.rows[0]
        sel_club = df_latest.iloc[sel_idx]['CLUB_NAME']
        st.info(f"Verlauf für: **{sel_club}**")
        club_data = df[df['CLUB_NAME'] == sel_club].sort_values('DATE')
        fig = px.line(club_data, x='DATE', y='FOLLOWER', markers=True, color_discrete_sequence=['#00CC96'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("💡 Klicke oben in der Ranking-Tabelle auf ein Kästchen!")

except Exception as e:
    st.error(f"Da hat sich ein Fehler versteckt: {e}")
