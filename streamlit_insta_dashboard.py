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

# --- STYLING (Unverändert) ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; padding-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { height: 30px; background-color: #FFFFFF; border: 2px solid #D3D3D3; border-radius: 0px; padding: 0px 10px; color: #31333F; font-weight: 100; transition: all 0.3s ease; }
    .stTabs [data-baseweb="tab"]:hover { border-color: #0047AB; background-color: #E8F0FE; color: #0047AB; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #0047AB; border: 2px solid #0047AB; color: #FFFFFF !important; box-shadow: 0px 4px 6px rgba(0, 71, 171, 0.3); }
    .stTabs [data-baseweb="tab"][aria-selected="true"] p { color: #FFFFFF !important; font-size: 18px; font-weight: bold; }
    div[data-baseweb="select"] > div { background-color: #FDFDFD; border: 2px solid #0047AB; border-radius: 8px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); }
    .stSelectbox label p { font-size: 18px !important; color: #0047AB !important; font-weight: 800 !important; margin-bottom: 5px; }
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
    except:
        return pd.DataFrame()

# ==========================================
# 1. KOPFBEREICH (Unverändert)
# ==========================================
df = load_data(INSTA_SHEET_ID, "gcp_service_account")
if not df.empty:
    if 'DATE' in df.columns: df['DATE'] = pd.to_datetime(df['DATE']).dt.date
    df['FOLLOWER'] = pd.to_numeric(df['FOLLOWER'], errors='coerce').fillna(0)
    df = df.sort_values(by=['CLUB_NAME', 'DATE']).drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index().sort_values(by='FOLLOWER', ascending=False)
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    akt_datum = df['DATE'].max().strftime('%d.%m.%Y')
else:
    summe_follower, akt_datum = "0", "-"

try: st.image("banner_statistik_dashboard.png", width=450)
except: st.title("Futsal Dashboard") 
st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")
st.divider()

# ==========================================
# 2. REITER / TABS
# ==========================================
tab_insta, tab_zuschauer = st.tabs(["📸 Instagram Dashboard", "🏟️ Zuschauer Dashboard"])

# --- TAB 1: INSTAGRAM (100% wie vorher) ---
with tab_insta:
    if not df.empty:
        df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        df_latest_display = df_latest.copy()
        df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
        df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_latest_display['STAND'] = df_latest_display['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))
        row1_col1, row1_col2 = st.columns(2, gap="medium")
        with row1_col1:
            st.subheader("🏆 Aktuelles Ranking")
            selection = st.dataframe(df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND']], column_config={"RANG": st.column_config.TextColumn("Rang"), "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"), "FOLLOWER": st.column_config.TextColumn("Follower"), "STAND": st.column_config.TextColumn("Stand")}, hide_index=True, on_select="rerun", selection_mode="multi-row", use_container_width=True, height=2150)
        with row1_col2:
            st.subheader("🔍 Detailanalyse")
            if selection and selection.selection.rows:
                sel_clubs = df_latest.iloc[selection.selection.rows]['CLUB_NAME'].tolist()
                plot_data = df[df['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                fig_detail = px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', title="Vergleich der Vereine", markers=True)
                st.plotly_chart(fig_detail, use_container_width=True)
            else: st.info("💡 Klicke links auf einen oder mehrere Vereine für Details.")
        st.divider()
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
            df_top10 = df_trend.sort_values(by='Zuwachs', ascending=False).head(10).copy()
            st.plotly_chart(px.bar(df_top10, x='Zuwachs', y='CLUB_NAME', orientation='h', title="🚀 Top 10 Gewinner", color_discrete_sequence=['#00CC96'], text='Zuwachs').update_layout(yaxis={'categoryorder':'total ascending'}), use_container_width=True, config={'staticPlot': True})
            df_bottom10 = df_trend.sort_values(by='Zuwachs', ascending=True).head(10).copy()
            st.plotly_chart(px.bar(df_bottom10, x='Zuwachs', y='CLUB_NAME', orientation='h', title="📉 Geringstes Wachstum", color_discrete_sequence=['#FF4B4B'], text='Zuwachs').update_layout(yaxis={'categoryorder':'total descending'}), use_container_width=True, config={'staticPlot': True})
        with row2_col2:
            st.subheader("🌐 Gesamtentwicklung Deutschland")
            st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
            st.plotly_chart(px.line(df.groupby('DATE')['FOLLOWER'].sum().reset_index(), x='DATE', y='FOLLOWER', title="Summe aller Follower", markers=True, color_discrete_sequence=['#FFB200']).update_yaxes(tickformat=',d'), use_container_width=True, config={'staticPlot': True})
    else: st.error("Instagram-Daten konnten nicht geladen werden.")

# --- TAB 2: ZUSCHAUER (ANGESPASST) ---
with tab_zuschauer:
    st.header("🏟️ Zuschauer-Statistiken")
    df_z = load_data(ZUSCHAUER_SHEET_ID, "gcp_service_account")

    if not df_z.empty:
        if 'DATUM' in df_z.columns: df_z['DATUM'] = pd.to_datetime(df_z['DATUM'], dayfirst=True, errors='coerce')
        if 'ZUSCHAUER' in df_z.columns: df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce').fillna(0)
        
        def get_season(d):
            if pd.isnull(d): return "Unbekannt"
            return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"
        df_z['SAISON'] = df_z['DATUM'].apply(get_season)

        unique_seasons = sorted([s for s in df_z['SAISON'].unique() if s != "Unbekannt"])
        color_map = {s: ('#0047AB' if i % 2 == 0 else '#FFC000') for i, s in enumerate(unique_seasons)}

        if 'HEIM' in df_z.columns:
            options_list = ["🇩🇪 Liga-Gesamtentwicklung (Jahres-Schnitt)"] + sorted(df_z['HEIM'].unique())
            auswahl = st.selectbox("Wähle eine Analyse:", options_list)

            # --- OPTION: LIGA-GESAMT ---
            if "Liga-Gesamtentwicklung" in auswahl:
                st.subheader("📈 Entwicklung der Zuschauerzahlen (Saisonschnitt)")
                
                # 1. Durchschnitt pro Saison (Jahres-Ebene)
                stats_year = df_z.groupby('SAISON')['ZUSCHAUER'].agg(['count', 'mean']).reset_index()
                stats_year.columns = ['Saison', 'Anzahl Spiele', 'Ø Zuschauer']
                stats_year['Ø Zuschauer'] = stats_year['Ø Zuschauer'].round(0).astype(int)
                #st.dataframe(stats_year, hide_index=True, use_container_width=True)
                
                fig_year = px.bar(stats_year, x='Saison', y='Ø Zuschauer', text='Ø Zuschauer', color='Saison', color_discrete_map=color_map, title="Schnitt pro Saison")
                fig_year.update_layout(yaxis_range=[0, stats_year['Ø Zuschauer'].max() * 1.2])
                st.plotly_chart(fig_year, use_container_width=True)

                # 2. Alle Phasen (Spieltage inkl. Playoffs)
                if 'SPIELTAG' in df_z.columns:
                    st.divider()
                    st.subheader("🏟️ Details pro Spielphase (Alle Spieltage & Playoffs)")
                    df_all_phases = df_z.copy()
                    df_all_phases['SPIELTAG_STR'] = df_all_phases['SPIELTAG'].astype(str).str.replace(".0", "", regex=False)
                    df_phase_agg = df_all_phases.groupby(['SAISON', 'SPIELTAG_STR', 'DATUM'])['ZUSCHAUER'].mean().reset_index().sort_values('DATUM')
                    df_phase_agg['X_LABEL'] = df_phase_agg['SAISON'] + " - " + df_phase_agg['SPIELTAG_STR']
                    
                    fig_phases = px.bar(df_phase_agg, x='X_LABEL', y='ZUSCHAUER', text='ZUSCHAUER', color='SAISON', color_discrete_map=color_map, title="Schnitt je Spielphase (chronologisch)")
                    fig_phases.update_traces(textposition='outside')
                    fig_phases.update_layout(yaxis_range=[0, df_phase_agg['ZUSCHAUER'].max() * 1.2])
                    st.plotly_chart(fig_phases, use_container_width=True)

            # --- OPTION: EINZELNER VEREIN ---
            else:
                team_data = df_z[df_z['HEIM'] == auswahl].sort_values('DATUM')
                st.subheader(f"Entwicklung: {auswahl}")
                
                stats_team = team_data.groupby('SAISON')['ZUSCHAUER'].agg(['count', 'mean']).reset_index()
                stats_team.columns = ['Saison', 'Anzahl Spiele', 'Ø Zuschauer']
                stats_team['Ø Zuschauer'] = stats_team['Ø Zuschauer'].round(0).astype(int)
                st.dataframe(stats_team, hide_index=True, use_container_width=True)

                team_data['X_LABEL'] = team_data.apply(lambda x: f"{x['DATUM'].strftime('%d.%m.%Y')} ({str(x['SPIELTAG']).replace('.0', '')})", axis=1)
                fig_team = px.bar(team_data, x='X_LABEL', y='ZUSCHAUER', text='ZUSCHAUER', color='SAISON', color_discrete_map=color_map, title=f"Spiele von {auswahl}")
                fig_team.update_layout(yaxis_range=[0, team_data['ZUSCHAUER'].max() * 1.2])
                st.plotly_chart(fig_team, use_container_width=True)
