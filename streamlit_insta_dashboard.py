import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- Konfiguration ---
INSTA_SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"
ZUSCHAUER_SHEET_ID = "14puepYtteWGPD1Qv89gCpZijPm5Yrgr8glQnGBh3PXM"

st.set_page_config(page_title="Futsal Insta-Analytics", layout="wide")

# --- STYLING FÜR DIE REITER (Blau/Gelb) ---
st.markdown("""
<style>
    /* Hintergrund der Reiter-Leiste */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    /* Nicht ausgewählte Reiter */
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    /* Ausgewählter Reiter: BLAU Hintergrund, GELB Text */
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #0047AB; 
        color: #FFD700 !important;
    }
    /* Damit die Schriftfarbe auch wirklich übernommen wird */
    .stTabs [data-baseweb="tab"][aria-selected="true"] p {
        color: #FFD700 !important;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- DATEN LADEN ---
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
        return pd.DataFrame()

# ==========================================
# 1. KOPFBEREICH (Immer sichtbar)
# ==========================================

# Wir laden Insta-Daten hier schon, damit wir die Gesamtzahl im Header zeigen können
df_insta = load_data(INSTA_SHEET_ID, "gcp_service_account")

# Datenaufbereitung für Header
if not df_insta.empty:
    if 'DATE' in df_insta.columns:
        df_insta['DATE'] = pd.to_datetime(df_insta['DATE']).dt.date
    df_insta['FOLLOWER'] = pd.to_numeric(df_insta['FOLLOWER'], errors='coerce').fillna(0)
    df_insta = df_insta.sort_values(by=['CLUB_NAME', 'DATE'])
    df_insta = df_insta.drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
    
    # Neueste Daten für Header-Summe
    df_latest = df_insta.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    akt_datum = df_insta['DATE'].max().strftime('%d.%m.%Y')
else:
    summe_follower = "0"
    akt_datum = "-"

# Header Anzeige
st.image("logo_instagram_dashboard.png", width=350)
st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")

st.divider()

# ==========================================
# 2. DIE REITER (TABS)
# ==========================================
tab_insta, tab_zuschauer = st.tabs(["📸 Instagram Dashboard", "🏟️ Zuschauer Dashboard"])

# --- REITER 1: INSTAGRAM (Vollständig) ---
with tab_insta:
    if not df_insta.empty:
        # Datenvorbereitung (wie im Original)
        df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
        df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        
        df_latest_display = df_latest.copy()
        df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
        df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_latest_display['STAND'] = df_latest_display['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))

        # --- OBERE REIHE (Tabelle & Detail) ---
        row1_col1, row1_col2 = st.columns(2, gap="medium")
        
        with row1_col1:
            st.subheader("🏆 Aktuelles Ranking")
            st.markdown("**:yellow[👇 Wähle hier einen oder mehrere Vereine aus!]**")
            selection = st.dataframe(
                df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND']], 
                column_config={
                    "RANG": st.column_config.TextColumn("Rang"),
                    "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"),
                    "FOLLOWER": st.column_config.TextColumn("Follower"),
                    "STAND": st.column_config.TextColumn("Stand")
                },
                hide_index=True, on_select="rerun", selection_mode="multi-row", use_container_width=True, height=2150
            )

        with row1_col2:
            st.subheader("🔍 Detailanalyse")
            if selection and selection.selection.rows:
                sel_indices = selection.selection.rows
                sel_clubs = df_latest.iloc[sel_indices]['CLUB_NAME'].tolist()
                plot_data = df_insta[df_insta['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                
                fig_detail = px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', title="Vergleich der Vereine", markers=True)
                fig_detail.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
                st.plotly_chart(fig_detail, use_container_width=True)
            else:
                st.info("💡 Klicke links auf einen oder mehrere Vereine für Details.")

        st.divider()

        # --- UNTERE REIHE (Trends & Gesamt) ---
        row2_col1, row2_col2 = st.columns(2, gap="medium")

        with row2_col1:
            st.subheader("📈 Wachstumstrends")
            latest_date_global = df_insta['DATE'].max()
            target_date_4w = latest_date_global - timedelta(weeks=4)
            available_dates = sorted(df_insta['DATE'].unique())
            closest_old_date = min(available_dates, key=lambda x: x if x <= target_date_4w else available_dates[0])
            
            df_then = df_insta[df_insta['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
            df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
            df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']

            # Top 10
            df_top10 = df_trend.sort_values(by='Zuwachs', ascending=False).head(10).copy()
            df_top10['CLUB_NAME'] = df_top10['CLUB_NAME'].str[:20]
            fig_top = px.bar(df_top10, x='Zuwachs', y='CLUB_NAME', orientation='h', title="🚀 Top 10 Gewinner", color_discrete_sequence=['#00CC96'], text='Zuwachs')
            fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_top, use_container_width=True, config={'staticPlot': True})

            # Flop 10
            df_bottom10 = df_trend.sort_values(by='Zuwachs', ascending=True).head(10).copy()
            df_bottom10['CLUB_NAME'] = df_bottom10['CLUB_NAME'].str[:20]
            fig_bottom = px.bar(df_bottom10, x='Zuwachs', y='CLUB_NAME', orientation='h', title="📉 Geringstes Wachstum", color_discrete_sequence=['#FF4B4B'], text='Zuwachs')
            fig_bottom.update_layout(yaxis={'categoryorder':'total descending'})
            st.plotly_chart(fig_bottom, use_container_width=True, config={'staticPlot': True})

        with row2_col2:
            st.subheader("🌐 Gesamtentwicklung Deutschland")
            df_total_history = df_insta.groupby('DATE')['FOLLOWER'].sum().reset_index()
            fig_total = px.line(df_total_history, x='DATE', y='FOLLOWER', title="Summe aller Follower", markers=True, color_discrete_sequence=['#FFB200'])
            fig_total.update_yaxes(tickformat=',d')
            fig_total.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
            st.plotly_chart(fig_total, use_container_width=True, config={'staticPlot': True})

    else:
        st.error("Instagram-Daten konnten nicht geladen werden.")

# --- REITER 2: ZUSCHAUER ---
with tab_zuschauer:
    st.header("🏟️ Zuschauer-Statistiken")
    df_z = load_data(ZUSCHAUER_SHEET_ID, "Google_Sheets_zuschauer")

    if not df_z.empty:
        if 'DATUM' in df_z.columns:
            df_z['DATUM'] = pd.to_datetime(df_z['DATUM']).dt.date
        if 'ZUSCHAUER' in df_z.columns:
            df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce').fillna(0)

        if 'HEIM' in df_z.columns:
            heim_teams = sorted(df_z['HEIM'].unique())
            auswahl_team = st.selectbox("Wähle ein Heim-Team:", heim_teams)

            team_data = df_z[df_z['HEIM'] == auswahl_team].sort_values('DATUM')
            
            if not team_data.empty:
                st.subheader(f"Zuschauer bei {auswahl_team}")
                fig_z = px.bar(
                    team_data, 
                    x='DATUM', 
                    y='ZUSCHAUER', 
                    text='ZUSCHAUER',
                    title=f"Heimspiele",
                    labels={'ZUSCHAUER': 'Fans', 'DATUM': 'Datum'},
                    color_discrete_sequence=['#0047AB'] # Blau passend zum Thema
                )
                fig_z.update_traces(textposition='outside')
                st.plotly_chart(fig_z, use_container_width=True)
            else:
                st.warning("Keine Spiele gefunden.")
        else:
            st.error("Spalte 'HEIM' fehlt im Google Sheet.")
    else:
        st.error("Zuschauer-Daten konnten nicht geladen werden.")
