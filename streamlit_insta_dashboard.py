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
    # col_logo, col_titel = st.columns([1])
    # with col_logo:
    #     st.image("logo_instagram_dashboard.png", width=250)
    # with col_titel:
    #     st.title("Mister Futsal - Instagram Dashboard")

    st.image("logo_instagram_dashboard.png", width=350)

    st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
    st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")
    st.divider()

    # --- OBERE REIHE ---
    row1_col1, row1_col2 = st.columns(2, gap="medium")
    h_tables = 2150

    with row1_col1:
        st.subheader("🏆 Aktuelles Ranking")
        selection = st.dataframe(
            df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER']],
            column_config={
                "RANG": st.column_config.TextColumn("Rang"),
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"),
                "FOLLOWER": st.column_config.TextColumn("Follower")
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
            # Achse sauber machen:
            fig_detail.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
            st.plotly_chart(fig_detail, use_container_width=True, config={'staticPlot': True})
        else:
            st.info("💡 Klicke links auf einen Verein für Details.")

    st.divider()

    # --- UNTERE REIHE ---
    row2_col1, row2_col2 = st.columns(2, gap="medium")

    with row2_col1:
        st.subheader("📈 Wachstumstrends")
        latest_date_global = df['DATE'].max()
        target_date_4w = latest_date_global - timedelta(weeks=4)
        available_dates = sorted(df['DATE'].unique())
        closest_old_date = min(available_dates, key=lambda x: abs(x - target_date_4w))
        df_then = df[df['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
        df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
        df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']

        df_top10 = df_trend.sort_values(by='Zuwachs', ascending=False).head(10)
        fig_top = px.bar(df_top10, x='Zuwachs', y='CLUB_NAME', orientation='h', 
                         title="🚀 Top 10 Gewinner (seit dem 15.01.2026)", color_discrete_sequence=['#00CC96'], text='Zuwachs')
        fig_top.update_traces(textposition='inside', insidetextanchor='start', textangle=0)
        fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top, use_container_width=True, config={'staticPlot': True})

        df_bottom10 = df_trend.sort_values(by='Zuwachs', ascending=True).head(10)
        fig_bottom = px.bar(df_bottom10, x='Zuwachs', y='CLUB_NAME', orientation='h', 
                            title="📉 Geringstes Wachstum (seit dem 15.01.2026)", color_discrete_sequence=['#FF4B4B'], text='Zuwachs')
        fig_bottom.update_traces(textposition='inside', insidetextanchor='start', textangle=0)
        fig_bottom.update_layout(yaxis={'categoryorder':'total descending'})
        st.plotly_chart(fig_bottom, use_container_width=True, config={'staticPlot': True})

    with row2_col2:
        st.subheader("🌐 Gesamtentwicklung Deutschland")
        df_total_history = df.groupby('DATE')['FOLLOWER'].sum().reset_index()
        fig_total = px.line(df_total_history, x='DATE', y='FOLLOWER', title="Summe aller Follower", markers=True, color_discrete_sequence=['#FFB200'])
        fig_total.update_layout(separators=',.')
        fig_total.update_yaxes(tickformat="d")
        
        # Achse sauber machen:
        fig_total.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
        st.plotly_chart(fig_total, use_container_width=True, config={'staticPlot': True})

except Exception as e:
    st.error(f"Fehler: {e}")
















