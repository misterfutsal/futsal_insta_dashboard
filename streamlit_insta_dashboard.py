import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# --- Konfiguration ---
INSTA_SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"
ZUSCHAUER_SHEET_ID = "14puepYtteWGPD1Qv89gCpZijPm5Yrgr8glQnGBh3PXM"

st.set_page_config(page_title="Futsal Statistik Dashboard", layout="wide")

# --- STYLING ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; padding-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { height: 30px; background-color: #FFFFFF; border: 2px solid #D3D3D3; border-radius: 0px; padding: 0px 10px; color: #31333F; font-weight: 100; transition: all 0.3s ease; }
    .stTabs [data-baseweb="tab"]:hover { border-color: #0047AB; background-color: #E8F0FE; color: #0047AB; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #0047AB; border: 2px solid #0047AB; color: #FFFFFF !important; box-shadow: 0px 4px 6px rgba(0, 71, 171, 0.3); }
    .stTabs [data-baseweb="tab"][aria-selected="true"] p { color: #FFFFFF !important; font-size: 18px; font-weight: bold; }
    div[data-baseweb="select"] > div { background-color: #FDFDFD; border: 2px solid #0047AB; border-radius: 8px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); }
    div[data-baseweb="select"] * { color: #0047AB !important;}
    .stSelectbox label p { font-size: 18px !important; color: #0047AB !important; font-weight: 800 !important; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- JAVASCRIPT SCROLL FUNKTION ---
def scroll_to_anchor():
    js = """
    <script>
        var element = document.getElementById('ranking_anchor');
        if (element) {
            element.scrollIntoView({behavior: "smooth", block: "start"});
        }
    </script>
    """
    components.html(js, height=0)

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
tab_insta, tab_zuschauer = st.tabs(["📸 Instagram Follower", "🏟️ Bundesliga Zuschauer"])

# --- TAB 1: INSTAGRAM ---
with tab_insta:
    if not df_insta.empty:
        df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        df_latest_display = df_latest.copy()
        df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
        df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_latest_display['STAND'] = df_latest_display['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))
        
        # --- TEIL 1: WACHSTUMSTRENDS ---
        latest_date_global = df_insta['DATE'].max()
        target_date_4w = latest_date_global - timedelta(weeks=4)
        available_dates = sorted(df_insta['DATE'].unique())
        closest_old_date = min(available_dates, key=lambda x: x if x <= target_date_4w else available_dates[0])
        
        df_then = df_insta[df_insta['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
        df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
        df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
        
        # Namen kürzen
        df_trend['CLUB_NAME_SHORT'] = df_trend['CLUB_NAME'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)

        # STATE INITIALISIERUNG FÜR KLICK-EVENT
        if 'selected_club_from_chart' not in st.session_state:
            st.session_state.selected_club_from_chart = None

        top_row_col1, top_row_col2 = st.columns(2, gap="medium")

        # --- FUNKTION: ROBUSTE AUSWERTUNG DES KLICKS ---
        def handle_chart_selection(event_data):
            if not event_data:
                return False
            
            try:
                # Versuch 1: Normaler Streamlit Objekt-Zugriff
                points = event_data.selection.points
            except AttributeError:
                # Versuch 2: Falls es ein Dictionary ist
                try:
                    points = event_data["selection"]["points"]
                except (KeyError, TypeError):
                    return False
            
            if points:
                first_point = points[0]
                if "customdata" in first_point:
                    selected_name = first_point["customdata"][0]
                    # Nur aktualisieren, wenn es ein neuer Verein ist
                    if st.session_state.selected_club_from_chart != selected_name:
                        st.session_state.selected_club_from_chart = selected_name
                        return True
            return False

        with top_row_col1:
            # Top 10 Gewinner
            fig_win = px.bar(
                df_trend.sort_values(by='Zuwachs', ascending=False).head(10), 
                x='Zuwachs', y='CLUB_NAME_SHORT', 
                orientation='h', 
                title="🚀 Top 10 Gewinner seit dem 15.01.2026 (Klickbar)", 
                color_discrete_sequence=['#00CC96'], 
                text='Zuwachs',
                custom_data=['CLUB_NAME'] 
            )
            
            # Layout aktualisieren: Zoom sperren, aber Klickbarkeit erhalten
            fig_win.update_layout(
                yaxis={
                    'categoryorder': 'total ascending',
                    'fixedrange': True  # 🔒 Verhindert Zoom auf Y-Achse
                },
                xaxis={
                    'fixedrange': True  # 🔒 Verhindert Zoom auf X-Achse
                },
                yaxis_title=None,
                clickmode='event+select',
                dragmode=False,         # 🔒 Verhindert das Ziehen/Maus-Selektieren
                margin=dict(l=0, r=0, t=40, b=0) # Optional: Ränder optimieren
            )
            
            fig_win.update_traces(textposition='inside', insidetextanchor='start', textfont_color='black', textangle=0)
            
            # Event Listener
            event_win = st.plotly_chart(fig_win, use_container_width=True, on_select="rerun", selection_mode="points", key="chart_win")
            if handle_chart_selection(event_win):
                scroll_to_anchor()

        with top_row_col2:
            # Geringstes Wachstum
            fig_loss = px.bar(
                df_trend.sort_values(by='Zuwachs', ascending=True).head(10), 
                x='Zuwachs', y='CLUB_NAME_SHORT', 
                orientation='h', 
                title="📉 Geringstes Wachstum seit dem 15.01.2026 (Klickbar)", 
                color_discrete_sequence=['#FF4B4B'], 
                text='Zuwachs',
                custom_data=['CLUB_NAME'] 
            )
            
            # Layout aktualisieren: Zoom sperren, Interaktion beschränken
            fig_loss.update_layout(
                yaxis={
                    'categoryorder': 'total descending',
                    'fixedrange': True  # 🔒 Verhindert Zoom auf Y-Achse
                },
                xaxis={
                    'fixedrange': True  # 🔒 Verhindert Zoom auf X-Achse
                },
                yaxis_title=None,
                clickmode='event+select',
                dragmode=False          # 🔒 Verhindert das Ziehen/Maus-Selektieren
            )
            fig_loss.update_traces(textposition='inside', insidetextanchor='start', textfont_color='black', textangle=-0)
            
            # Event Listener
            event_loss = st.plotly_chart(fig_loss, use_container_width=True, on_select="rerun", selection_mode="points", key="chart_loss")
            if handle_chart_selection(event_loss):
                scroll_to_anchor()

        st.divider()

        # --- TEIL 2: TABELLEN & DETAILANALYSE ---
        
        # 1. ANCHOR SETZEN
        st.markdown("<div id='ranking_anchor'></div>", unsafe_allow_html=True)
        
        row1_col1, row1_col2 = st.columns(2, gap="medium")
        #h_tables = 2150
        
        with row1_col1:
            st.subheader("🏆 Aktuelles Ranking")
            
            # Hinweis anzeigen
            if st.session_state.selected_club_from_chart:
                st.info(f"👉 Markiert: **{st.session_state.selected_club_from_chart}** (Scrollen Sie in der Liste, falls nicht sichtbar)")
                if st.button("Markierung aufheben"):
                    st.session_state.selected_club_from_chart = None
                    st.rerun()
            else:
                st.markdown("👇 :yellow[Hier Vereine für Detailanalyse selektieren]")

            # Styling Funktion: Färbt die Zeile gelb, wenn sie dem Chart-Klick entspricht
            def highlight_selected_row(row):
                color = ''
                if st.session_state.selected_club_from_chart and row['CLUB_NAME'] == st.session_state.selected_club_from_chart:
                    color = 'background-color: #ffeeba; color: black; font-weight: bold' # Helles Gelb
                return [color] * len(row)

            # Daten vorbereiten (nur Spalten, die wir anzeigen wollen)
            df_view = df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND']]
            
            # Styling anwenden
            styled_df = df_view.style.apply(highlight_selected_row, axis=1)
                
            selection = st.dataframe(
                styled_df, 
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
                height=(len(df_view) + 1) * 35 + 3
            )
            
        with row1_col2:
            st.subheader("🔍 Detailanalyse")
            
            sel_clubs = []
            
            # 1. Manuelle Auswahl aus Tabelle
            if selection and selection.selection.rows:
                sel_clubs = df_latest_display.iloc[selection.selection.rows]['CLUB_NAME'].tolist()
            
            # 2. Automatische Auswahl durch Chart-Klick (hinzufügen, falls nicht schon da)
            if st.session_state.selected_club_from_chart:
                 if st.session_state.selected_club_from_chart not in sel_clubs:
                     sel_clubs.append(st.session_state.selected_club_from_chart)

            if sel_clubs:
                plot_data = df_insta[df_insta['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                fig_detail = px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', title="Vergleich der Vereine", markers=True)
                st.plotly_chart(fig_detail, use_container_width=True)
            else: 
                st.info("💡 Klicke links in der Tabelle auf Zeilen oder oben auf das Diagramm, um den Verlauf zu sehen.")
        
        st.divider()
        
        # --- TEIL 3: GESAMTENTWICKLUNG ---
        st.subheader("🌐 Gesamtentwicklung Deutschland")
        st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
        fig_total = px.line(df_insta.groupby('DATE')['FOLLOWER'].sum().reset_index(), x='DATE', y='FOLLOWER', title="Summe aller Follower", markers=True, color_discrete_sequence=['#FFB200']).update_yaxes(tickformat=',d')
        st.plotly_chart(fig_total, use_container_width=True, config={'staticPlot': True})

    else: 
        st.error("Instagram-Daten konnten nicht geladen werden.")

# --- TAB 2: ZUSCHAUER ---
with tab_zuschauer:
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
            auswahl = st.selectbox("## Wähle einen Verein aus:", options_list, key="vereins_auswahl")

            if "Liga-Gesamtentwicklung" in auswahl:
                df_saison = df_z.groupby('SAISON')['ZUSCHAUER'].mean().reset_index()
                
                if not df_saison.empty:
                    farben_liste = ['#FFD700', '#0057B8'] 
                    df_saison['COLOR'] = [farben_liste[i % 2] for i in range(len(df_saison))]
                
                    fig_saison = px.bar(
                        df_saison, 
                        x='SAISON', 
                        y='ZUSCHAUER',
                        text='ZUSCHAUER',
                        title="Saisonschnitt Bundesliga gesamt",
                    )
                    fig_saison.update_traces(
                        marker_color=df_saison['COLOR'], 
                        textposition='outside',
                        texttemplate='%{text:.0f}' 
                    )
                    fig_saison.update_layout(
                        xaxis_title=None,
                        yaxis_title=None,
                        xaxis=dict(
                            tickfont=dict(size=10),
                            type='category' 
                        ),
                        yaxis=dict(
                            range = [0,350]
                        ),
                        hovermode="x unified"
                    )
                    st.plotly_chart(fig_saison, use_container_width=True)

                cols = ["DATUM", 'SAISON', 'SPIELTAG', 'AVERAGE_SPIELTAG']
                df_helper = df_z[[c for c in cols if c in df_z.columns]].copy()
                
                df_helper = df_helper.drop_duplicates(subset=['SAISON', 'SPIELTAG']).sort_values('DATUM')

                df_helper['DATUM'] = pd.to_datetime(df_helper['DATUM'])
                ist_doppelt = df_helper.duplicated(subset=['DATUM'], keep='first')
                df_helper.loc[ist_doppelt, 'DATUM'] = df_helper.loc[ist_doppelt, 'DATUM'] - pd.Timedelta(days=1)
                
                if not df_helper.empty:
                    fig_trend = px.bar(
                        df_helper, 
                        x='DATUM', 
                        y='AVERAGE_SPIELTAG', 
                        color='SAISON', 
                        text='AVERAGE_SPIELTAG', 
                        title="Zuschauerschnitt im Saisonvergleich (nach Spieltag)",
                        color_discrete_sequence=['#FFD700', '#0057B8']
                    )
                
                    fig_trend.update_layout(
                        xaxis_title=None,
                        yaxis_title=None,
                        xaxis=dict(
                            type='category', 
                            tickmode='array',
                            tickvals=df_helper['DATUM'], 
                            ticktext=df_helper['SPIELTAG'],
                            tickangle=-45,
                            tickfont=dict(size=10)
                        ),
                        hovermode="x unified"
                    )
                    
                    fig_trend.update_traces(textposition='outside')
                    st.plotly_chart(fig_trend, use_container_width=True)
                    
                else:
                    st.warning("Die erforderlichen Spalten (SAISON, SPIELTAG, AVERAGE_SPIELTAG) fehlen im Datensatz.")

            else:
                    team_data = df_z[df_z['HEIM'] == auswahl].sort_values('DATUM')
                    st.markdown(f"### Entwicklung: {auswahl}")
                    
                    stats_saison = team_data.groupby('SAISON')['ZUSCHAUER'].mean().reset_index()
                    stats_saison.columns = ['Saison', 'Ø Zuschauer']
                    stats_saison['Ø Zuschauer'] = stats_saison['Ø Zuschauer'].round(0).astype(int)
                    
                    fig_avg = px.bar(stats_saison, x='Saison', y='Ø Zuschauer', text='Ø Zuschauer', 
                                     title=f"Durchschnittliche Zuschauer pro Saison",
                                     color='Saison', color_discrete_map=color_map)
                    fig_avg.update_traces(textposition='outside')
                    fig_avg.update_layout(
                        xaxis=dict(fixedrange=True),
                        yaxis=dict(
                            fixedrange=True, 
                            range=[0, stats_saison['Ø Zuschauer'].max() * 1.25],
                            nticks=10, 
                            exponentformat="none"
                        ),
                        margin=dict(b=100)
                    )
                    st.plotly_chart(fig_avg, use_container_width=True)
                    
                    team_data['X_LABEL'] = team_data.apply(lambda x: f"{x['DATUM'].strftime('%d.%m.%Y')} (ST {str(x['SPIELTAG']).replace('.0', '')})", axis=1)
                    
                    fig_team = px.bar(team_data, x='X_LABEL', y='ZUSCHAUER', text='ZUSCHAUER', 
                                      color='SAISON', color_discrete_map=color_map, 
                                      title=f"Alle Heimspiele von {auswahl}")
                    
                    fig_team.update_traces(textposition='outside')
                    fig_team.update_layout(
                        xaxis=dict(fixedrange=True),
                        xaxis_tickangle=-45,
                        yaxis_range=[0, team_data['ZUSCHAUER'].max() * 1.25], 
                        yaxis=dict(fixedrange=True, nticks=10, exponentformat="none"),
                        margin=dict(b=100)
                    )
                    
                    st.plotly_chart(fig_team, use_container_width=True)
    else: 
        st.error("Zuschauer-Daten konnten nicht geladen werden.")





