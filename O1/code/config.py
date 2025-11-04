import json
import os
import logging

def load_config():
    """
    Load the main configuration from a JSON file.

    By default, it looks for 'config.json' in the 'data' directory relative to this file's location.
    You can override the path using the 'CONFIG_PATH' environment variable.

    Expected 'config.json' Structure (example):
    {
      "data_path": "C:/Valuebet/O1/data",
      "cert_path": "C:/Valuebet/O1/certificates",
      "credentials_path": "credentials.json",
      "fuzzy_threshold": 80,
      "common_filler_words": ["and", "or", "the", "a", "an", "v"],
      "sport_event_type_ids": {
        "football": "1",
        "nba": "7522",
        "nfl": "6423",
        "nhl": "7524"
      },
      "market_name_to_types": {
        "match odds": ["MATCH_ODDS"]
        // ...other mappings
      }
    }

    If the file is missing, a FileNotFoundError is raised.
    If keys are missing, defaults are applied where possible.

    Consider adding validation or defaults for all keys if needed.

    :return: A dictionary containing all the loaded configurations.
    """
    # Default to looking inside the 'data' directory for config.json
    default_path = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")
    config_path = os.environ.get("CONFIG_PATH", default_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()

DATA_PATH = config.get("data_path", "C:/Valuebet/O1/data")
CERT_PATH = config.get("cert_path", "C:/Valuebet/O1/certificates")
CREDENTIALS_PATH = os.path.join(DATA_PATH, config.get("credentials_path", "credentials.json"))

# Parsing and Fuzzy Matching Config
FUZZY_THRESHOLD = config.get("fuzzy_threshold", 80)
COMMON_FILLER_WORDS = set(config.get("common_filler_words", ["and", "or", "the", "a", "an", "v"]))

# Sport Event Type IDs
SPORT_EVENT_TYPE_IDS = config.get("sport_event_type_ids", {
    "football": "1",
    "nba": "7522",
    "nfl": "6423",
    "nhl": "7524"
})

# Market Name to Types Mapping
MARKET_NAME_TO_TYPES = config.get("market_name_to_types", {
    "match odds": ["MATCH_ODDS"]
})

def load_markets_data():
    """
    Load market definitions from 'markets.json' in DATA_PATH.
    This file is expected to define each market, its aliases, and metadata.

    If the file is missing, logs a warning and returns an empty dictionary.
    If it's malformed, logs an error and returns empty.

    :return: A dictionary representing markets data, or empty if not found or invalid.
    """
    markets_file = os.path.join(DATA_PATH, "markets.json")
    if not os.path.exists(markets_file):
        logging.warning(f"markets.json not found at {markets_file}. Returning empty market data.")
        return {}
    try:
        with open(markets_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading markets data: {e}. Returning empty.")
        return {}

def load_teams_data():
    """
    Load team definitions from 'teams.json' in DATA_PATH.
    This file typically contains each team, its sport, and aliases.

    If the file is missing, logs a warning and returns an empty dictionary.
    If it's malformed, logs an error and returns empty.

    :return: A dictionary representing teams data, or empty if not found or invalid.
    """
    teams_file = os.path.join(DATA_PATH, "teams.json")
    if not os.path.exists(teams_file):
        logging.warning(f"teams.json not found at {teams_file}. Returning empty teams data.")
        return {}
    try:
        with open(teams_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading teams data: {e}. Returning empty.")
        return {}
