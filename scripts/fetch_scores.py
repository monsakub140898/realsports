import os
import requests
from datetime import datetime, timedelta
import libsql_experimental as libsql

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")

def init_db(cursor):
    # 1. สร้างตารางถ้ายังไม่มี
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            home_team TEXT,
            away_team TEXT,
            home_score INTEGER,
            away_score INTEGER,
            status TEXT,
            league_name TEXT,
            match_date TEXT,
            match_time TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS standings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league_code TEXT,
            league_name TEXT,
            position INTEGER,
            team_name TEXT,
            played INTEGER,
            won INTEGER,
            draw INTEGER,
            lost INTEGER,
            points INTEGER,
            goals_for INTEGER,
            goals_against INTEGER
        )
    """)

    # 2. ป้องกัน Error โดยการสั่งเพิ่มคอลัมน์ match_date และ match_time หากตารางเดิมยังไม่มี
    try:
        cursor.execute("ALTER TABLE matches ADD COLUMN match_date TEXT")
    except Exception:
        pass  # ถ้ามีคอลัมน์อยู่แล้วให้ข้ามไป

    try:
        cursor.execute("ALTER TABLE matches ADD COLUMN match_time TEXT")
    except Exception:
        pass  # ถ้ามีคอลัมน์อยู่แล้วให้ข้ามไป

def fetch_and_save_data():
    if not (TURSO_DATABASE_URL and TURSO_AUTH_TOKEN and FOOTBALL_API_KEY):
        print("Missing required environment variables.")
        return

    conn = libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    cursor = conn.cursor()
    init_db(cursor)

    headers = {"X-Auth-Token": FOOTBALL_API_KEY}

    # ดึงข้อมูลแมตช์ (ย้อนหลัง 1 วัน ถึง ล่วงหน้า 1 วัน)
    today = datetime.utcnow().date()
    date_from = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    matches_url = f"https://api.football-data.org/v4/matches?dateFrom={date_from}&dateTo={date_to}"
    resp = requests.get(matches_url, headers=headers)
    
    if resp.status_code == 200:
        matches = resp.json().get("matches", [])
        for m in matches:
            utc_date = m["utcDate"] # e.g. "2026-09-01T18:00:00Z"
            m_date = utc_date.split("T")[0]
            m_time = utc_date.split("T")[1][:5]

            cursor.execute("""
                INSERT INTO matches (id, home_team, away_team, home_score, away_score, status, league_name, match_date, match_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    home_score=excluded.home_score,
                    away_score=excluded.away_score,
                    status=excluded.status,
                    match_date=excluded.match_date,
                    match_time=excluded.match_time
            """, (
                m["id"],
                m["homeTeam"]["name"],
                m["awayTeam"]["name"],
                m["score"]["fullTime"]["home"],
                m["score"]["fullTime"]["away"],
                m["status"],
                m["competition"]["name"],
                m_date,
                m_time
            ))
        print(f"Updated {len(matches)} matches successfully.")

    # ดึงตารางคะแนน 5 ลีกหลัก
    leagues = [
        ('PL', 'Premier League'),
        ('PD', 'La Liga'),
        ('BL1', 'Bundesliga'),
        ('SA', 'Serie A'),
        ('FL1', 'Ligue 1')
    ]
    
    cursor.execute("DELETE FROM standings")

    for code, name in leagues:
        standings_url = f"https://api.football-data.org/v4/competitions/{code}/standings"
        resp = requests.get(standings_url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            table = data.get("standings", [])[0].get("table", []) if data.get("standings") else []
            for row in table:
                cursor.execute("""
                    INSERT INTO standings (league_code, league_name, position, team_name, played, won, draw, lost, points, goals_for, goals_against)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    code, name, row["position"], row["team"]["name"],
                    row["playedGames"], row["won"], row["draw"], row["lost"],
                    row["points"], row["goalsFor"], row["goalsAgainst"]
                ))

    conn.commit()

if __name__ == "__main__":
    fetch_and_save_data()
