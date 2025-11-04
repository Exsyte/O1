import os
import json
import logging
from config import DATA_PATH  # Import DATA_PATH from config.py

class DataManager:
    """
    Manages teams, players, and markets data, allowing loading, saving, and lookups by aliases.
    
    Although this file is named 'fuzzy_matcher.py', the current code is identical to DataManager functionality.
    Once the actual fuzzy matching logic is introduced or corrected, consider:
      - Integrating fuzzy matching functions here.
      - Or renaming the file to reflect its purpose.
    
    Current responsibilities:
      - Load data (teams, markets, players) from JSON files.
      - Add new teams, markets, players, and save them.
      - Lookup by aliases.
    
    Potential Future Improvements:
      - Move fuzzy matching logic (once implemented) into this file or a helper function.
      - Separate data loading/saving from business logic for better testability.
      - Introduce domain classes (Team, Market, Player) for validation and richer domain logic.
    """

    def __init__(self):
        logging.debug("Initializing DataManager (fuzzy_matcher placeholder).")
        self.teams = {}
        self.players = {}
        self.markets = {}
        self.load_all()

    def load_all(self):
        """
        Load all data (teams, markets, players) from JSON files in DATA_PATH.
        
        Uses _safe_load_json to handle missing or malformed files gracefully.
        After loading, sets self.teams, self.markets, self.players as dicts.
        """
        logging.debug("Loading all data (teams, markets, players) in fuzzy_matcher.py (currently DataManager logic).")
        self.teams = self._safe_load_json("teams.json") or {}
        self.markets = self._safe_load_json("markets.json") or {}

        players_file = os.path.join(DATA_PATH, "players.json")
        self.players = self._safe_load_json("players.json") if os.path.exists(players_file) else {}
        logging.debug("Data loaded. Teams: %d, Markets: %d, Players: %d",
                      len(self.teams), len(self.markets), len(self.players))

    def _safe_load_json(self, filename: str):
        """
        Safely load JSON data from a given filename in DATA_PATH.
        
        :param filename: Name of the JSON file (e.g., 'teams.json').
        :return: The loaded data as a dict, or {} if file not found or invalid.
        """
        filepath = os.path.join(DATA_PATH, filename)
        logging.debug(f"Attempting to load JSON data from {filepath}")
        if not os.path.exists(filepath):
            logging.warning(f"File {filename} not found at {filepath}. Returning empty data.")
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            logging.debug(f"Loaded {len(data)} items from {filename}")
            return data
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON in file {filename}: {e}")
            return {}
        except Exception as e:
            logging.error(f"Unexpected error loading {filename}: {e}")
            return {}

    def _safe_save_json(self, filename: str, data: dict):
        """
        Safely save the dictionary 'data' to a JSON file in DATA_PATH.
        
        Logs errors if saving fails. Data may be partially saved if one file fails.
        
        :param filename: The name of the file to save to.
        :param data: The dictionary to save.
        """
        filepath = os.path.join(DATA_PATH, filename)
        logging.debug(f"Attempting to save JSON data to {filepath}")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logging.debug(f"Successfully saved {len(data)} items to {filename}")
        except Exception as e:
            logging.error(f"Failed to save {filename}: {e}")

    def save_all(self):
        """
        Save all data (teams, markets, players) to their respective JSON files.
        
        If any save fails, logs an error but continues attempting to save others.
        """
        logging.debug("Saving all data (teams, markets, players).")
        self._safe_save_json("teams.json", self.teams)
        self._safe_save_json("markets.json", self.markets)
        self._safe_save_json("players.json", self.players)

    def add_team(self, team_name: str, sport: str, aliases: list = None):
        """
        Add a new team and save changes.
        
        :param team_name: The canonical team name.
        :param sport: The sport of the team. Consider sport mandatory for clarity.
        :param aliases: Optional list of aliases for the team.
        """
        team_name = team_name.lower().strip()
        if not aliases:
            aliases = []
        if team_name not in self.teams:
            self.teams[team_name] = {
                "sport": sport,
                "aliases": aliases
            }
            logging.debug(f"Added new team: {team_name} (Sport: {sport}, Aliases: {aliases})")
            self.save_all()

    def add_market(self, market_name: str, sport: str, mtype: str, aliases: list = None):
        """
        Add a new market and save changes.
        
        :param market_name: The canonical market name (e.g., 'match odds').
        :param sport: The sport this market belongs to.
        :param mtype: The market type code (e.g., 'MATCH_ODDS').
        :param aliases: Optional list of aliases for the market.
        """
        market_name = market_name.lower().strip()
        if not aliases:
            aliases = []
        if market_name not in self.markets:
            if market_name not in aliases:
                aliases.append(market_name)
            self.markets[market_name] = {
                "sport": sport,
                "aliases": aliases,
                "type": mtype,
                "description": "User-added market"
            }
            logging.debug(f"Added new market: {market_name} (Sport: {sport}, Type: {mtype}, Aliases: {aliases})")
            self.save_all()

    def add_player(self, player_name: str, sport: str, team: str = None, aliases: list = None):
        """
        Add a new player and save changes.
        
        :param player_name: The canonical name of the player.
        :param sport: The sport the player participates in.
        :param team: Optional team name (must already exist to link player to team).
        :param aliases: Optional list of aliases for the player.
        """
        player_name = player_name.lower().strip()
        if not aliases:
            aliases = []
        if player_name not in self.players:
            self.players[player_name] = {
                "sport": sport,
                "team": team.lower() if team else None,
                "aliases": aliases
            }
            logging.debug(f"Added new player: {player_name} (Sport: {sport}, Team: {team}, Aliases: {aliases})")
            self.save_all()
            if team and team.lower() in self.teams:
                if "players" not in self.teams[team.lower()]:
                    self.teams[team.lower()]["players"] = []
                if player_name not in self.teams[team.lower()]["players"]:
                    self.teams[team.lower()]["players"].append(player_name)
                    logging.debug(f"Linked player '{player_name}' to team '{team.lower()}'.")
                self.save_all()

    def list_teams(self) -> list:
        """
        List all canonical team names.
        
        :return: A list of team names.
        """
        logging.debug("Listing all teams.")
        return list(self.teams.keys())

    def list_markets(self) -> list:
        """
        List all canonical market names.
        
        :return: A list of market names.
        """
        logging.debug("Listing all markets.")
        return list(self.markets.keys())

    def find_team_by_alias(self, alias: str) -> str:
        """
        Find a team by alias or canonical name.
        
        :param alias: The alias or canonical name to search for.
        :return: The canonical team name if found, else None.
        """
        logging.debug(f"Searching for team by alias: {alias}")
        alias = alias.lower().strip()
        for team_name, data in self.teams.items():
            all_aliases = [team_name] + data.get("aliases", [])
            if alias in [a.lower() for a in all_aliases]:
                logging.debug(f"Found team '{team_name}' for alias '{alias}'")
                return team_name
        logging.debug(f"No team found for alias '{alias}'")
        return None

    def find_market_by_alias(self, alias: str) -> str:
        """
        Find a market by alias or canonical name.
        
        :param alias: The alias or canonical name to search for.
        :return: The canonical market name if found, else None.
        """
        logging.debug(f"Searching for market by alias: {alias}")
        alias = alias.lower().strip()
        for market_name, data in self.markets.items():
            all_aliases = data.get("aliases", []) + [market_name]
            if alias in [a.lower() for a in all_aliases]:
                logging.debug(f"Found market '{market_name}' for alias '{alias}'")
                return market_name
        logging.debug(f"No market found for alias '{alias}'")
        return None

    def find_player_by_alias(self, alias: str) -> str:
        """
        Find a player by alias or canonical name.
        
        :param alias: The alias or canonical name to search for.
        :return: The canonical player name if found, else None.
        """
        logging.debug(f"Searching for player by alias: {alias}")
        alias = alias.lower().strip()
        for player_name, data in self.players.items():
            all_aliases = [player_name] + data.get("aliases", [])
            if alias in [a.lower() for a in all_aliases]:
                logging.debug(f"Found player '{player_name}' for alias '{alias}'")
                return player_name
        logging.debug(f"No player found for alias '{alias}'")
        return None
