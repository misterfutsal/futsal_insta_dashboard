import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- Konfiguration ---
SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"

# 1. Stadion-Modus: Wir machen das Dashboard breit und geben ihm einen coolen Namen
st.set_page_config(page_title="Futsal Pro-Stats", layout="wide", page_icon="⚽")

# (Hier bleibt deine load_data_from_sheets Funktion wie sie war...)
@st.cache_data(ttl=3600)
def load_data_from_sheets():
    # ... (Dein Code) ...
    return df

try:
    df = load_data_from_sheets()
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    
    # --- DESIGN-UPDATE ---
    
    # Titel mit Stadion-Gefühl
    st.title("⚽ Mister Futsal | Arena-Analytics")
    
    # 2. Sammelkarten-Look (Metrics): Wichtige Zahlen ganz oben in Boxen
    col_m1, col_m2, col_m3 = st.columns(3)
    
    total_folls = int(df_latest['FOLLOWER'].sum())
    top_club = df_latest.iloc[0]['CLUB_NAME']
    
    with col_m1:
        st.metric("Gesamt-Follower 👥", f"{total_folls:,}".replace(",", "."))
    with col_m2:
        st.metric("Top Verein 🏆", top_club)
    with col_m3:
        st.metric("Update 📅", df['DATE'].max().strftime('%d.%m.%Y'))

    st.divider()

    # Layout mit Spalten
    col_links, col_rechts = st.columns([1, 1], gap="large")

    with col_links:
        st.subheader("📊 Die Bestenliste")
        # Schicke Tabelle
        st.dataframe(
            df_latest[['CLUB_NAME', 'FOLLOWER']].sort_values(by="FOLLOWER", ascending=False),
            use_container_width=True,
            height=400
        )

    with col_rechts:
        st.subheader("📈 Wachstum im Stadion")
        # Eine leuchtende Linie für die Grafik
        df_total = df.groupby('DATE')['FOLLOWER'].sum().reset_index()
        fig = px.line(df_total, x='DATE', y='FOLLOWER', 
                     template="plotly_dark", # Dunkles Design
                     color_discrete_sequence=['#FFB200']) # Goldene Linie
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Oh weh, ein kleiner Fehler: {e}")
