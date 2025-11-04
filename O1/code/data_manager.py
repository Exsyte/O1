import os
import json
import logging
from config import DATA_PATH

class DataManager:
    """
    Manages the loading, saving, and in-memory representation of teams, players, and markets data.

    Responsibilities:
      - Load and store teams, markets, and players data from JSON files in DATA_PATH.
      - Provide methods to add new teams, markets, and players, automatically saving changes.
      - Offer lookup methods (e.g., find_team_by_alias()) to search for entities by aliases.

    Potential Future Improvements:
      - Separate reading/writing logic into a dedicated repository layer for cleaner separation of concerns.
      - Introduce domain models (e.g., Team, Market, Player classes) to add validation and domain logic at the object level.
      - Add unit tests by injecting mock data or abstracting file operations, making testing easier.
    """

    def __init__(self):
        logging.debug("Initializing DataManager.")
        self.teams = {}
        self.players = {}
        self.markets = {}
        self.load_all()

    def load_all(self):
        """
        Load all data (teams, markets, players) from JSON files in DATA_PATH.
        
        If files are missing or malformed, logs warnings or errors and uses empty dicts as fallbacks.
        After loading:
          - self.teams, self.markets, self.players are dictionaries keyed by names (lowercase keys recommended).
        """
        logging.debug("Loading all data (teams, markets, players).")
        self.teams = self._safe_load_json("teams.json") or {}
        self.markets = self._safe_load_json("markets.json") or {}

        players_file = os.path.join(DATA_PATH, "players.json")
        self.players = self._safe_load_json("players.json") if os.path.exists(players_file) else {}
        logging.debug("Data loaded. Teams: %d, Markets: %d, Players: %d",
                      len(self.teams), len(self.markets), len(self.players))

    def _safe_load_json(self, filename: str):
        """
        Safely load JSON data from a specified file within DATA_PATH.
        
        :param filename: The name of the JSON file to load (e.g., 'teams.json').
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
        Safely save a dictionary to a JSON file in DATA_PATH.
        
        Logs an error if saving fails, but doesn't raise an exception. 
        In a more robust system, you might handle errors by retrying or alerting an administrator.
        
        :param filename: The name of the JSON file to save to.
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
        
        If saving fails for any file, logs an error. Some data may still be saved partially.
        """
        logging.debug("Saving all data (teams, markets, players).")
        self._safe_save_json("teams.json", self.teams)
        self._safe_save_json("markets.json", self.markets)
        self._safe_save_json("players.json", self.players)

    def add_team(self, team_name: str, sport: str, aliases: list = None):
        """
        Add a new team to the in-memory data and persist it to teams.json.
        
        :param team_name: The canonical name of the team.
        :param sport: The sport this team belongs to (required).
        :param aliases: A list of aliases for this team. Optional, defaults to [].
        
        Validations/Checks:
          - If sport is missing or empty, logs a warning. Continues to add team but consider sport mandatory for future.
          - If the team already exists, does nothing.
        
        After adding, calls save_all(). If saving fails, logs an error.
        """
        team_name = team_name.lower().strip()
        if not sport:
            logging.warning(f"No sport specified for team '{team_name}'. Consider adding a sport.")
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
        Add a new market to the in-memory data and persist it to markets.json.
        
        :param market_name: The canonical name of the market (e.g., "match odds").
        :param sport: The sport for this market.
        :param mtype: The type of the market (e.g., "MATCH_ODDS").
        :param aliases: A list of aliases for this market. Optional.
        
        Validations/Checks:
          - If sport or mtype missing, logs a warning. Market still added but consider them required.
          - If market already exists, does nothing.
        
        After adding, calls save_all(). If saving fails, logs an error.
        """
        market_name = market_name.lower().strip()
        if not sport:
            logging.warning(f"No sport specified for market '{market_name}'. Consider adding a sport.")
        if not mtype:
            logging.warning(f"No market type specified for '{market_name}'. Consider adding a type.")
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
        Add a new player to the in-memory data and persist it to players.json.
        
        :param player_name: The player's canonical name.
        :param sport: The sport the player participates in.
        :param team: The player's team name (optional).
        :param aliases: List of aliases for the player.
        
        Validations/Checks:
          - If sport is missing, logs a warning. Player still added.
          - If team given and team doesn't exist, player still added but not linked to team.
        
        After adding, attempts to link the player to the team if specified and exists.
        Calls save_all(). Logs errors if saving fails.
        """
        player_name = player_name.lower().strip()
        if not sport:
            logging.warning(f"No sport specified for player '{player_name}'. Consider adding a sport.")
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
        List all known teams by their canonical names.
        
        :return: A list of team names.
        """
        logging.debug("Listing all teams.")
        return list(self.teams.keys())

    def list_markets(self) -> list:
        """
        List all known markets by their canonical names.
        
        :return: A list of market names.
        """
        logging.debug("Listing all markets.")
        return list(self.markets.keys())

    def find_team_by_alias(self, alias: str) -> str:
        """
        Find a team by one of its aliases (or its canonical name).
        
        :param alias: An alias or canonical name of the team to search for.
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
        Find a market by one of its aliases (or its canonical name).
        
        :param alias: An alias or canonical name of the market.
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
        Find a player by one of its aliases (or its canonical name).
        
        :param alias: An alias or canonical name of the player.
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
