import logging
import difflib
from typing import List
from normalization import normalize_text
from data_manager import DataManager

def prompt_for_odds() -> float:
    """
    Continuously prompt the user to enter odds until a valid positive decimal is provided.

    Steps:
      - Ask for input.
      - Convert to float, check if > 0.
      - If invalid, print a warning and re-prompt.

    Returns:
      A positive float representing the entered odds.

    Example:
      User enters: "1.85" → returns 1.85
      User enters: "-2" or non-numeric → prompts again.
    """
    while True:
        odds_input = input("Enter odds (must be a positive decimal): ").strip()
        try:
            odds_val = float(odds_input)
            if odds_val > 0:
                logging.debug(f"User entered valid odds: {odds_val}")
                return odds_val
            else:
                print("Odds must be positive. Try again.")
                logging.debug("User entered non-positive odds, prompting again.")
        except ValueError:
            print("Invalid input. Please enter a positive decimal number.")
            logging.debug(f"User entered invalid odds: '{odds_input}'.")

def fuzzy_search_and_add_alias(token: str, existing_list: list, data_dict: dict, data_manager: DataManager, entity_type: str):
    """
    Attempt a fuzzy search to find close matches for a token among existing entities (teams/markets),
    and optionally add the token as a new alias to an existing entity.

    Logic:
      - Uses difflib.get_close_matches to find up to 5 close matches with a cutoff=0.6 similarity.
      - If matches found, prompt user to select one or opt to create a new entity.
      - If a match is chosen, add 'token' as an alias to that entity and save changes.
      - If no matches or user chooses none, return None indicating user will add new entity separately.
      - If user makes an invalid choice, return 'retry' to re-prompt.

    Parameters:
      - token: The entity name or alias to classify.
      - existing_list: A list of existing canonical names for teams/markets.
      - data_dict: The dictionary holding all team/market data.
      - data_manager: DataManager instance for saving updates.
      - entity_type: 'team' or 'market'.

    Returns:
      - 'team_existing' or 'market_existing' if token was added as alias to an existing entity.
      - None if user opts to create a new entity.
      - 'retry' if user made an invalid choice (e.g., bad number).

    Example:
      token="man utd", existing_list=["manchester united"], finds a close match "manchester united".
      User picks the match, alias added to "manchester united", return "team_existing".
    """
    logging.debug(f"Fuzzy searching for '{token}' among {len(existing_list)} existing {entity_type}(s).")
    close_matches = difflib.get_close_matches(token, existing_list, n=5, cutoff=0.6)
    if close_matches:
        print(f"Close {entity_type} matches found:")
        for i, match in enumerate(close_matches, start=1):
            info = data_dict[match]
            if entity_type == 'team':
                sport = info.get("sport", "unknown sport")
                print(f"{i}. {match} (Sport: {sport})")
            elif entity_type == 'market':
                sport = info.get("sport", "unknown sport")
                mtype = info.get("type", "regular")
                print(f"{i}. {match} (Sport: {sport}, Type: {mtype})")

        choice = input(f"Select a matching {entity_type} by number, or (N)one to add as new {entity_type}: ").strip().lower()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(close_matches):
                chosen = close_matches[idx-1]
                aliases = data_dict[chosen].get("aliases", [])
                if token.lower() not in [a.lower() for a in aliases]:
                    aliases.append(token.lower())
                    data_dict[chosen]["aliases"] = aliases
                    data_manager.save_all()
                    print(f"Added '{token}' as an alias to existing {entity_type} '{chosen}'.")
                    logging.debug(f"Added alias '{token}' to existing {entity_type} '{chosen}'.")
                return f"{entity_type}_existing"
            else:
                print("Invalid choice number.")
                logging.debug("User entered invalid choice number for fuzzy search results.")
                return 'retry'
        elif choice == 'n':
            logging.debug("User chose to add a new entity rather than using a close match.")
            return None
        else:
            print("Invalid choice, returning to main classification options.")
            logging.debug("User entered invalid choice when selecting close match.")
            return 'retry'
    else:
        print(f"No close {entity_type} matches found.")
        logging.debug(f"No close {entity_type} matches found for '{token}'.")
        return None

def handle_entity_classification(token: str, entity_type: str, data_manager: DataManager) -> str:
    """
    Handle classification of an entity (team or market), first attempting fuzzy search and, if no match,
    allow manual creation of a new entity.

    Steps:
      - If fuzzy search finds a match, user can add alias to existing entity.
      - If no matches or user chooses none, user can either specify a manual name or add a completely new entity.
      - If invalid input during the process, will retry or eventually return None.

    Parameters:
      - token: The token to classify.
      - entity_type: 'team' or 'market'.
      - data_manager: DataManager instance.

    Returns:
      - 'team', 'team_existing', 'market', 'market_existing' if entity is successfully added or matched.
      - 'ignore' if user chooses to ignore.
      - None if user cancels.

    Potential Future Improvements:
      - Add validation for sport or type inputs.
      - Integrate fuzzy logic for manual name as well.
      - Move prompting logic out of this function for better testability.

    Example:
      token="chelsey"
      If fuzzy search: "chelsea" found, user picks it → 'team_existing'
      If no match, user chooses manual and enters a new team name → 'team'
    """
    logging.debug(f"Handling classification for '{token}' as '{entity_type}'.")

    if entity_type == 'team':
        existing_list = data_manager.list_teams()
        data_dict = data_manager.teams
    else:  # entity_type == 'market'
        existing_list = data_manager.list_markets()
        data_dict = data_manager.markets

    result = fuzzy_search_and_add_alias(token, existing_list, data_dict, data_manager, entity_type)
    if result == 'retry':
        logging.debug("Retrying entity classification due to invalid choice.")
        return handle_entity_classification(token, entity_type, data_manager)
    elif result is None:
        # No suitable match found; ask user for manual input.
        manual_choice = input(f"No suitable match. Enter (M)anual {entity_type} name or (N)ew {entity_type}: ").strip().lower()
        logging.debug(f"No matches found; user chose '{manual_choice}' option for {entity_type} '{token}'.")

        if manual_choice == 'm':
            manual_name = input(f"Type the canonical {entity_type} name exactly: ").strip().lower()
            manual_close = difflib.get_close_matches(manual_name, existing_list, n=5, cutoff=0.6)
            if manual_close:
                chosen_manual = manual_close[0]
                aliases = data_dict[chosen_manual].get("aliases", [])
                if token.lower() not in [a.lower() for a in aliases]:
                    aliases.append(token.lower())
                    data_dict[chosen_manual]["aliases"] = aliases
                    data_manager.save_all()
                    print(f"Added '{token}' as an alias to existing {entity_type} '{chosen_manual}'.")
                    logging.debug(f"Added alias '{token}' to existing {entity_type} '{chosen_manual}' via manual match.")
                return f"{entity_type}_existing"
            else:
                # Add a completely new entity
                sport = input(f"Enter the sport for {entity_type} '{manual_name}': ").strip().lower()
                aliases_str = input(f"Enter aliases for this {entity_type} (comma-separated) or leave blank: ").strip()
                aliases = [a.strip().lower() for a in aliases_str.split(",") if a.strip()] if aliases_str else []
                if token.lower() not in aliases and token.lower() != manual_name:
                    aliases.append(token.lower())
                if entity_type == 'team':
                    data_manager.add_team(manual_name, sport, aliases)
                    print(f"New team '{manual_name}' added (with '{token}' as alias).")
                    logging.debug(f"New team '{manual_name}' added with alias '{token}'.")
                    return 'team'
                else:
                    data_manager.add_market(manual_name, sport, 'regular', aliases)
                    print(f"New market '{manual_name}' added (with '{token}' as alias).")
                    logging.debug(f"New market '{manual_name}' added with alias '{token}'.")
                    return 'market'
        else:
            # New entity directly named after token
            sport = input(f"Enter the sport for this {entity_type} '{token}': ").strip().lower()
            aliases_str = input(f"Enter aliases for this {entity_type} (comma-separated) or leave blank: ").strip()
            aliases = [a.strip().lower() for a in aliases_str.split(",") if a.strip()] if aliases_str else []
            if entity_type == 'team':
                data_manager.add_team(token, sport, aliases)
                print(f"New team '{token}' added.")
                logging.debug(f"New team '{token}' added directly.")
                return 'team'
            else:
                data_manager.add_market(token, sport, 'regular', aliases)
                print(f"New market '{token}' added.")
                logging.debug(f"New market '{token}' added directly.")
                return 'market'
    else:
        # result is 'team_existing', 'market_existing', etc.
        logging.debug(f"Classification result for '{token}' as '{entity_type}': {result}")
        return result

def prompt_user_for_classification(token: str, data_manager):
    """
    Prompt the user to classify an unrecognized token as a team, player, market, or ignore.

    Steps:
      - Print the unrecognized token.
      - Prompt user choice: Team/Player/Market/Ignore.
      - If team/market chosen, call handle_entity_classification.
      - If player chosen, prompt directly for player info.
      - If ignore chosen, return 'ignore'.

    Returns:
      - 'team', 'team_existing', 'market', 'market_existing', 'player', or 'ignore' depending on user actions.
    """
    print(f"Unrecognized token: '{token}'")
    logging.debug(f"Prompting user for classification of '{token}'.")
    while True:
        ans = input("Options: (T)eam/(P)layer/(M)arket/(I)gnore? ").strip().lower()
        logging.debug(f"User chose '{ans}' for token '{token}'.")
        if ans == 't':
            return handle_entity_classification(token, 'team', data_manager)
        elif ans == 'm':
            return handle_entity_classification(token, 'market', data_manager)
        elif ans == 'p':
            # Player logic: ask for sport/team/aliases directly, then add player.
            sport = input(f"Enter the sport for player '{token}': ").strip().lower()
            team = input("Enter the player's team name or leave blank if none: ").strip()
            aliases_str = input("Enter aliases for this player (comma-separated) or leave blank: ").strip()
            aliases = [a.strip().lower() for a in aliases_str.split(",") if a.strip()] if aliases_str else []
            data_manager.add_player(token, sport, team, aliases)
            logging.debug(f"New player '{token}' added with sport='{sport}', team='{team}', aliases={aliases}.")
            return 'player'
        elif ans == 'i':
            logging.debug(f"User chose to ignore token '{token}'.")
            return 'ignore'
        else:
            print("Invalid choice, please select T/P/M/I.")
            logging.debug(f"User entered invalid choice '{ans}' for token '{token}'.")
