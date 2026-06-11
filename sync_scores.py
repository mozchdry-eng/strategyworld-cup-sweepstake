#!/usr/bin/env python3
"""
Fetches finished World Cup 2026 matches from football-data.org and writes
a scores.json file that the front-end reads.  Runs as a GitHub Action.
"""

import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone

API_KEY  = os.environ.get("FOOTBALL_API_KEY", "")
API_URL  = "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED"

ROUND_ORDER = [
    "Group Stage",
    "Round of 32",
    "Round of 16",
    "Quarter-final",
    "Semi-final",
    "Runner-up",
    "Winner",
]

TEAM_NAME_MAP = {
    "United States":            "USA",
    "IR Iran":                  "Iran",
    "Korea Republic":           "South Korea",
    "Cote d'Ivoire":            "Côte d'Ivoire",
    "Côte d'Ivoire":            "Côte d'Ivoire",
    "Bosnia and Herzegovina":   "Bosnia & Herz.",
    "Bosnia-Herzegovina":       "Bosnia & Herz.",
    "Cape Verde":               "Cabo Verde",
    "Congo DR":                 "DR Congo",
}

def normalise(name):
    return TEAM_NAME_MAP.get(name, name) if name else ""

def stage_to_round(stage):
    if not stage:
        return None
    s = stage.upper()
    if s == "FINAL":
        return "Runner-up"          # both finalists; winner promoted below
    if "SEMI" in s:
        return "Semi-final"
    if "QUARTER" in s:
        return "Quarter-final"
    if "ROUND_OF_16" in s or "LAST_16" in s:
        return "Round of 16"
    if "ROUND_OF_32" in s or "LAST_32" in s:
        return "Round of 32"
    return None

def fetch_matches():
    req = urllib.request.Request(API_URL, headers={"X-Auth-Token": API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)

def build_team_status(matches):
    reached = {}   # team -> round string

    def promote(team, round_str):
        if not team or not round_str:
            return
        cur_idx = ROUND_ORDER.index(reached[team]) if team in reached else -1
        new_idx = ROUND_ORDER.index(round_str)
        if new_idx > cur_idx:
            reached[team] = round_str

    for m in matches:
        stage  = m.get("stage", "")
        round_ = stage_to_round(stage)
        if not round_:
            continue

        home   = normalise(m.get("homeTeam", {}).get("name"))
        away   = normalise(m.get("awayTeam", {}).get("name"))
        winner = (m.get("score") or {}).get("winner")  # HOME_TEAM | AWAY_TEAM | DRAW

        # Both teams reached this round
        promote(home, round_)
        promote(away, round_)

        # Winner advances one further
        if winner in ("HOME_TEAM", "AWAY_TEAM"):
            winner_team = home if winner == "HOME_TEAM" else away
            next_idx = ROUND_ORDER.index(round_) + 1
            if next_idx < len(ROUND_ORDER):
                promote(winner_team, ROUND_ORDER[next_idx])

    return reached

def main():
    if not API_KEY:
        print("FOOTBALL_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    data    = fetch_matches()
    matches = data.get("matches", [])
    status  = build_team_status(matches)

    output = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "teamStatus":  status,
    }

    with open("scores.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Written scores.json — {len(status)} teams with progress")

if __name__ == "__main__":
    main()
