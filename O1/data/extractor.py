import json
import re
from fuzzywuzzy import fuzz
import os

# Determine the script's directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEAMS_JSON_PATH = os.path.join(BASE_DIR, "teams.json")
MATCHES_DATA_PATH = os.path.join(BASE_DIR, "matches.txt")

def normalize_text(t: str) -> str:
    return t.strip().lower()

def load_teams():
    try:
        with open(TEAMS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_teams(teams_data):
    # Sort alphabetically by key
    sorted_teams = dict(sorted(teams_data.items(), key=lambda x: x[0]))
    with open(TEAMS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted_teams, f, ensure_ascii=False, indent=4)

def team_exists(teams_data, team_name):
    for canonical_name, data in teams_data.items():
        if fuzz.ratio(team_name, canonical_name) == 100:
            return canonical_name
        for alias in data.get("aliases", []):
            if fuzz.ratio(team_name, normalize_text(alias)) == 100:
                return canonical_name
    return None

def add_or_update_team(teams_data, team_name, sport):
    norm_name = normalize_text(team_name)
    existing_team_key = team_exists(teams_data, norm_name)
    if existing_team_key:
        aliases_lower = [normalize_text(a) for a in teams_data[existing_team_key].get("aliases", [])]
        if team_name.lower() not in aliases_lower:
            teams_data[existing_team_key]["aliases"].append(team_name)
        return

    teams_data[norm_name] = {
        "sport": sport,
        "aliases": [team_name]
    }

def clean_team_name(name: str) -> str:
    name = name.strip()
    # If (W) is at the end, keep it as is
    if name.endswith("(W)"):
        return name
    # Otherwise, remove trailing info in parentheses or multiple spaces
    cleaned_name = re.split(r"\s{2,}|\(", name)[0].strip()
    return cleaned_name

def parse_line_for_teams(line: str):
    line = line.strip()

    if " v " in line:
        parts = line.split(" v ")
    elif " @" in line:
        parts = line.split(" @ ")
    else:
        return None, None

    if len(parts) == 2:
        home_team = clean_team_name(parts[0])
        away_team = clean_team_name(parts[1])
        return home_team, away_team

    return None, None

def main():
    sport = input("Enter the sport for the teams (e.g. 'football', 'nba'): ").strip().lower()

    teams_data = load_teams()

    with open(MATCHES_DATA_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        home_team, away_team = parse_line_for_teams(line)
        if home_team and away_team:
            add_or_update_team(teams_data, home_team, sport)
            add_or_update_team(teams_data, away_team, sport)

    save_teams(teams_data)
    print("Teams updated and saved successfully!")

if __name__ == "__main__":
    main()
