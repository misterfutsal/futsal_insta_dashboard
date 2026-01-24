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

# --- STYLING (DESIGN UPDATE: HIGH CONTRAST TABS) ---
st.markdown("""
<style>
    /* --- TAB STYLING (NEU: Button-Style mit hohem Kontrast) --- */
    
    /* Container der Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px; /* Abstand zwischen den Tabs */
        background-color: transparent;
        padding-bottom: 10px;
    }

    /* INAKTIVER TAB (Standard) */
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #FFFFFF; /* Reinweiß */
        border: 2px solid #D3D3D3; /* Hellgrauer Rahmen zur Abgrenzung */
        border-radius: 8px; /* Abgerundete Ecken */
        padding: 0px 20px;
        color: #31333F; /* Dunkelgrauer Text für Lesbarkeit */
        font-weight: 600;
        transition: all 0.3s ease; /* Weicher Übergang */
    }

    /* HOVER EFFEKT (Maus drüber) */
    .stTabs [data-baseweb="tab"]:hover {
        border-color: #0047AB;
        background-color: #E8F0FE; /* Ganz helles Blau */
        color: #0047AB;
    }

    /* AKTIVER TAB (Ausgewählt) */
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #0047AB; /* Tiefes Blau */
        border: 2px solid #0047AB;
        color: #FFFFFF !important; /* Weißer Text - bester Kontrast */
        box-shadow: 0px 4px 6px rgba(0, 71, 171, 0.3); /* Schatten für "Pop"-Effekt */
    }
    
    /* Text im aktiven Tab */
    .stTabs [data-baseweb="tab"][aria-selected="true"] p {
        color: #FFFFFF !important;
        font-size: 18px; /* Etwas größer */
        font-weight: bold;
    }

    /* --- SELECTBOX DESIGN (Beibehalten) --- */
    div[data-baseweb="select"] > div {
        background-color: #FDFDFD;
        border: 2px solid #0047AB;
        border-radius: 8px;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
    }
    div[data-baseweb="select"] span {
        font-weight: 600;
        color: #333;
    }
    .stSelectbox label p {
        font-size: 18px !important;
        color: #0047AB !important;
        font-weight: 800 !important;
        margin-bottom: 5px;
    }
    div[data-baseweb="select"] svg {
        fill: #0047AB !important;
    }

    /* --- DATAFRAME HINWEIS (Beibehalten) --- */
    .instruction-text {
        background-color: #FFF9C4;
        padding: 10px;
        border-left: 5px solid #FFD700;
        border-radius: 4px;
        font-weight: bold;
        color: #333;
        margin-bottom: 10px;
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
# 1. KOPFBEREICH (Logo & Link)
# ==========================================

# Wir laden Insta-Daten hier schon für den Header
df = load_data(INSTA_SHEET_ID, "gcp_service_account")

# Daten vorbereiten
if not df.empty:
    if 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE']).dt.date
    df['FOLLOWER'] = pd.to_numeric(df['FOLLOWER'], errors='coerce').fillna(0)
    df = df.sort_values(by=['CLUB_NAME', 'DATE'])
    df = df.drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
    
    # Neueste Daten für Header
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
    
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    akt_datum = df['DATE'].max().strftime('%d.%m.%Y')
else:
    summe_follower = "0"
    akt_datum = "-"

# Header Anzeige
try:
    st.image("banner_statistik_dashboard.png", width=450)
except:
    st.title("Futsal Dashboard") 

st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")

st.divider()

# ==========================================
# 2. REITER / TABS
# ==========================================
tab_insta, tab_zuschauer = st.tabs(["📸 Instagram Dashboard", "🏟️ Zuschauer Dashboard"])

# --- TAB 1: INSTAGRAM ---
with tab_insta:
    if not df.empty:
        # Daten weiterverarbeiten
        df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        
        df_latest_display = df_latest.copy()
        df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
        df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_latest_display['STAND'] = df_latest_display['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))

        # --- OBERE REIHE ---
        row1_col1, row1_col2 = st.columns(2, gap="medium")
        h_tables = 2150 

        with row1_col1:
            st.subheader("🏆 Aktuelles Ranking")
            st.markdown('<div class="instruction-text">👇 Klicke in die Tabelle, um Vereine auszuwählen!</div>', unsafe_allow_html=True)
            
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
            if selection and selection.selection.rows:
                sel_indices = selection.selection.rows
                sel_clubs = df_latest.iloc[sel_indices]['CLUB_NAME'].tolist()
                
                plot_data = df[df['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                
                fig_detail = px.line(
                    plot_data, 
                    x='DATE', 
                    y='FOLLOWER', 
                    color='CLUB_NAME', 
                    title="Vergleich der Vereine", 
                    markers=True
                )
                
                fig_detail.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
                st.plotly_chart(fig_detail, use_container_width=True)
            else:
                st.info("💡 Klicke links auf einen oder mehrere Vereine für Details.")

        st.divider()

        # --- UNTERE REIHE ---
        row2_col1, row2_col2 = st.columns(2, gap="medium")

        with row2_col1:
            st.subheader("📈 Wachstumstrends")
            latest_date_global = df['DATE'].max()
            target_date_4w = latest_date_global - timedelta(weeks=4)
            available_dates = sorted(df['DATE'].unique())
            closest_old_date = min(available_dates, key=lambda x: x if x <= target_date_4w else available_dates[0])
            
            df_then = df[df['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
            df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
            df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']

            # TOP 10 GRAFIK
            df_top10 = df_trend.sort_values(by='Zuwachs', ascending=False).head(10).copy()
            df_top10['CLUB_NAME'] = df_top10['CLUB_NAME'].str[:20]
            
            fig_top = px.bar(df_top10, x='Zuwachs', y='CLUB_NAME', orientation='h', 
                             title="🚀 Top 10 Gewinner (seit dem 15.01.2026)", color_discrete_sequence=['#00CC96'], text='Zuwachs')
            fig_top.update_traces(textposition='inside', insidetextanchor='start', textangle=0)
            fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
            fig_top.update_yaxes(title_text=None)
            st.plotly_chart(fig_top, use_container_width=True, config={'staticPlot': True})

            # BOTTOM 10 GRAFIK
            df_bottom10 = df_trend.sort_values(by='Zuwachs', ascending=True).head(10).copy()
            df_bottom10['CLUB_NAME'] = df_bottom10['CLUB_NAME'].str[:20]
            
            fig_bottom = px.bar(df_bottom10, x='Zuwachs', y='CLUB_NAME', orientation='h', 
                                title="📉 Geringstes Wachstum (seit dem 15.01.2026)", color_discrete_sequence=['#FF4B4B'], text='Zuwachs')
            fig_bottom.update_traces(textposition='inside', insidetextanchor='start', textangle=0)
            fig_bottom.update_layout(yaxis={'categoryorder':'total descending'})
            fig_bottom.update_yaxes(title_text=None)
            st.plotly_chart(fig_bottom, use_container_width=True, config={'staticPlot': True})

        with row2_col2:
            st.subheader("🌐 Gesamtentwicklung Deutschland")
            st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
            df_total_history = df.groupby('DATE')['FOLLOWER'].sum().reset_index()
            fig_total = px.line(df_total_history, x='DATE', y='FOLLOWER', title="Summe aller Follower", markers=True, color_discrete_sequence=['#FFB200'])
            fig_total.update_layout(separators=',.')
            fig_total.update_yaxes(tickformat=',d')
            fig_total.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
            st.plotly_chart(fig_total, use_container_width=True, config={'staticPlot': True})

    else:
        st.error("Instagram-Daten konnten nicht geladen werden.")

# --- TAB 2: ZUSCHAUER ---
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
            
            auswahl_team = st.selectbox("Wähle einen Verein (Heimteam):", heim_teams)

            team_data = df_z[df_z['HEIM'] == auswahl_team].sort_values('DATUM')
            
            if not team_data.empty:
                st.subheader(f"Zuschauer bei {auswahl_team}")
                fig_z = px.bar(
                    team_data, 
                    x='DATUM', 
                    y='ZUSCHAUER',
                    text='ZUSCHAUER',
                    color_discrete_sequence=['#0047AB'],
                    labels={'ZUSCHAUER': 'Anzahl', 'DATUM': 'Datum'}
                )
                fig_z.update_traces(textposition='outside')
                st.plotly_chart(fig_z, use_container_width=True)
            else:
                st.warning("Keine Daten für dieses Team gefunden.")
        else:
            st.error("Spalte 'HEIM' fehlt im Sheet.")



