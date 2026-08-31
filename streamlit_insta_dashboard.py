"""
German Futsal Statistics Dashboard – Mister Futsal
==================================================

Optimierte Fassung. Wesentliche Änderungen gegenüber der Vorversion:

1.  google-auth statt des deprecateten oauth2client.
2.  Retry mit exponentiellem Backoff auf transiente Google-Fehler (429/5xx).
    Fehler werden NICHT mehr gecached – ein einzelner 503 legt das Dashboard
    nicht länger für eine Stunde still.
3.  gspread-Client liegt in @st.cache_resource, nicht mehr pro Aufruf neu.
4.  Alle Sheet-Zugriffe laufen einmal zentral, Tab 2 und Tab 3 teilen sich
    denselben geladenen DataFrame (spart Requests gegen das Quota).
5.  Leere DataFrames werden konsequent VOR dem Spaltenzugriff abgefangen.
6.  Plotly-Config, Achsen-Locking und Detailcharts als wiederverwendbare
    Helfer – der Code war an vier Stellen nahezu identisch dupliziert.
"""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import gspread
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

# ==========================================================================
# KONFIGURATION
# ==========================================================================

INSTA_SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"
ZUSCHAUER_SHEET_ID = "14puepYtteWGPD1Qv89gCpZijPm5Yrgr8glQnGBh3PXM"
REKORDE_URL = "https://misterfutsal.de/zuschauerrekorde/"
BANNER_PATH = Path("banner_dashboard.png")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

CACHE_TTL = 3600
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 4

# Vereine, die im Hauptranking nicht auftauchen sollen
INAKTIVE_CLUBS = [
    "Beton Boys",
    "Futsal Dragons Augsburg",
    "Longericher SC",
    "MSV Bonner Lions",
]

# Vereine, die aus dem "Geringstes Wachstum"-Chart fliegen
AUSSCHLUSS_TREND = [
    "Futsal Dragons Augsburg",
    "TSV Neuried",
]

ZEITRAEUME = {
    "Letzte 14 Tage": timedelta(days=14),
    "Letzte 30 Tage": timedelta(days=30),
    "Letzte 60 Tage": timedelta(days=60),
    "Letzte 90 Tage": timedelta(days=90),
    "Seit Datenaufzeichnung (15.01.2026)": None,
}

SAISON_FARBEN = ["#FFD700", "#0057B8"]

# Zoom-/Pan-Buttons raus, Download bleibt drin
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "scrollZoom": False,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
    ],
}

st.set_page_config(page_title="Futsal Statistik Dashboard", layout="wide")

# ==========================================================================
# STYLING
# ==========================================================================

st.markdown(
    """
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 10px; background-color: transparent; padding-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { height: 30px; background-color: #FFFFFF; border: 2px solid #D3D3D3; border-radius: 0px; padding: 0px 10px; color: #31333F; font-weight: 100; transition: all 0.3s ease; }
    .stTabs [data-baseweb="tab"]:hover { border-color: #0047AB; background-color: #E8F0FE; color: #0047AB; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #0047AB; border: 2px solid #0047AB; color: #FFFFFF !important; box-shadow: 0px 4px 6px rgba(0, 71, 171, 0.3); }
    .stTabs [data-baseweb="tab"][aria-selected="true"] p { color: #FFFFFF !important; font-size: 18px; font-weight: bold; }
    div[data-baseweb="select"] > div { background-color: #FDFDFD; border: 2px solid #0047AB; border-radius: 8px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1); }
    div[data-baseweb="select"] * { color: #0047AB !important; }
    .stSelectbox label p { font-size: 18px !important; color: #0047AB !important; font-weight: 800 !important; margin-bottom: 5px; }
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================================
# HELFER
# ==========================================================================


def fmt_de(value) -> str:
    """1234567 -> '1.234.567'."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "-"


def scroll_to_anchor() -> None:
    components.html(
        """
        <script>
            var el = document.getElementById('ranking_anchor');
            if (el) { el.scrollIntoView({behavior: "smooth", block: "start"}); }
        </script>
        """,
        height=0,
    )


def lock_axes(fig, tickangle: int = -45):
    """Zoom/Pan sperren + einheitliches Datumsformat auf der X-Achse."""
    fig.update_layout(
        xaxis_title=None,
        xaxis=dict(
            tickformat="%d.%m.%Y",
            fixedrange=True,
            nticks=20,
            tickmode="auto",
            tickangle=tickangle,
            showgrid=False,
            gridcolor="lightgray",
        ),
        yaxis=dict(fixedrange=True),
        dragmode=False,
        legend_title_text=None,
    )
    fig.update_traces(cliponaxis=False)
    return fig


def add_y_padding(fig, series: pd.Series, low: float = 0.05, high: float = 0.15):
    """Verhindert, dass der höchste Punkt am oberen Rand klebt."""
    if series.empty:
        return fig
    y_max, y_min = series.max(), series.min()
    diff = y_max - y_min
    if diff == 0:
        diff = y_max * 0.1 or 1
    fig.update_yaxes(range=[y_min - diff * low, y_max + diff * high])
    return fig


def render_verlauf(df_source: pd.DataFrame, clubs: list[str], title: str) -> None:
    """Detailchart für eine Auswahl von Vereinen (vorher 2x dupliziert)."""
    plot_data = df_source[df_source["CLUB_NAME"].isin(clubs)].sort_values(
        ["CLUB_NAME", "DATE"]
    )
    if plot_data.empty:
        st.info("Für die Auswahl liegen keine Verlaufsdaten vor.")
        return

    fig = px.line(
        plot_data,
        x="DATE",
        y="FOLLOWER",
        color="CLUB_NAME",
        title=title,
        markers=True,
    )
    add_y_padding(fig, plot_data["FOLLOWER"])
    lock_axes(fig)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)


# ==========================================================================
# DATENZUGRIFF
# ==========================================================================


@st.cache_resource(show_spinner=False)
def get_gspread_client(secret_key: str) -> gspread.Client:
    """Client einmal pro Session aufbauen statt bei jedem Sheet-Zugriff."""
    creds = Credentials.from_service_account_info(
        dict(st.secrets[secret_key]), scopes=SCOPES
    )
    return gspread.authorize(creds)


@st.cache_data(ttl=CACHE_TTL, show_spinner="Lade Daten …")
def load_data(sheet_id: str, secret_key: str) -> pd.DataFrame:
    """
    Liest Blatt 1 eines Sheets.

    Wichtig: bei dauerhaftem Fehlschlag wird eine Exception GEWORFEN, kein
    leeres DataFrame zurückgegeben. Nur so verhindert st.cache_data, dass ein
    einmaliger 503 für die gesamte TTL festgeschrieben wird.
    """
    client = get_gspread_client(secret_key)
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            worksheet = client.open_by_key(sheet_id).get_worksheet(0)
            values = worksheet.get_all_values()
            if not values:
                return pd.DataFrame()

            header = [str(c).strip().upper() for c in values[0]]
            # Doppelte Spaltennamen eindeutig machen, sonst kippt pandas
            seen: dict[str, int] = {}
            unique_header = []
            for col in header:
                if col in seen:
                    seen[col] += 1
                    unique_header.append(f"{col}_{seen[col]}")
                else:
                    seen[col] = 0
                    unique_header.append(col)

            return pd.DataFrame(values[1:], columns=unique_header)

        except APIError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in RETRY_STATUS and attempt < MAX_RETRIES - 1:
                last_error = exc
                time.sleep(2**attempt)  # 1s, 2s, 4s
                continue
            raise  # 401/403 etc. sofort durchreichen

    raise last_error  # type: ignore[misc]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def scrape_zuschauerrekorde() -> pd.DataFrame:
    """Rekordtabelle von misterfutsal.de. Fehler hier sind nicht kritisch."""
    response = requests.get(REKORDE_URL, timeout=10)
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.content, "html.parser")

    table = soup.find("table")
    if not table:
        return pd.DataFrame()

    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        try:
            rows.append(
                {
                    "RANG": int(tds[0].text.strip()),
                    "DATUM": tds[1].text.strip(),
                    "PARTIE": tds[2].text.strip(),
                    "HALLE": tds[3].text.strip(),
                    "ZUSCHAUER": int(
                        tds[4].text.strip().replace(".", "").replace(",", "")
                    ),
                    "QUELLE": "misterfutsal.de",
                }
            )
        except (ValueError, AttributeError):
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["DATUM"] = pd.to_datetime(df["DATUM"], format="%d.%m.%Y", errors="coerce")
    return df


def safe_load(sheet_id: str, secret_key: str, label: str) -> pd.DataFrame | None:
    """Wrapper mit Fehleranzeige und Retry-Button."""
    try:
        return load_data(sheet_id, secret_key)
    except Exception as exc:  # noqa: BLE001 – bewusst breit, UI-Ebene
        st.error(f"{label} konnten nicht geladen werden: {exc}")
        if st.button("🔄 Erneut versuchen", key=f"retry_{sheet_id}"):
            st.cache_data.clear()
            st.rerun()
        return None


# ==========================================================================
# AUFBEREITUNG INSTAGRAM
# ==========================================================================


def prepare_insta(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "DATE" in out.columns:
        out["DATE"] = pd.to_datetime(out["DATE"], errors="coerce").dt.date
    out["FOLLOWER"] = pd.to_numeric(out["FOLLOWER"], errors="coerce").fillna(0)
    out = out.dropna(subset=["DATE"])
    out = out.sort_values(["CLUB_NAME", "DATE"]).drop_duplicates(
        subset=["CLUB_NAME", "DATE"], keep="last"
    )
    return out


def build_ranking(df_latest: pd.DataFrame) -> pd.DataFrame:
    out = df_latest.copy()
    out.insert(0, "RANG", range(1, len(out) + 1))
    out["RANG"] = out["RANG"].astype(str)
    out["FOLLOWER_FMT"] = out["FOLLOWER"].apply(fmt_de)
    out["STAND"] = out["DATE"].apply(lambda d: d.strftime("%d.%m.%Y"))
    return out


# ==========================================================================
# HEADER
# ==========================================================================

df_insta_raw = safe_load(INSTA_SHEET_ID, "gcp_service_account", "Instagram-Daten")
df_insta = prepare_insta(df_insta_raw) if df_insta_raw is not None else pd.DataFrame()

if not df_insta.empty:
    df_latest = (
        df_insta.sort_values("DATE")
        .groupby("CLUB_NAME")
        .last()
        .reset_index()
        .sort_values("FOLLOWER", ascending=False)
    )
    summe_follower = fmt_de(df_latest["FOLLOWER"].sum())
    akt_datum = df_insta["DATE"].max().strftime("%d.%m.%Y")
else:
    df_latest = pd.DataFrame()
    summe_follower, akt_datum = "0", "-"

if BANNER_PATH.exists():
    st.image(str(BANNER_PATH), width=600)
else:
    st.title("⚽ Futsal Dashboard")

st.markdown(
    f"[www.misterfutsal.de](https://www.misterfutsal.de) | :grey[Stand {akt_datum}]"
)
st.divider()

tab_insta, tab_zuschauer, tab_rekorde = st.tabs(
    ["📸 Instagram Follower", "🏟️ Bundesliga Zuschauer", "🏆 Zuschauer-Rekorde"]
)

# ==========================================================================
# TAB 1: INSTAGRAM
# ==========================================================================

with tab_insta:
    if df_insta.empty:
        st.info("Keine Instagram-Daten verfügbar.")
    else:
        st.session_state.setdefault("selected_club_from_chart", None)

        maske_inaktiv = df_latest["CLUB_NAME"].str.strip().isin(INAKTIVE_CLUBS)
        df_ranking = build_ranking(df_latest[~maske_inaktiv])
        df_excluded = build_ranking(df_latest[maske_inaktiv])

        # ---------- Teil 1: Wachstumstrends ----------
        latest_date_global = df_insta["DATE"].max()
        available_dates = sorted(df_insta["DATE"].unique())

        zeit_auswahl = st.selectbox(
            "Wähle deine Zeitreise", list(ZEITRAEUME.keys()), index=0
        )
        time_delta = ZEITRAEUME[zeit_auswahl]
        target_date = (
            latest_date_global - time_delta if time_delta else available_dates[0]
        )
        closest_old_date = min(available_dates, key=lambda d: abs((d - target_date).days))

        df_then = df_insta.loc[
            df_insta["DATE"] == closest_old_date, ["CLUB_NAME", "FOLLOWER"]
        ]
        df_trend = df_latest[["CLUB_NAME", "FOLLOWER"]].merge(
            df_then, on="CLUB_NAME", suffixes=("_neu", "_alt")
        )
        df_trend["Zuwachs"] = df_trend["FOLLOWER_neu"] - df_trend["FOLLOWER_alt"]
        df_trend["CLUB_NAME_SHORT"] = df_trend["CLUB_NAME"].apply(
            lambda x: x[:20] + "..." if len(x) > 20 else x
        )

        def handle_chart_selection(event_data) -> bool:
            """Robust gegen Objekt- und Dict-Rückgabe von st.plotly_chart."""
            if not event_data:
                return False
            try:
                points = event_data.selection.points
            except AttributeError:
                try:
                    points = event_data["selection"]["points"]
                except (KeyError, TypeError):
                    return False
            if not points or "customdata" not in points[0]:
                return False
            name = points[0]["customdata"][0]
            if st.session_state.selected_club_from_chart != name:
                st.session_state.selected_club_from_chart = name
                return True
            return False

        def trend_chart(data: pd.DataFrame, title: str, color: str, ascending: bool):
            fig = px.bar(
                data,
                x="Zuwachs",
                y="CLUB_NAME_SHORT",
                orientation="h",
                title=title,
                color_discrete_sequence=[color],
                text="Zuwachs",
                custom_data=["CLUB_NAME"],
            )
            fig.update_layout(
                yaxis={
                    "categoryorder": "total ascending" if ascending else "total descending",
                    "fixedrange": True,
                },
                xaxis={"fixedrange": True},
                yaxis_title=None,
                clickmode="event+select",
                dragmode=False,
                margin=dict(l=0, r=0, t=40, b=0),
                uniformtext_minsize=14,
                uniformtext_mode="show",
            )
            fig.update_traces(
                textposition="auto",
                insidetextanchor="start",
                texttemplate="%{text}",
                textfont=dict(size=14),
                insidetextfont=dict(color="black"),
                outsidetextfont=dict(color="white"),
                textangle=0,
            )
            return fig

        col_win, col_loss = st.columns(2, gap="medium")

        with col_win:
            fig_win = trend_chart(
                df_trend.nlargest(10, "Zuwachs"),
                f"🚀 Top 10 Gewinner ({zeit_auswahl})",
                "#00CC96",
                ascending=True,
            )
            if handle_chart_selection(
                st.plotly_chart(
                    fig_win,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="points",
                    key="chart_win",
                )
            ):
                scroll_to_anchor()

        with col_loss:
            fig_loss = trend_chart(
                df_trend[~df_trend["CLUB_NAME"].isin(AUSSCHLUSS_TREND)].nsmallest(
                    10, "Zuwachs"
                ),
                f"📉 Geringstes Wachstum ({zeit_auswahl})",
                "#FF4B4B",
                ascending=False,
            )
            if handle_chart_selection(
                st.plotly_chart(
                    fig_loss,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="points",
                    key="chart_loss",
                )
            ):
                scroll_to_anchor()

        st.divider()

        # ---------- Teil 2: Tabellen & Detailanalyse ----------
        st.markdown("<div id='ranking_anchor'></div>", unsafe_allow_html=True)

        def highlight_selected_row(row):
            marked = st.session_state.selected_club_from_chart
            if marked and row["CLUB_NAME"] == marked:
                return ["background-color: #ffeeba; color: black; font-weight: bold"] * len(row)
            return [""] * len(row)

        COLUMN_CONFIG = {
            "RANG": st.column_config.TextColumn("Rang"),
            "URL": st.column_config.LinkColumn(
                "Instagram", display_text=r"https://www.instagram.com/([^/?#]+)"
            ),
            "FOLLOWER_FMT": st.column_config.TextColumn("Follower"),
            "STAND": st.column_config.TextColumn("Stand"),
        }
        VIEW_COLS = ["RANG", "CLUB_NAME", "URL", "FOLLOWER_FMT", "STAND"]

        row_col1, row_col2 = st.columns(2, gap="medium")

        with row_col1:
            st.subheader("🏆 Aktuelles Ranking")
            st.markdown(
                "<span style='font-size: 14px; color: grey;'>Deutsche Futsal-Seiten mit "
                "Aktivität innerhalb der letzten 6 Monate – inaktive Profile siehe ganz "
                "unten</span>",
                unsafe_allow_html=True,
            )

            if st.session_state.selected_club_from_chart:
                st.info(
                    f"👉 Markiert: **{st.session_state.selected_club_from_chart}** "
                    "(ggf. in der Liste scrollen)"
                )
                if st.button("Markierung aufheben"):
                    st.session_state.selected_club_from_chart = None
                    st.rerun()
            else:
                st.markdown("👇 :yellow[Hier Vereine für Detailanalyse selektieren]")

            df_view = df_ranking[VIEW_COLS]
            selection = st.dataframe(
                df_view.style.apply(highlight_selected_row, axis=1),
                column_config=COLUMN_CONFIG,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                use_container_width=True,
                height=(len(df_view) + 1) * 35 + 3,
            )

        with row_col2:
            st.subheader("🔍 Detailanalyse")

            sel_clubs: list[str] = []
            if selection and selection.selection.rows:
                sel_clubs = df_ranking.iloc[selection.selection.rows]["CLUB_NAME"].tolist()

            marked = st.session_state.selected_club_from_chart
            if marked and marked not in sel_clubs:
                sel_clubs.append(marked)

            if sel_clubs:
                render_verlauf(df_insta, sel_clubs, "Vergleich der Vereine")
            else:
                st.info(
                    "💡 Klicke links in der Tabelle auf Zeilen oder oben auf das "
                    "Diagramm, um den Verlauf zu sehen."
                )

        st.divider()

        # ---------- Teil 3: Gesamtentwicklung ----------
        st.subheader("🌐 Gesamtentwicklung Deutschland")
        st.markdown(f"##### Deutschland gesamt: :yellow[**{summe_follower}**]")

        df_grouped = df_insta.groupby("DATE")["FOLLOWER"].sum().reset_index()
        fig_total = px.line(
            df_grouped,
            x="DATE",
            y="FOLLOWER",
            title="Summe aller Follower",
            markers=True,
            color_discrete_sequence=["#FFB200"],
        )
        fig_total.update_yaxes(
            range=[
                df_grouped["FOLLOWER"].min() * 0.995,
                df_grouped["FOLLOWER"].max() * 1.005,
            ],
            tickformat=",d",
        )
        st.plotly_chart(fig_total, use_container_width=True, config=PLOTLY_CONFIG)

        # ---------- Teil 4: Inaktive Profile ----------
        st.divider()
        st.subheader("🚫 Inaktive oder aussortierte Instagram-Profile")

        if df_excluded.empty:
            st.info("Keine ausgeschlossenen Vereine in der aktuellen Datenbasis gefunden.")
        else:
            df_ex_view = df_excluded[VIEW_COLS]
            ex_selection = st.dataframe(
                df_ex_view.style.apply(highlight_selected_row, axis=1),
                column_config=COLUMN_CONFIG,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                use_container_width=True,
                height=(len(df_ex_view) + 1) * 35 + 3,
            )

            if ex_selection and ex_selection.selection.rows:
                render_verlauf(
                    df_insta,
                    df_ex_view.iloc[ex_selection.selection.rows]["CLUB_NAME"].tolist(),
                    "Vergleich der ausgeschlossenen Vereine",
                )
            else:
                st.info("💡 Klicke auf Zeilen in der Tabelle, um den Verlauf zu sehen.")

# ==========================================================================
# ZUSCHAUERDATEN (einmal laden, von Tab 2 und Tab 3 genutzt)
# ==========================================================================


def prepare_zuschauer(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "ZUSCHAUER" not in df.columns:
        return pd.DataFrame()

    out = df.copy()
    out["ZUSCHAUER"] = pd.to_numeric(out["ZUSCHAUER"], errors="coerce").fillna(0)

    if "DATUM" in out.columns:
        out["DATUM"] = pd.to_datetime(out["DATUM"], dayfirst=True, errors="coerce")
    if "SPIELTAG" in out.columns:
        out["SPIELTAG"] = (
            pd.to_numeric(out["SPIELTAG"], errors="coerce").fillna(0).astype(int)
        )
    if "AVERAGE_SPIELTAG" in out.columns:
        out["AVERAGE_SPIELTAG"] = pd.to_numeric(
            out["AVERAGE_SPIELTAG"], errors="coerce"
        ).fillna(0)

    def get_season(d):
        if pd.isnull(d):
            return "Unbekannt"
        return f"{d.year}/{d.year + 1}" if d.month >= 7 else f"{d.year - 1}/{d.year}"

    if "SAISON" not in out.columns:
        if "SEASON" in out.columns:
            out["SAISON"] = out["SEASON"]
        elif "DATUM" in out.columns:
            out["SAISON"] = out["DATUM"].apply(get_season)
        else:
            out["SAISON"] = "Unbekannt"

    return out


df_z_raw = safe_load(ZUSCHAUER_SHEET_ID, "gcp_service_account", "Zuschauer-Daten")
df_z_all = prepare_zuschauer(df_z_raw) if df_z_raw is not None else pd.DataFrame()

# ==========================================================================
# TAB 2: BUNDESLIGA ZUSCHAUER
# ==========================================================================

with tab_zuschauer:
    df_z = df_z_all[df_z_all["ZUSCHAUER"] > 0] if not df_z_all.empty else pd.DataFrame()

    if df_z.empty or "HEIM" not in df_z.columns:
        st.info("Keine Zuschauer-Daten verfügbar.")
    else:
        unique_seasons = sorted(s for s in df_z["SAISON"].unique() if s != "Unbekannt")
        color_map = {
            s: SAISON_FARBEN[i % 2] for i, s in enumerate(unique_seasons)
        }

        LIGA_OPTION = "🇩🇪 Liga-Gesamtentwicklung (Spieltag-Schnitt)"
        auswahl = st.selectbox(
            "Wähle einen Verein aus:",
            [LIGA_OPTION] + sorted(df_z["HEIM"].unique()),
            key="vereins_auswahl",
        )

        def saison_bar(data: pd.DataFrame, title: str):
            fig = px.bar(
                data, x="SAISON", y="ZUSCHAUER", text="ZUSCHAUER", title=title
            )
            fig.update_traces(
                marker_color=[SAISON_FARBEN[i % 2] for i in range(len(data))],
                textposition="outside",
                texttemplate="%{text:.0f}",
            )
            fig.update_layout(
                xaxis_title=None,
                yaxis_title=None,
                xaxis=dict(tickfont=dict(size=10), type="category"),
                yaxis=dict(range=[0, 350]),
                hovermode="x unified",
            )
            return fig

        if auswahl == LIGA_OPTION:
            df_saison = df_z.groupby("SAISON")["ZUSCHAUER"].mean().reset_index()
            if not df_saison.empty:
                st.plotly_chart(
                    saison_bar(df_saison, "Saisonschnitt Bundesliga gesamt"),
                    use_container_width=True,
                )

            # Like-for-Like: alle Saisons nur bis zum aktuell erreichten Spieltag
            if {"SPIELTAG", "DATUM"}.issubset(df_z.columns) and df_z["DATUM"].notna().any():
                latest_season = df_z.loc[df_z["DATUM"].idxmax(), "SAISON"]
                max_st = df_z.loc[df_z["SAISON"] == latest_season, "SPIELTAG"].max()
                if pd.notna(max_st) and max_st > 0:
                    df_lfl = (
                        df_z[df_z["SPIELTAG"] <= max_st]
                        .groupby("SAISON")["ZUSCHAUER"]
                        .mean()
                        .reset_index()
                    )
                    if not df_lfl.empty:
                        st.plotly_chart(
                            saison_bar(
                                df_lfl,
                                f"Saisonschnitt bis Spieltag {int(max_st)} (Like-for-Like)",
                            ),
                            use_container_width=True,
                        )

            cols = ["DATUM", "SAISON", "SPIELTAG", "AVERAGE_SPIELTAG"]
            if all(c in df_z.columns for c in cols):
                df_helper = (
                    df_z[cols]
                    .drop_duplicates(subset=["SAISON", "SPIELTAG"])
                    .sort_values("DATUM")
                    .copy()
                )
                # Kollidierende Termine um einen Tag versetzen, damit die
                # kategoriale X-Achse keine Balken überlagert
                doppelt = df_helper.duplicated(subset=["DATUM"], keep="first")
                df_helper.loc[doppelt, "DATUM"] -= pd.Timedelta(days=1)

                if not df_helper.empty:
                    fig_trend = px.bar(
                        df_helper,
                        x="DATUM",
                        y="AVERAGE_SPIELTAG",
                        color="SAISON",
                        text="AVERAGE_SPIELTAG",
                        title="Zuschauerschnitt im Saisonvergleich (nach Spieltag)",
                        color_discrete_map=color_map,
                    )
                    fig_trend.update_layout(
                        xaxis_title=None,
                        yaxis_title=None,
                        xaxis=dict(
                            type="category",
                            tickmode="array",
                            tickvals=df_helper["DATUM"],
                            ticktext=df_helper["SPIELTAG"],
                            tickangle=-45,
                            tickfont=dict(size=10),
                        ),
                        hovermode="x unified",
                    )
                    fig_trend.update_traces(textposition="outside")
                    st.plotly_chart(fig_trend, use_container_width=True)
                    st.markdown(
                        ":grey[Hinweis: Spieltag 19 = Relegation; 20 = Viertelfinale; "
                        "21 = Halbfinale; 22 = Finale]"
                    )
            else:
                st.warning(
                    "Die Spalten SAISON, SPIELTAG und AVERAGE_SPIELTAG fehlen im Datensatz."
                )

        else:
            team_data = df_z[df_z["HEIM"] == auswahl].sort_values("DATUM").copy()
            st.markdown(f"### Entwicklung: {auswahl}")

            stats_saison = team_data.groupby("SAISON")["ZUSCHAUER"].mean().reset_index()
            stats_saison.columns = ["Saison", "Ø Zuschauer"]
            stats_saison["Ø Zuschauer"] = stats_saison["Ø Zuschauer"].round(0).astype(int)

            fig_avg = px.bar(
                stats_saison,
                x="Saison",
                y="Ø Zuschauer",
                text="Ø Zuschauer",
                title="Durchschnittliche Zuschauer pro Saison",
                color="Saison",
                color_discrete_map=color_map,
            )
            fig_avg.update_traces(textposition="outside")
            fig_avg.update_layout(
                xaxis=dict(fixedrange=True),
                yaxis=dict(
                    fixedrange=True,
                    range=[0, stats_saison["Ø Zuschauer"].max() * 1.25],
                    nticks=10,
                    exponentformat="none",
                ),
                margin=dict(b=100),
            )
            st.plotly_chart(fig_avg, use_container_width=True)

            team_data["X_LABEL"] = team_data.apply(
                lambda r: f"{r['DATUM'].strftime('%d.%m.%Y')} (ST {int(r['SPIELTAG'])})"
                if pd.notna(r["DATUM"])
                else "-",
                axis=1,
            )
            fig_team = px.bar(
                team_data,
                x="X_LABEL",
                y="ZUSCHAUER",
                text="ZUSCHAUER",
                color="SAISON",
                color_discrete_map=color_map,
                title=f"Alle Heimspiele von {auswahl}",
            )
            fig_team.update_traces(textposition="outside")
            fig_team.update_layout(
                xaxis=dict(fixedrange=True),
                xaxis_tickangle=-45,
                yaxis_range=[0, team_data["ZUSCHAUER"].max() * 1.25],
                yaxis=dict(fixedrange=True, nticks=10, exponentformat="none"),
                margin=dict(b=100),
            )
            st.plotly_chart(fig_team, use_container_width=True)

# ==========================================================================
# TAB 3: ZUSCHAUER-REKORDE
# ==========================================================================

with tab_rekorde:
    st.markdown("### 🏆 Futsal Zuschauer-Rekorde")
    st.markdown("Spiele sortiert nach Zuschauerzahl (absteigend)")
    st.divider()

    try:
        df_website = scrape_zuschauerrekorde()
    except Exception as exc:  # noqa: BLE001
        st.warning(f"misterfutsal.de nicht erreichbar ({exc}) – zeige nur Sheet-Daten.")
        df_website = pd.DataFrame()

    REKORD_COLS = ["DATUM", "PARTIE", "HALLE", "ZUSCHAUER", "QUELLE"]
    frames = []

    if not df_website.empty:
        frames.append(df_website[REKORD_COLS])

    if not df_z_all.empty and {"HEIM", "GAST"}.issubset(df_z_all.columns):
        df_g = df_z_all.copy()
        df_g["PARTIE"] = df_g["HEIM"] + " – " + df_g["GAST"]
        if "HALLE" not in df_g.columns:
            df_g["HALLE"] = ""
        df_g["QUELLE"] = "Google Sheets (Bundesliga)"
        frames.append(df_g[REKORD_COLS])

    if not frames:
        st.warning("Keine Zuschauer-Rekorde konnten geladen werden.")
    else:
        df_combined = (
            pd.concat(frames, ignore_index=True)
            .drop_duplicates(subset=["DATUM", "PARTIE"], keep="first")
            .sort_values("ZUSCHAUER", ascending=False)
            .reset_index(drop=True)
        )
        df_combined["RANG"] = range(1, len(df_combined) + 1)

        df_table = pd.DataFrame(
            {
                "Rang": df_combined["RANG"],
                "Datum": df_combined["DATUM"].dt.strftime("%d.%m.%Y"),
                "Partie": df_combined["PARTIE"],
                "Halle": df_combined["HALLE"],
                "Zuschauer": df_combined["ZUSCHAUER"].apply(fmt_de),
            }
        )
        st.dataframe(
            df_table,
            use_container_width=True,
            hide_index=True,
            height=35 + len(df_table) * 35,
        )
