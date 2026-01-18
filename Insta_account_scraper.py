import instaloader
import pandas as pd
import time
import random
import re
import gspread
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

#Erstelle Session ID für Instagram Zugang
session_id = os.getenv("INSTAGRAM_SESSION_ID")
if session_id:
    # Nutze das Session-Cookie, um sich als eingeloggter User auszugeben
    L.context._session.cookies.set("sessionid", session_id)
    print("✅ Login via Session-ID erfolgreich.")
    
# ================= CONFIGURATION =================
SHEET_ID = "1_Ni1ALTrq3qkgXxgBaG2TNjRBodCEaYewhhTPq0aWfU"

# Liste der Instagram URLs
insta_urls = [
    "https://www.instagram.com/ybbalkan/",
    "https://www.instagram.com/tsvweilimdorf/",
    "https://www.instagram.com/tsg1846_futsal/",
    "https://www.instagram.com/fcg.futsal/",
    "https://www.instagram.com/preussen06futsal/",
    "https://www.instagram.com/mchfutsalclub/",
    "https://www.instagram.com/futsaliciousessen/",
    "https://www.instagram.com/wuppertaler_sv_futsal/",
    "https://www.instagram.com/ffmg07_furious_futsal/",
    "https://www.instagram.com/futsaliciousessen/", # Dublette entfernt falls nötig
    "https://www.instagram.com/futsalpantherskoeln/",
    "https://www.instagram.com/karlsruherscfutsal/",
    "https://www.instagram.com/jahnfutsal/",
    "https://www.instagram.com/fcregensburg/",
    "https://www.instagram.com/futsal_munich_tsv_neuried/",
    "https://www.instagram.com/fc.liria.1985.futsal/",
    "https://www.instagram.com/ufk08/",
    "https://www.instagram.com/eintrachtsuedring.futsal/",
    "https://www.instagram.com/spbarrio96/",
    "https://www.instagram.com/fcstpfutsal/",
    "https://www.instagram.com/futsal_hamburg/",
    "https://www.instagram.com/h96futsal/",
    "https://www.instagram.com/futsalnbg/",
    "https://www.instagram.com/hot05futsal/",
    "https://www.instagram.com/osc_04_futsal/",
    "https://www.instagram.com/hsvfutsal/",
    "https://www.instagram.com/asc_futsal/",
    "https://www.instagram.com/sv_pars/",
    "https://www.instagram.com/sv98_futsal/",
    "https://www.instagram.com/futsal_allgaeu/",
    "https://www.instagram.com/fc_niederrhein_soccer_futsal/",
    "https://www.instagram.com/sf_doenbergfutsal/",
    "https://www.instagram.com/betonboysmunchen.e.v/",
    "https://www.instagram.com/futsal.tvherbeck/",
    "https://www.instagram.com/futsalfalken/",
    "https://www.instagram.com/fc_mattheck_moers/",
    "https://www.instagram.com/blunited.futsal/",
    "https://www.instagram.com/alemanniaaachen_futsal/",
    "https://www.instagram.com/mitteldeutscher_futsalclub/",
    "https://www.instagram.com/fussball.gtsvffm1908/",
    "https://www.instagram.com/pcfmuelheim/",
    "https://www.instagram.com/holzpfostenschwerte/",
    "https://www.instagram.com/nk_zagreb_dortmund_futsal/",
    "https://www.instagram.com/alhuda98.futsal/",
    "https://www.instagram.com/rsc.futsal/",
    "https://www.instagram.com/ljiljanihamburg/",
    "https://www.instagram.com/hamburgergsv.fussball/",
    "https://www.instagram.com/croatia.hamburg.futsal/",
    "https://www.instagram.com/blackforestfutsal/",
    "https://www.instagram.com/afgbergstrasse/",
    "https://www.instagram.com/futsalclubfrankfurt/",
    "https://www.instagram.com/futsalclubbiberach/",
    "https://www.instagram.com/futsalclubusora/",
    "https://www.instagram.com/gsvaugsburg1934/",
    "https://www.instagram.com/atleticoerlangen/",
    "https://www.instagram.com/gsc_regensburg/",
    "https://www.instagram.com/futsal_dragons_augsburg/",
    "https://www.instagram.com/dfb.futsal/",
    "https://www.instagram.com/dfb.u19.futsal.westfalen/",
    "https://www.instagram.com/mister.futsal/"
]

def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Prüfen, ob wir in der Cloud (GitHub Actions) oder lokal sind
    creds_json = os.getenv("GOOGLE_SHEETS_CREDS")
    
    if creds_json:
        # GitHub Actions Modus: Nutzt das Secret
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Lokaler Modus: Nutzt deine Datei auf dem PC
        local_path = r"C:\Users\Daniel\Dropbox\Mister Futsal\User-Auswertung\futsal-instagram-stats-credentioals.json"
        creds = ServiceAccountCredentials.from_json_keyfile_name(local_path, scope)
        
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

def extract_username(url):
    match = re.search(r"instagram\.com/([^/?]+)", url)
    return match.group(1) if match else None

# --- SCRAPING PROZESS ---
print(f"[{datetime.now().strftime('%H:%M:%S')}] Starte Scraper...")

try:
    sheet = get_google_sheet()
    all_data = sheet.get_all_records()
    df_cloud = pd.DataFrame(all_data)
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    urls_already_done_today = []

    if not df_cloud.empty:
        # Spaltennamen auf Großschreibung normalisieren zur Sicherheit
        df_cloud.columns = [str(c).strip().upper() for c in df_cloud.columns]
        # Suche nach heutigen Einträgen
        if 'DATE' in df_cloud.columns:
            df_today = df_cloud[df_cloud['DATE'].astype(str).str.strip() == today_date]
            urls_already_done_today = df_today['URL'].str.strip().tolist()

    urls_to_scrape = [url for url in insta_urls if url.strip() not in urls_already_done_today]

    print(f"ℹ️ Gesamt: {len(insta_urls)} | Heute bereits erledigt: {len(urls_already_done_today)}")
    print(f"🚀 Verbleibende Abrufe: {len(urls_to_scrape)}")

    if not urls_to_scrape:
        print("✅ Alles aktuell.")
    else:
        L = instaloader.Instaloader()
        new_rows = []

        for i, url in enumerate(urls_to_scrape, 1):
            username = extract_username(url)
            if not username: continue

            success = False
            attempts = 0
            while attempts < 2 and not success:
                try:
                    print(f"[{i}/{len(urls_to_scrape)}] @{username}...")
                    profile = instaloader.Profile.from_username(L.context, username)
                    
                    new_rows.append([
                        today_date,
                        profile.full_name,
                        f"@{username}",
                        profile.followers,
                        url.strip()
                    ])
                    success = True
                    time.sleep(random.uniform(10, 30)) # Sicherheits-Pause
                    
                except Exception as e:
                    attempts += 1
                    print(f"⚠️ Fehler bei {username}: {e}. Versuch {attempts}/2...")
                    time.sleep(60)

        if new_rows:
            print(f"Schreibe {len(new_rows)} Zeilen...")
            sheet.append_rows(new_rows)
            # Sortierung (Datum absteigend, Follower absteigend)
            sheet.sort((1, 'des'), (4, 'des'), range='A2:E50000')
            print("✅ Erfolgreich aktualisiert.")

except Exception as e:
    print(f"❌ KRITISCHER FEHLER: {e}")

print("FERTIG!")

