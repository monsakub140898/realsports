import os
import requests
import libsql_experimental as libsql

# ดึงค่า Secrets จาก Environment Variables
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")

def fetch_and_save_matches():
    if not ALL_SECRETS_PRESENT():
        print("Missing required environment variables.")
        return

    # ยิง API ดึงข้อมูลผลบอล
    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"API Error: {response.status_code}")
        return

    data = response.json()
    matches = data.get("matches", [])

    # เชื่อมต่อ Database บน Turso
    conn = libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    cursor = conn.cursor()

    # สร้างตารางถ้ายังไม่มี
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            status TEXT,
            league_name TEXT,
            match_time TEXT
        )
    """)

    # อัปเดตข้อมูลแมตช์
    for match in matches:
        cursor.execute("""
            INSERT INTO matches (id, home_team, away_team, home_score, away_score, status, league_name, match_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                home_score=excluded.home_score,
                away_score=excluded.away_score,
                status=excluded.status
        """, (
            match["id"],
            match["homeTeam"]["name"],
            match["awayTeam"]["name"],
            match["score"]["fullTime"]["home"],
            match["score"]["fullTime"]["away"],
            match["status"],
            match["competition"]["name"],
            match["utcDate"]
        ))

    conn.commit()
    print(f"Successfully updated {len(matches)} matches.")

def ALL_SECRETS_PRESENT():
    return TURSO_DATABASE_URL and TURSO_AUTH_TOKEN and FOOTBALL_API_KEY

if __name__ == "__main__":
    fetch_and_save_matches()
