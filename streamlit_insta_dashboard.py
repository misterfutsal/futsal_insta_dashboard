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

# --- HILFSFUNKTION FÜR DEZIMALZAHLEN ---
def clean_numeric(series):
    """Konvertiert deutsche Dezimal-Strings (mit Komma) korrekt in Floats."""
    return pd.to_numeric(series.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

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
        st.error(f"Fehler: {e}")
        return pd.DataFrame()

# ==========================================
# 1. DATEN-VORBEREITUNG
# ==========================================
df_insta = load_data(INSTA_SHEET_ID, "gcp_service_account")
if not df_insta.empty:
    if 'DATE' in df_insta.columns: df_insta['DATE'] = pd.to_datetime(df_insta['DATE']).dt.date
    df_insta['FOLLOWER'] = clean_numeric(df_insta['FOLLOWER'])
    df_insta = df_insta.sort_values(by=['CLUB_NAME', 'DATE']).drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')
    # Konto-Name auf 20 Zeichen kürzen
    df_insta['CLUB_NAME_SHORT'] = df_insta['CLUB_NAME'].str[:20]
    
    df_latest = df_insta.sort_values('DATE').groupby('CLUB_NAME').last().reset_index().sort_values(by='FOLLOWER', ascending=False)
    summe_follower = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    akt_datum = df_insta['DATE'].max().strftime('%d.%m.%Y')
else:
    summe_follower, akt_datum = "0", "-"

try: st.image("banner_statistik_dashboard.png", width=450)
except: st.title("⚽ Futsal Dashboard") 
st.markdown(f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]")
st.divider()

# ==========================================
# 2. TABS
# ==========================================
tab_insta, tab_zuschauer = st.tabs(["📸 Instagram Dashboard", "🏟️ Zuschauer Dashboard"])

with tab_insta:
    if not df_insta.empty:
        df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))
        df_latest_display = df_latest.copy()
        df_latest_display['FOLLOWER_FORMAT'] = df_latest_display['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        
        row1_col1, row1_col2 = st.columns(2, gap="medium")
        with row1_col1:
            st.subheader("🏆 Aktuelles Ranking")
            selection = st.dataframe(df_latest_display[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER_FORMAT']], 
                column_config={"URL": st.column_config.LinkColumn("Instagram")}, hide_index=True, on_select="rerun", selection_mode="multi-row", use_container_width=True, height=600)
        
        with row1_col2:
            st.subheader("🔍 Detailanalyse")
            if selection and selection.selection.rows:
                sel_clubs = df_latest.iloc[selection.selection.rows]['CLUB_NAME'].tolist()
                plot_data = df_insta[df_insta['CLUB_NAME'].isin(sel_clubs)].sort_values(['CLUB_NAME', 'DATE'])
                st.plotly_chart(px.line(plot_data, x='DATE', y='FOLLOWER', color='CLUB_NAME', markers=True), use_container_width=True)
            else: st.info("💡 Wähle Vereine in der Tabelle aus.")

        st.divider()
        row2_col1, row2_col2 = st.columns(2, gap="medium")
        with row2_col1:
            st.subheader("📈 Wachstumstrends (4 Wochen)")
            # Trendberechnung
            latest_date = df_insta['DATE'].max()
            df_then = df_insta[df_insta['DATE'] == (latest_date - timedelta(weeks=4))][['CLUB_NAME', 'FOLLOWER']]
            df_trend = pd.merge(df_latest[['CLUB_NAME', 'CLUB_NAME_SHORT', 'FOLLOWER']], df_then, on='CLUB_NAME', suffixes=('_neu', '_alt'))
            df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']
            
            # Instagram Balkendiagramme (Beschriftung links im Balken, horizontal)
            for title, data, color in [("🚀 Top 10 Gewinner", df_trend.sort_values('Zuwachs', ascending=False).head(10), '#00CC96'), 
                                       ("📉 Geringstes Wachstum", df_trend.sort_values('Zuwachs', ascending=True).head(10), '#FF4B4B')]:
                fig = px.bar(data, x='Zuwachs', y='CLUB_NAME_SHORT', orientation='h', title=title, text='Zuwachs', color_discrete_sequence=[color])
                fig.update_traces(textposition='inside', insidetextanchor='start') # Links im Balken
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title=None, yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True)

        with row2_col2:
            st.subheader("🌐 Gesamtentwicklung")
            st.markdown(f"##### Gesamt: :yellow[**{summe_follower}**]")
            st.plotly_chart(px.line(df_insta.groupby('DATE')['FOLLOWER'].sum().reset_index(), x='DATE', y='FOLLOWER', markers=True, color_discrete_sequence=['#FFB200']), use_container_width=True)

with tab_zuschauer:
    st.header("🏟️ Zuschauer-Statistiken")
    df_z = load_data(ZUSCHAUER_SHEET_ID, "gcp_service_account")
    if not df_z.empty:
        # Zahlenbereinigung (Komma zu Punkt)
        for col in ['ZUSCHAUER', 'AVERAGE_SPIELTAG']:
            if col in df_z.columns: df_z[col] = clean_numeric(df_z[col])
        
        if 'DATUM' in df_z.columns: df_z['DATUM'] = pd.to_datetime(df_z['DATUM'], dayfirst=True, errors='coerce')
        if 'SAISON' not in df_z.columns: df_z['SAISON'] = df_z['DATUM'].apply(lambda d: f"{d.year}/{d.year+1}" if d.month >= 7 else f"{d.year-1}/{d.year}" if pd.notnull(d) else "Unbekannt")

        options = ["🇩🇪 Liga-Gesamtentwicklung"] + sorted(df_z['HEIM'].unique())
        auswahl = st.selectbox("Analyse wählen:", options)

        if "Liga-Gesamtentwicklung" in auswahl:
            df_helper = df_z[['SAISON', 'SPIELTAG', 'AVERAGE_SPIELTAG']].drop_duplicates(subset=['SAISON', 'SPIELTAG']).sort_values(['SAISON', 'SPIELTAG'])
            # Zuschauer Balken: Beschriftung DRÜBER (outside)
            fig = px.bar(df_helper, x='SPIELTAG', y='AVERAGE_SPIELTAG', color='SAISON', barmode='group', text='AVERAGE_SPIELTAG', title="Ø Zuschauer pro Spieltag")
            fig.update_traces(textposition='outside') # Beschriftung über den Balken
            st.plotly_chart(fig, use_container_width=True)
        else:
            team_data = df_z[df_z['HEIM'] == auswahl].sort_values('DATUM')
            team_data['LABEL'] = team_data['DATUM'].dt.strftime('%d.%m')
            fig_team = px.bar(team_data, x='LABEL', y='ZUSCHAUER', text='ZUSCHAUER', color='SAISON', title=f"Spiele: {auswahl}")
            fig_team.update_traces(textposition='outside')
            st.plotly_chart(fig_team, use_container_width=True)
