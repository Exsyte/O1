import logging
from config import MARKET_NAME_TO_TYPES

def map_market_name_to_type(market_name: str, sport: str = "football"):
    """
    Map a human-readable market name to a list of standardized market type codes.

    **What it Does:**
    Given a market name (e.g., "match odds") and a sport (defaulting to football), 
    this function returns the corresponding standardized market type codes 
    based on mappings loaded from configuration.

    **Configuration:**
    MARKET_NAME_TO_TYPES is loaded from config.py, which should be populated from config.json.
    For example:
    {
      "match odds": ["MATCH_ODDS"],
      "both teams to score": ["BOTH_TEAMS_TO_SCORE"],
      ...
    }

    **Special Cases:**
    - If market_name is "to win to nil", returns an empty list.
      The logic determining TEAM_A_WIN_TO_NIL or TEAM_B_WIN_TO_NIL is handled elsewhere in the code.
    
    **Fallback Logic:**
    - If the given market_name is not found in MARKET_NAME_TO_TYPES:
      - Returns ["MATCH_ODDS"] for football.
      - Returns ["MONEY_LINE"] for other sports.
    
    **Examples:**
    - map_market_name_to_type("match odds", "football") → ["MATCH_ODDS"]
    - map_market_name_to_type("over/under 2.5 goals", "football") might return ["OVER_UNDER_25"] if defined.
    - map_market_name_to_type("to win to nil") → []

    **Error Handling:**
    - This function does not raise exceptions for unknown markets; it uses fallback logic.
    - If configuration is missing or incomplete, it relies on defaults and logs debug info.

    **Future Improvements:**
    - Consider validating that sport is recognized, and if not, provide a warning or fallback.
    - Allow configuration to specify fallback values on a per-sport basis for better customization.
    - Extract mapping logic into a dedicated mapping object or class if complexity grows.

    :param market_name: The human-readable name of the market (e.g., "match odds").
    :param sport: The sport associated with the market, defaults to "football".
    :return: A list of market type codes corresponding to the given market name.
    """
    logging.debug(f"Mapping market name: '{market_name}' for sport: '{sport}'")
    if not market_name:
        logging.debug("No market_name provided, defaulting to 'match odds'")
        market_name = "match odds"
    name = market_name.strip().lower()

    if name == "to win to nil":
        logging.debug("Market name is 'to win to nil', returning empty list.")
        return []

    if name in MARKET_NAME_TO_TYPES:
        mapped_types = MARKET_NAME_TO_TYPES[name]
        logging.debug(f"Found mapping for '{name}': {mapped_types}")
        return mapped_types

    # Fallback logic if not found in MARKET_NAME_TO_TYPES
    if sport.lower() == "football":
        logging.debug(f"No direct mapping found for '{name}' in football. Returning ['MATCH_ODDS'].")
        return ["MATCH_ODDS"]
    else:
        logging.debug(f"No direct mapping found for '{name}' in '{sport}'. Returning ['MONEY_LINE'].")
        return ["MONEY_LINE"]
