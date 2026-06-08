import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime, timedelta
import streamlit.components.v1 as components
import requests
from bs4 import BeautifulSoup

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
    /* Das blendet das GitHub-Symbol und das Menü oben rechts aus */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
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

# --- FUNKTION: ZUSCHAUERREKORDE VON WEBSITE SCRAPEN ---
@st.cache_data(ttl=3600)
def scrape_zuschauerrekorde():
    try:
        response = requests.get("https://misterfutsal.de/zuschauerrekorde/", timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Finde die Tabelle
        table = soup.find('table')
        if not table:
            return pd.DataFrame()
        
        rows = []
        for tr in table.find_all('tr')[1:]:  # Überspringe Header
            tds = tr.find_all('td')
            if len(tds) >= 5:
                try:
                    rang = tds[0].text.strip()
                    datum = tds[1].text.strip()
                    partie = tds[2].text.strip()
                    ort = tds[3].text.strip()
                    zuschauer = int(tds[4].text.strip().replace('.', '').replace(',', ''))
                    
                    rows.append({
                        'RANG': int(rang),
                        'DATUM': datum,
                        'PARTIE': partie,
                        'HALLE': ort,
                        'ZUSCHAUER': zuschauer,
                        'QUELLE': 'misterfutsal.de'
                    })
                except (ValueError, AttributeError):
                    continue
        
        if rows:
            df = pd.DataFrame(rows)
            # Versuche Datum zu parsen
            df['DATUM'] = pd.to_datetime(df['DATUM'], format='%d.%m.%Y', errors='coerce')
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Fehler beim Scrapen der Zuschauerrekorde: {e}")
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
    st.image("banner_dashboard.png", width=600)
except: 
    st.title("⚽ Futsal Dashboard") 

st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")
st.divider()

# ==========================================
# 2. REITER / TABS
# ==========================================
tab_insta, tab_zuschauer, tab_rekorde = st.tabs(["📸 Instagram Follower", "🏟️ Bundesliga Zuschauer", "🏆 Zuschauer-Rekorde"])
with tab_insta:
    if not df_insta.empty:

        
        # ==========================================
        #               TAB 1: INSTAGRAM
        # ==========================================
        
        #df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        df_latest_display = df_latest.copy()

        # Entferne inaktive CLubs und speichere diese separat
        liste_ausschluss_inaktiv = [
            "Beton Boys ",
            "Futsal Dragons Augsburg",
        ]
        df_excluded = df_latest_display[df_latest_display['CLUB_NAME'].isin(liste_ausschluss_inaktiv)].copy()
        df_excluded.insert(0, 'RANG', range(1, len(df_excluded) + 1))
        df_excluded['RANG'] = df_excluded['RANG'].astype(str)
        df_excluded['FOLLOWER'] = df_excluded['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_excluded['STAND'] = df_excluded['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))
        

        # Sortiere Mainfraime
        df_latest_display = df_latest_display[~df_latest_display['CLUB_NAME'].isin(liste_ausschluss_inaktiv)]
        df_latest_display.insert(0, 'RANG', range(1, len(df_latest_display) + 1))
        df_latest_display['RANG'] = df_latest_display['RANG'].astype(str)
        df_latest_display['FOLLOWER'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_latest_display['STAND'] = df_latest_display['DATE'].apply(lambda x: x.strftime('%d.%m.%Y'))
        
        # --- TEIL 1: WACHSTUMSTRENDS ---
        latest_date_global = df_insta['DATE'].max()
        available_dates = sorted(df_insta['DATE'].unique())

        # STATE INITIALISIERUNG FÜR KLICK-EVENT
        if 'selected_club_from_chart' not in st.session_state:
            st.session_state.selected_club_from_chart = None

        # 🌟 Hier kommt dein Menü hin (ganz gerade eingerückt!):
        zeit_auswahl = st.selectbox(
            "Wähle deine Zeitreise",
            [
                "Letzte 14 Tage",
                "Letzte 30 Tage",
                "Letzte 60 Tage",
                "Letzte 90 Tage",
                # "Letztes Jahr",
                "Seit Datenaufzeichnung (15.01.2026)"
            ],
            index=0
        )

        # 📊 Berechne das Zeitfenster basierend auf die Auswahl
        def calculate_time_window(selection):
            if selection == "Letzte 30 Tage":
                return timedelta(days=30)
            elif selection == "Letzte 60 Tage":
                return timedelta(days=60)
            elif selection == "Letzte 14 Tage":
                return timedelta(days=14)
            elif selection == "Letzte 90 Tage":
                return timedelta(days=90)
            elif selection == "Letztes Jahr":
                return timedelta(days=365)
            else:  # "Seit Datenaufzeichnung"
                return None

        time_delta = calculate_time_window(zeit_auswahl)
        
        # Berechne das Zieldatum basierend auf das Zeitfenster
        if time_delta:
            target_date = latest_date_global - time_delta
        else:
            target_date = available_dates[0]  # Ältestes verfügbares Datum

        # Finde das nächstgelegene Datum in den Daten
        closest_old_date = min(available_dates, key=lambda x: abs((x - target_date).days))
        
        # Erstelle df_then basierend auf das gefilterte Datum
        df_then = df_insta[df_insta['DATE'] == closest_old_date][['CLUB_NAME', 'FOLLOWER']]
        df_trend = pd.merge(df_latest[['CLUB_NAME', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
        df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
        
        # Namen kürzen
        df_trend['CLUB_NAME_SHORT'] = df_trend['CLUB_NAME'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)
        
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
                title=f"🚀 Top 10 Gewinner Yes ({zeit_auswahl})",  # Überschrift ändert sich von Zauberhand! ✨
                color_discrete_sequence=['#00CC96'], 
                text='Zuwachs',
                custom_data=['CLUB_NAME'] 
            )
            
            # Layout aktualisieren
            fig_win.update_layout(
                yaxis={'categoryorder': 'total ascending', 'fixedrange': True},
                xaxis={'fixedrange': True},
                yaxis_title=None,
                clickmode='event+select',
                dragmode=False,
                margin=dict(l=0, r=0, t=40, b=0),
                uniformtext_minsize=14,
                uniformtext_mode='show'
            )
            
            fig_win.update_traces(
                textposition='auto',
                insidetextanchor='start',
                texttemplate='%{text}',
                textfont=dict(size=14),
                insidetextfont=dict(color='black'),
                outsidetextfont=dict(color='white'),
                textangle=0
            )
            
            # Event Listener
            event_win = st.plotly_chart(fig_win, use_container_width=True, on_select="rerun", selection_mode="points", key="chart_win")
            if handle_chart_selection(event_win):
                scroll_to_anchor()
        
        with top_row_col2:
            # Liste Ausschluss von Top Down
            liste_ausschluss_trend = [
               # 'DJK Würmtal Planegg',
                "Futsal Dragons Augsburg"
            ]
            
            # Geringstes Wachstum 
            fig_loss = px.bar(
                df_trend[~df_trend['CLUB_NAME'].isin(liste_ausschluss_trend)].sort_values(by='Zuwachs', ascending=True).head(10), 
                x='Zuwachs', y='CLUB_NAME_SHORT', 
                orientation='h', 
                title=f"📉 Geringstes Wachstum ({zeit_auswahl})", # Überschrift ändert sich von Zauberhand! ✨
                color_discrete_sequence=['#FF4B4B'], 
                text='Zuwachs',
                custom_data=['CLUB_NAME'] 
            )
            
            # Layout aktualisieren
            fig_loss.update_layout(
                yaxis={'categoryorder': 'total descending', 'fixedrange': True},
                xaxis={'fixedrange': True},
                yaxis_title=None,
                clickmode='event+select',
                dragmode=False,
                margin=dict(l=0, r=0, t=40, b=0),
                uniformtext_minsize=14,
                uniformtext_mode='show'
            )
            fig_loss.update_traces(
                textposition='auto',
                insidetextanchor='start',
                texttemplate='%{text}',
                textfont=dict(size=14),
                insidetextfont=dict(color='black'),
                outsidetextfont=dict(color='white'),
                textangle=-0
            )
            
            # Event Listener
            event_loss = st.plotly_chart(fig_loss, use_container_width=True, on_select="rerun", selection_mode="points", key="chart_loss")
            if handle_chart_selection(event_loss):
                scroll_to_anchor()
        
        st.divider()

        
        # =======================================================
        #             TEIL 2: TABELLEN & DETAILANALYSE 
        # =======================================================
        
        # 1. ANCHOR SETZEN
        st.markdown("<div id='ranking_anchor'></div>", unsafe_allow_html=True)
        
        row1_col1, row1_col2 = st.columns(2, gap="medium")
        #h_tables = 2150

        with row1_col1:
            st.subheader("🏆 Aktuelles Ranking")
            subtext = "Deutsche Futsal Seiten mit einer Aktivität innerhalb der letzten 6 Monate - für inaktive Profile siehe ganz unten"
            st.markdown(f"<span style='font-size: 14px; color: grey;'>{subtext}</span>", unsafe_allow_html=True)

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
                # plot_data = df_insta[df_insta['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                # fig_detail = px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', title="Vergleich der Vereine", markers=True)
                # st.plotly_chart(fig_detail, use_container_width=True)
                # Daten vorbereiten
                plot_data = df_insta[df_insta['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                
                # Plot erstellen
                fig_detail = px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', title="Vergleich der Vereine", markers=True)
                
                # 🛠️ Y-Achsen Puffer berechnen (damit der höchste Wert nicht oben "klebt")
                if not plot_data.empty:
                    y_max = plot_data['FOLLOWER'].max()
                    y_min = plot_data['FOLLOWER'].min()
                    # Puffer berechnen (z.B. 10% der Spannweite oben draufrechnen)
                    diff = y_max - y_min
                    if diff == 0: diff = y_max * 0.1 # Fallback, falls alle Werte gleich sind
                    
                    # Bereich manuell setzen: Unten etwas Luft, Oben 10% Luft für den nächsten Tick
                    y_range = [y_min - (diff * 0.05), y_max + (diff * 0.15)]
                    fig_detail.update_yaxes(range=y_range)
                
                # Layout Updates
                fig_detail.update_layout(
                    xaxis_title=None,       # 🚫 X-Titel ausblenden
                    xaxis=dict(
                        tickformat="%d.%m.%Y", # 📅 Format dd.mm.yyyy
                        fixedrange=True,        # 🔒 X-Zoom sperren
                        nticks=20,           # Erzwingt ca. 20 Markierungen
                        tickmode="auto",
                        tickangle=-45,
                        showgrid=False,       # ✅ Zeige das Gitter an
                        gridcolor='lightgray'   # 🩶 Farbe der Linien (Grau)
                    ),
                    yaxis=dict(
                        fixedrange=True        # 🔒 Y-Zoom sperren
                    ),
                    dragmode=False,            # 🔒 Ziehen verhindern
                    legend_title_text=None     # Optional: Legenden-Titel entfernen (sieht oft sauberer aus)
                )
                
                # Marker dürfen über die Achsen hinausgehen (verhindert halbe Kreise am Rand)
                fig_detail.update_traces(cliponaxis=False)
                
                # Anzeigen mit Konfiguration
                st.plotly_chart(
                    fig_detail, 
                    use_container_width=True,
                    config={
                        'displayModeBar': True, # ✅ Toolbar bleibt an (für Download)
                        'scrollZoom': False,    # 🚫 Mausrad deaktivieren
                        'displaylogo': False,   # 🚫 Plotly Logo weg
                        # Wir entfernen gezielt nur die Zoom/Pan-Buttons, lassen "Download" aber da:
                        'modeBarButtonsToRemove': [
                            'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'
                        ]
                    }
                )
            else: 
                st.info("💡 Klicke links in der Tabelle auf Zeilen oder oben auf das Diagramm, um den Verlauf zu sehen.")
        
        st.divider()

        
        # =======================================================
        #                TEIL 3: GESAMTENTWICKLUNG
        # =======================================================
        
        st.subheader("🌐 Gesamtentwicklung Deutschland")
        st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")
        
        # 1. Daten berechnen (unten 5% weniger, oben 5% mehr Platz)
        df_grouped = df_insta.groupby('DATE')['FOLLOWER'].sum().reset_index()
        y_min = df_grouped['FOLLOWER'].min() * 0.995
        y_max = df_grouped['FOLLOWER'].max() * 1.005
        
        # 2. Grafik erstellen
        fig_total = px.line(df_grouped, x='DATE', y='FOLLOWER', 
                            title="Summe aller Follower", markers=True, 
                            color_discrete_sequence=['#FFB200'])
        
        # 3. Y-Achse fest einstellen
        fig_total.update_yaxes(range=[y_min, y_max], tickformat=',d')
        
        # 4. In Streamlit anzeigen (Zoomen verboten!)
        st.plotly_chart(fig_total, use_container_width=True, config={
            'displayModeBar': True,        # Zeigt die Werkzeugleiste oben
            'scrollZoom': False,           # Mausrad-Zoom aus
            'staticPlot': False,           # Erlaubt Mouseover und Download
            'modeBarButtonsToRemove': [    # Entfernt alle Zoom-Knöpfe
                'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'
            ]
        })


        # =======================================================
        #        Teil 4: Ausgeschlossene Vereine anzeigen
        # =======================================================
        
        st.divider()
        st.subheader("🚫 Inaktive oder aussortierte Instagram Profile")
       # df_excluded = df_latest_display[df_latest_display['CLUB_NAME'].isin(liste_ausschluss_inaktiv)].copy()

        if not df_excluded.empty:
            df_excluded_display = df_excluded[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER', 'STAND']]
            excluded_styled = df_excluded_display.style.apply(highlight_selected_row, axis=1)
            excluded_selection = st.dataframe(
                excluded_styled,
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
                height=(len(df_excluded_display) + 1) * 35 + 3
            )
            
            # Detailanalyse für ausgeschlossene Vereine
            if excluded_selection and excluded_selection.selection.rows:
                sel_excluded_clubs = df_excluded_display.iloc[excluded_selection.selection.rows]['CLUB_NAME'].tolist()
                plot_data_ex = df_insta[df_insta['CLUB_NAME'].isin(sel_excluded_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                fig_detail_ex = px.line(plot_data_ex, x='DATE', y='FOLLOWER', color='CLUB_NAME', title="Vergleich der ausgeschlossenen Vereine", markers=True)
                
                # Layout wie im Hauptteil
                if not plot_data_ex.empty:
                    y_max = plot_data_ex['FOLLOWER'].max()
                    y_min = plot_data_ex['FOLLOWER'].min()
                    diff = y_max - y_min
                    if diff == 0: diff = y_max * 0.1
                    y_range = [y_min - (diff * 0.05), y_max + (diff * 0.15)]
                    fig_detail_ex.update_yaxes(range=y_range)
                
                fig_detail_ex.update_layout(
                    xaxis_title=None,
                    xaxis=dict(
                        tickformat="%d.%m.%Y",
                        fixedrange=True,
                        nticks=20,
                        tickmode="auto",
                        tickangle=-45,
                        showgrid=False,
                        gridcolor='lightgray'
                    ),
                    yaxis=dict(
                        fixedrange=True
                    ),
                    dragmode=False,
                    legend_title_text=None
                )
                
                fig_detail_ex.update_traces(cliponaxis=False)
                
                st.plotly_chart(
                    fig_detail_ex, 
                    use_container_width=True,
                    config={
                        'displayModeBar': True,
                        'scrollZoom': False,
                        'displaylogo': False,
                        'modeBarButtonsToRemove': [
                            'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d'
                        ]
                    }
                )
            else:
                st.info("💡 Klicke auf Zeilen in der Tabelle, um den Verlauf zu sehen.")
        else:
            st.info("Keine ausgeschlossenen Vereine in der aktuellen Datenbasis gefunden.")

    else:
        st.error("Instagram-Daten konnten nicht geladen werden.")

# --- TAB 2: ZUSCHAUER ---
with tab_zuschauer:
    df_z = load_data(ZUSCHAUER_SHEET_ID, "gcp_service_account")
    df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce')
    df_z = df_z[df_z['ZUSCHAUER'] > 0]

    if not df_z.empty:
        # Datum konvertieren
        if 'DATUM' in df_z.columns: 
            df_z['DATUM'] = pd.to_datetime(df_z['DATUM'], dayfirst=True, errors='coerce')
        # Zuschauer als Zahl garantie
        if 'ZUSCHAUER' in df_z.columns: 
            df_z['ZUSCHAUER'] = pd.to_numeric(df_z['ZUSCHAUER'], errors='coerce').fillna(0)
        # Spieltag falls vorhanden numerisch machen (wichtig für den Vergleich)
        if 'SPIELTAG' in df_z.columns:
            df_z['SPIELTAG'] = pd.to_numeric(df_z['SPIELTAG'], errors='coerce').fillna(0).astype(int)
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

                    # --- NEU: Vergleich aller Saisons bis zum gleichen Spieltag (Like-for-Like) ---
                    # Bestimme aktuellste Saison und deren höchsten Spieltag
                    if 'SAISON' in df_z.columns and 'SPIELTAG' in df_z.columns:
                        latest_season = df_z.loc[df_z['DATUM'].idxmax(), 'SAISON']
                        max_st_current = df_z[df_z['SAISON'] == latest_season]['SPIELTAG'].max()
                        # Guard gegen NaN
                        if pd.notna(max_st_current) and max_st_current > 0:
                            df_lfl = df_z[df_z['SPIELTAG'] <= max_st_current]
                            df_saison_lfl = df_lfl.groupby('SAISON')['ZUSCHAUER'].mean().reset_index()
                            if not df_saison_lfl.empty:
                                df_saison_lfl['COLOR'] = [farben_liste[i % 2] for i in range(len(df_saison_lfl))]
                                fig_saison_lfl = px.bar(
                                    df_saison_lfl,
                                    x='SAISON',
                                    y='ZUSCHAUER',
                                    text='ZUSCHAUER',
                                    title=f"Saisonschnitt bis Spieltag {int(max_st_current)} (Like-for-Like)",
                                )
                                fig_saison_lfl.update_traces(
                                    marker_color=df_saison_lfl['COLOR'],
                                    textposition='outside',
                                    texttemplate='%{text:.0f}'
                                )
                                fig_saison_lfl.update_layout(
                                    xaxis_title=None,
                                    yaxis_title=None,
                                    xaxis=dict(tickfont=dict(size=10), type='category'),
                                    yaxis=dict(range=[0,350]),
                                    hovermode="x unified"
                                )
                                st.plotly_chart(fig_saison_lfl, use_container_width=True)

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
                    st.markdown(f":grey[Hinweis: Spieltag 19 = Relegation; 20 = Viertelfinale; 21 = Halbfinale ; 22 = Finale]")
                    
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

# ==========================================
# 3. REITER: ZUSCHAUER-REKORDE
# ==========================================
with tab_rekorde:
    st.markdown("### 🏆 Futsal Zuschauer-Rekorde")
    st.markdown("Spiele sortiert nach Zuschauerzahl (absteigend)")
    st.divider()
    
    # Lade Daten von misterfutsal.de
    df_website = scrape_zuschauerrekorde()
    
    # Lade Daten aus Google Sheets (Zuschauertabelle)
    df_google = load_data(ZUSCHAUER_SHEET_ID, "gcp_service_account")
    
    # Verarbeite Google Sheets Daten
    if not df_google.empty:
        # Konvertiere Zuschauer zu numerisch
        if 'ZUSCHAUER' in df_google.columns:
            df_google['ZUSCHAUER'] = pd.to_numeric(df_google['ZUSCHAUER'], errors='coerce').fillna(0)
        
        if 'DATUM' in df_google.columns:
            df_google['DATUM'] = pd.to_datetime(df_google['DATUM'], dayfirst=True, errors='coerce')
        
        # Transformiere Google Sheets Daten
        df_google_transformed = df_google[['DATUM', 'HEIM', 'GAST', 'ZUSCHAUER']].copy()
        df_google_transformed.columns = ['DATUM', 'HEIM', 'GAST', 'ZUSCHAUER']
        df_google_transformed['PARTIE'] = df_google_transformed['HEIM'] + ' – ' + df_google_transformed['GAST']
        if 'HALLE' in df_google.columns:
            df_google_transformed['HALLE'] = df_google['HALLE']
        else:
            df_google_transformed['HALLE'] = ''
        df_google_transformed['QUELLE'] = 'Google Sheets (Bundesliga)'
        
        # Wähle relevante Spalten für df_google_transformed
        df_google_for_display = df_google_transformed[['DATUM', 'PARTIE', 'HALLE', 'ZUSCHAUER', 'QUELLE']].copy()
    else:
        df_google_for_display = pd.DataFrame()
    
    # Kombiniere beide Datenquellen
    if not df_website.empty and not df_google_for_display.empty:
        df_website_for_display = df_website[['DATUM', 'PARTIE', 'HALLE', 'ZUSCHAUER', 'QUELLE']].copy()
        df_combined = pd.concat([df_website_for_display, df_google_for_display], ignore_index=True)
    elif not df_website.empty:
        df_combined = df_website[['DATUM', 'PARTIE', 'HALLE', 'ZUSCHAUER', 'QUELLE']].copy()
    elif not df_google_for_display.empty:
        df_combined = df_google_for_display
    else:
        df_combined = pd.DataFrame()
    
    if not df_combined.empty:
        # Entferne Duplikate: Behalte misterfutsal.de Einträge bei (diese sind zuerst)
        df_combined = df_combined.drop_duplicates(subset=['DATUM', 'PARTIE'], keep='first').reset_index(drop=True)
        
        # Sortiere nach Zuschauern (absteigend)
        df_combined = df_combined.sort_values('ZUSCHAUER', ascending=False).reset_index(drop=True)
        df_combined['RANG'] = range(1, len(df_combined) + 1)
        
        # Formatiere Datum und Zuschauer für Anzeige
        df_display = df_combined.copy()
        df_display['DATUM_STR'] = df_display['DATUM'].dt.strftime('%d.%m.%Y')
        df_display['ZUSCHAUER_STR'] = df_display['ZUSCHAUER'].apply(lambda x: f"{int(x):,}".replace(',', '.') if pd.notna(x) else '-')
        
        # Zeige Tabelle
        display_cols = ['RANG', 'DATUM_STR', 'PARTIE', 'HALLE', 'ZUSCHAUER_STR']
        df_table = df_display[display_cols].copy()
        df_table.columns = ['Rang', 'Datum', 'Partie', 'Halle', 'Zuschauer']
        
        # Berechne Tabellenhohe um alle Zeilen anzuzeigen (Header + Zeilen)
        table_height = 35 + (len(df_table) * 35)  # Header + ~35px pro Zeile
        st.dataframe(df_table, use_container_width=True, hide_index=True, height=table_height)
    else:
        st.warning("Keine Zuschauer-Rekorde konnten geladen werden.")



































