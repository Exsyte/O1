import logging
from typing import Dict
from normalization import normalize_text

def build_alias_map_markets(markets_data: Dict[str, Dict]) -> Dict[str, str]:
    """
    Build a dictionary mapping normalized market aliases to their canonical market names.

    This function expects a dictionary of markets, each possibly containing an "aliases" key.
    It normalizes all aliases and ensures that the canonical market name is also treated as an alias.
    Then it creates a reverse lookup so that any alias maps back to the canonical market name.

    Example:
        markets_data = {
            "match odds": {"aliases": ["Full Time Result"]},
            "over/under 2.5 goals": {"aliases": []}
        }

        Returns something like:
        {
            "match odds": "match odds",
            "full time result": "match odds",
            "over/under 2.5 goals": "over/under 2.5 goals"
        }

    :param markets_data: A dictionary keyed by market name. Each value is another dict with possible "aliases".
                         For example:
                         {
                           "match odds": {"aliases": ["Full Time Result"]}
                         }
                         Ensure this data is pre-loaded from external configuration or data source.
    :return: A dictionary mapping every normalized alias back to its canonical market name.
    """
    logging.debug("Starting to build alias map for markets.")

    if not markets_data:
        logging.warning("No market data provided. Returning empty alias map for markets.")
        return {}

    alias_map = {}
    for market_name, data in markets_data.items():
        aliases = data.get("aliases", [])
        # Ensure the canonical market name is included as an alias
        if market_name not in aliases:
            aliases.append(market_name)

        logging.debug(f"Processing market '{market_name}' with aliases: {aliases}")

        for a in aliases:
            norm_a = normalize_text(a)
            alias_map[norm_a] = market_name
            logging.debug(f"Alias '{a}' normalized to '{norm_a}' mapped to '{market_name}'")

    logging.debug("Completed building alias map for markets.")
    return alias_map

def build_alias_map_teams(teams_data: Dict[str, Dict]) -> Dict[str, str]:
    """
    Build a dictionary mapping normalized team aliases to their canonical team names.

    Similar to the markets function, this ensures that every alias for a team,
    as well as the team's canonical name, is included in the returned map.
    Any alias can then be used to find the canonical team name quickly.

    Example:
        teams_data = {
            "Manchester United": {"sport": "football", "aliases": ["Man Utd", "Man United"]},
            "Chelsea": {"sport": "football", "aliases": []}
        }

        Returns:
        {
            "manchester united": "Manchester United",
            "man utd": "Manchester United",
            "man united": "Manchester United",
            "chelsea": "Chelsea"
        }

    :param teams_data: A dictionary keyed by team name. Values contain team info, including an "aliases" list.
                       For example:
                       {
                         "Manchester United": {
                           "sport": "football",
                           "aliases": ["Man Utd", "Man United"]
                         }
                       }
                       This data should be pre-loaded from external configuration or data source.
    :return: A dictionary mapping normalized aliases to their canonical team name.
    """
    logging.debug("Starting to build alias map for teams.")

    if not teams_data:
        logging.warning("No team data provided. Returning empty alias map for teams.")
        return {}

    alias_map = {}
    for team_name, data in teams_data.items():
        norm_team = normalize_text(team_name)
        alias_map[norm_team] = team_name
        logging.debug(f"Team '{team_name}' normalized to '{norm_team}'.")

        # Add each alias
        for a in data.get("aliases", []):
            if a.strip():
                norm_a = normalize_text(a)
                alias_map[norm_a] = team_name
                logging.debug(f"Alias '{a}' normalized to '{norm_a}' mapped to '{team_name}'")

    logging.debug("Completed building alias map for teams.")
    return alias_map
