import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta

# --- Konfiguration ---
INSTA_SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"
ZUSCHAUER_SHEET_ID = "14puepYtteWGPD1Qv89gCpZijPm5Yrgr8glQnGBh3PXM"

st.set_page_config(page_title="Futsal Analytics Dashboard", layout="wide")

# --- STYLING ---
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

# --- DATEN LADEN FUNKTION ---
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
        st.error(f"Fehler beim Laden der Daten: {e}")
        return pd.DataFrame()

# ==========================================
# 1. DATEN-VORBEREITUNG (INSTAGRAM)
# ==========================================
df_insta = load_data(INSTA_SHEET_ID, "gcp_service_account")

if not df_insta.empty:
    if 'DATE' in df_insta.columns: 
        df_insta['DATE'] = pd.to_datetime(df_insta['DATE']).dt.date
    df_insta['FOLLOWER'] = pd.to_numeric(df_insta['FOLLOWER'], errors='coerce').fillna(0)
    df_insta = df_insta.sort_values(by=['CLUB_NAME', 'DATE']).drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
    
    df_latest = df_insta.sort_values('DATE').groupby('CLUB_NAME').last().reset_index().sort_values(by='FOLLOWER', ascending=False)
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    akt_datum = df_insta['DATE'].max().strftime('%d.%m.%Y')
else:
    summe_follower, akt_datum = "0", "-"

# Header-Bereich
try: 
    st.image("banner_statistik_dashboard.png", width=450)
except: 
    st.title("⚽ Futsal Dashboard") 

st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")
st.divider()

# ==========================================
# 2. REITER / TABS
# ==========================================
tab_insta, tab_zuschauer = st.tabs(["📸 Instagram Dashboard", "🏟️ Zuschauer Dashboard"])

# --- TAB 1: INSTAGRAM ---
with tab_insta:
    if not df_insta.empty:
        df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        df_latest_display = df_latest.copy()
        df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
        df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_latest_display['STAND'] = df_latest_display['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))
        
        row1_col1, row1_col2 = st.columns(2, gap="medium")
        h_tables = 2150
        
        with row1_col1:
            st.subheader("🏆 Aktuelles Ranking")
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
                sel_clubs = df_latest.iloc[selection.selection.rows]['CLUB_NAME'].tolist()
                plot_data = df_insta[df_insta['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                fig_detail = px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', title="Vergleich der Vereine", markers=True)
                st.plotly_chart(fig_detail, use_container_width=True)
            else: 
                st.info("💡 Klicke links in der Tabelle auf Zeilen, um den Verlauf zu vergleichen.")
        
        st.divider()
        
        row2_col1, row2_col2 = st.columns(2, gap="medium")
        with row2_col1:
            st.subheader("📈 Wachstumstrends (4 Wochen)")
            latest_date_global = df_insta['DATE'].max()
            target_date_4w = latest_date_global - timedelta(weeks=4)
            available_dates = sorted(df_insta['DATE'].unique())
            closest_old_date = min(available_dates, key=lambda x: x if x <= target_date_4w else available_dates[0])
            
            df_then = df_insta[df_insta['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
            df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
            df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
            
            # Namen auf 20 Zeichen kürzen
            df_trend['CLUB_NAME_SHORT'] = df_trend['CLUB_NAME'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)

            # Top 10 Gewinner
            fig_win = px.bar(df_trend.sort_values(by='Zuwachs', ascending=False).head(10), x='Zuwachs', y='CLUB_NAME_SHORT', orientation='h', title="🚀 Top 10 Gewinner", color_discrete_sequence=['#00CC96'], text='Zuwachs')
            fig_win.update_layout(yaxis={'categoryorder':'total ascending'}, yaxis_title=None)
            # Text weiß, 90 Grad gedreht, links im Balken
            fig_win.update_traces(textposition='inside', insidetextanchor='start', textfont_color='black', textangle=0)
            st.plotly_chart(fig_win, use_container_width=True, config={'staticPlot': True})

            # Geringstes Wachstum
            fig_loss = px.bar(df_trend.sort_values(by='Zuwachs', ascending=True).head(10), x='Zuwachs', y='CLUB_NAME_SHORT', orientation='h', title="📉 Geringstes Wachstum", color_discrete_sequence=['#FF4B4B'], text='Zuwachs')
            fig_loss.update_layout(yaxis={'categoryorder':'total descending'}, yaxis_title=None)
            # Text weiß, 90 Grad gedreht, links im Balken
            fig_loss.update_traces(textposition='inside', insidetextanchor='start', textfont_color='black', textangle=-0)
            st.plotly_chart(fig_loss, use_container_width=True, config={'staticPlot': True})
            
        with row2_col2:
            st.subheader("🌐 Gesamtentwicklung Deutschland")
            st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
            fig_total = px.line(df_insta.groupby('DATE')['FOLLOWER'].sum().reset_index(), x='DATE', y='FOLLOWER', title="Summe aller Follower", markers=True, color_discrete_sequence=['#FFB200']).update_yaxes(tickformat=',d')
            # Als fixes Bild anzeigen
            st.plotly_chart(fig_total, use_container_width=True, config={'staticPlot': True})
    else: 
        st.error("Instagram-Daten konnten nicht geladen werden.")

# --- TAB 2: ZUSCHAUER ---
with tab_zuschauer:
    st.header("🏟️ Zuschauer-Statistiken")
    df_z = load_data(ZUSCHAUER_SHEET_ID, "gcp_service_account")
    df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce')
    df_z = df_z[df_z['ZUSCHAUER'] > 0]

    if not df_z.empty:
        if 'DATUM' in df_z.columns: 
            df_z['DATUM'] = pd.to_datetime(df_z['DATUM'], dayfirst=True, errors='coerce')
        if 'ZUSCHAUER' in df_z.columns: 
            df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce').fillna(0)
        if 'AVERAGE_SPIELTAG' in df_z.columns:
            df_z['AVERAGE_SPIELTAG'] = pd.to_numeric(df_z['AVERAGE_SPIELTAG'], errors='coerce').fillna(0)
        
        def get_season(d):
            if pd.isnull(d): return "Unbekannt"
            return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"
        
        if 'SAISON' not in df_z.columns and 'SEASON' in df_z.columns:
            df_z['SAISON'] = df_z['SEASON']
        elif 'SAISON' not in df_z.columns:
            df_z['SAISON'] = df_z['DATUM'].apply(get_season)

        unique_seasons = sorted([s for s in df_z['SAISON'].unique() if s != "Unbekannt"])
        color_map = {s: ('#0047AB' if i % 2 == 0 else '#FFC000') for i, s in enumerate(unique_seasons)}

        if 'HEIM' in df_z.columns:
            options_list = ["🇩🇪 Liga-Gesamtentwicklung (Spieltag-Schnitt)"] + sorted(df_z['HEIM'].unique())
            auswahl = st.selectbox("Wähle eine Analyse:", options_list)

            if "Liga-Gesamtentwicklung" in auswahl:
                st.subheader("📈 Durchschnittliche Zuschauer pro Spieltag")
                cols = ['SAISON', 'SPIELTAG', 'AVERAGE_SPIELTAG']
                df_helper = df_z[[c for c in cols if c in df_z.columns]].copy()
                df_helper = df_helper.drop_duplicates(subset=['SAISON', 'SPIELTAG']).sort_values(['SAISON', 'SPIELTAG'])

                if not df_helper.empty:
                    fig_trend = px.line(df_helper, x='SPIELTAG', y='AVERAGE_SPIELTAG', color='SAISON', markers=True, title="Zuschauerschnitt im Saisonvergleich (nach Spieltag)", labels={'AVERAGE_SPIELTAG': 'Ø Zuschauer', 'SPIELTAG': 'Spieltag'}, color_discrete_map=color_map)
                    fig_trend.update_layout(hovermode="x unified", xaxis=dict(dtick=1))
                    st.plotly_chart(fig_trend, use_container_width=True)
                    with st.expander("Datenquelle der Grafik anzeigen"):
                        st.dataframe(df_helper, hide_index=True, use_container_width=True)
                else:
                    st.warning("Die erforderlichen Spalten (SAISON, SPIELTAG, AVERAGE_SPIELTAG) fehlen im Datensatz.")

            else:
                 # 1. Daten für das Team vorbereiten
                    team_data = df_z[df_z['HEIM'] == auswahl].sort_values('DATUM')
                    st.subheader(f"Entwicklung: {auswahl}")
                    
                    # --- NEU: DURCHSCHNITT JE SAISON ALS BALKEN ---
                    # Wir rechnen aus, wie viele Fans im Schnitt pro Jahr da waren
                    stats_saison = team_data.groupby('SAISON')['ZUSCHAUER'].mean().reset_index()
                    stats_saison.columns = ['Saison', 'Ø Zuschauer']
                    stats_saison['Ø Zuschauer'] = stats_saison['Ø Zuschauer'].round(0).astype(int)
                    
                    # Das Bild für die Jahres-Durchschnitte malen
                    fig_avg = px.bar(stats_saison, x='Saison', y='Ø Zuschauer', text='Ø Zuschauer', 
                                     title=f"Durchschnittliche Zuschauer pro Saison",
                                     color='Saison', color_discrete_map=color_map)
                    fig_avg.update_traces(textposition='outside')
                    fig_avg.update_layout(
                        yaxis_range=[0, team_data['ZUSCHAUER'].max() * 1.25], 
                        yaxis=dict(nticks=10, exponentformat="none"),
                        margin=dict(b=100)
                    )
                    st.plotly_chart(fig_avg, use_container_width=True)
                    
                    # --- EINZELNE SPIELE ---
                    # Hier bereiten wir die Namen für die untere Leiste vor (Datum + Spieltag)
                    team_data['X_LABEL'] = team_data.apply(lambda x: f"{x['DATUM'].strftime('%d.%m.%Y')} (ST {str(x['SPIELTAG']).replace('.0', '')})", axis=1)
                    
                    # Das Bild für jedes einzelne Spiel malen
                    fig_team = px.bar(team_data, x='X_LABEL', y='ZUSCHAUER', text='ZUSCHAUER', 
                                     color='SAISON', color_discrete_map=color_map, 
                                     title=f"Alle Heimspiele von {auswahl}")
                    
                    # Das Aussehen verschönern (Zahlen oben, Schrift schräg)
                    fig_team.update_traces(textposition='outside')
                    fig_team.update_layout(
                        xaxis_tickangle=-45,
                        yaxis_range=[0, team_data['ZUSCHAUER'].max() * 1.25], 
                        yaxis=dict(nticks=10, exponentformat="none"),
                        margin=dict(b=100)
                    )
                    
                    st.plotly_chart(fig_team, use_container_width=True)
    else: 
        st.error("Zuschauer-Daten konnten nicht geladen werden.")









