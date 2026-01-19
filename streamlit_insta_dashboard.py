import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import timedelta

# --- Einstellungen ---
SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"

st.set_page_config(page_title="Futsal Insta-Analytics", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    """Holt die Daten aus Google Sheets und macht sie sauber."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open_by_key(SHEET_ID).sheet1
    df = pd.DataFrame(sheet.get_all_records())
    
    # Namen hübsch machen
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Datum und Zahlen richtig einstellen
    if 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE']).dt.date
    df['FOLLOWER'] = pd.to_numeric(df['FOLLOWER'], errors='coerce').fillna(0)
    
    return df.sort_values(by=['CLUB_NAME', 'DATE']).drop_duplicates(subset=['CLUB_NAME', 'DATE'], keep='last')

def style_chart(fig):
    """Macht die Diagramme schick: Kein X-Achsen-Titel und sauberes Datum."""
    fig.update_xaxes(title_text=None, tickformat="%d.%m.%Y")
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig

try:
    df = load_data()
    df_latest = df.sort_values('DATE').groupby('CLUB_NAME').last().reset_index()
    df_latest = df_latest.sort_values(by='FOLLOWER', ascending=False)
    df_latest.insert(0, 'RANG', range(1, len(df_latest) + 1))

    # Kopfbereich
    col_logo, col_titel = st.columns([1, 5])
    with col_logo:
        st.image("logo_instagram_dashboard.png", width=250)
    with col_titel:
        st.title("Mister Futsal - Instagram Dashboard")

    summe = f"{int(df_latest['FOLLOWER'].sum()):,}".replace(",", ".")
    st.markdown(f"##### Gesamt Follower: :yellow[**{summe}**]")
    st.divider()

    # Obere Reihe: Tabelle und Details
    row1_left, row1_right = st.columns(2, gap="medium")

    with row1_left:
        st.subheader("🏆 Aktuelles Ranking")
        df_disp = df_latest.copy()
        df_disp['FOLLOWER'] = df_disp['FOLLOWER'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        
        selection = st.dataframe(
            df_disp[['RANG', 'CLUB_NAME', 'URL', 'FOLLOWER']],
            column_config={
                "URL": st.column_config.LinkColumn("Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"),
            },
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            use_container_width=True,
            height=400
        )

    with row1_right:
        st.subheader("🔍 Detailanalyse")
        if selection and selection.selection.rows:
            club = df_latest.iloc[selection.selection.rows[0]]['CLUB_NAME']
            chart_data = df[df['CLUB_NAME'] == club]
            fig = px.line(chart_data, x='DATE', y='FOLLOWER', title=f"Verlauf: {club}", markers=True)
            st.plotly_chart(style_chart(fig), use_container_width=True)
        else:
            st.info("💡 Klicke links auf einen Verein!")

    st.divider()

    # Untere Reihe: Trends
    row2_left, row2_right = st.columns(2, gap="medium")

    with row2_left:
        st.subheader("📈 Wachstumstrends")
        target_date = df['DATE'].max() - timedelta(weeks=4)
        old_date = min(df['DATE'].unique(), key=lambda x: abs(x - target_date))
        
        df_trend = pd.merge(
            df_latest[['CLUB_NAME', 'FOLLOWER']], 
            df[df['DATE'] == old_date][['CLUB_NAME', 'FOLLOWER']], 
            on='CLUB_NAME', suffixes=('_neu', '_alt')
        )
        df_trend['Zuwachs'] = df_trend['FOLLOWER_neu'] - df_trend['FOLLOWER_alt']

        # Gewinner
        top10 = df_trend.sort_values('Zuwachs', ascending=False).head(10)
        fig_up = px.bar(top10, x='Zuwachs', y='CLUB_NAME', orientation='h', title="🚀 Top Gewinner", text='Zuwachs')
        fig_up.update_traces(textangle=0, textposition='inside')
        st.plotly_chart(fig_up, use_container_width=True)

    with row2_right:
        st.subheader("🌐 Gesamtentwicklung")
        total_growth = df.groupby('DATE')['FOLLOWER'].sum().reset_index()
        fig_all = px.line(total_growth, x='DATE', y='FOLLOWER', title="Alle Follower zusammen", markers=True)
        st.plotly_chart(style_chart(fig_all), use_container_width=True)

except Exception as e:
    st.error(f"Oje, da ist etwas schiefgelaufen: {e}")
