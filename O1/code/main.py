# main.py

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

import re

from data_manager import DataManager
from bet_parser import parse_bet
from utils import prompt_for_odds, prompt_user_for_classification
from betfair_integration import BetfairIntegration, infer_sport_from_market
from config import COMMON_FILLER_WORDS, FUZZY_THRESHOLD, SPORT_EVENT_TYPE_IDS
from parse_multiple_matches import parse_multiple_matches

def preprocess_input(input_str: str) -> str:
    """
    Preprocess user input by:
      - Lowercasing
      - Replacing commas and ampersands with spaces (or 'and')
      - Collapsing multiple spaces into one

    Example:
      Input: "Ajax, Lazio & Rangers"
      Output: "ajax lazio rangers"

    :param input_str: The raw user input string.
    :return: A preprocessed, normalized string.
    """
    logging.debug(f"Preprocessing input: {input_str}")
    input_str = input_str.lower()
    input_str = input_str.replace(",", " ")
    input_str = input_str.replace("&", " ")
    input_str = " ".join(input_str.split())
    logging.debug(f"Preprocessed input: {input_str}")
    return input_str

def handle_unrecognized_segments(unrecognized_list, data_manager: DataManager, input_str: str, markets_data, teams_data):
    """
    Handle unrecognized segments of the parsed bet by allowing the user to classify them.

    Steps:
      - For each unrecognized segment, prompt user choices:
        (S)elect substring to classify
        (I)gnore remainder
        (D)one
        (Q)uit handling
      - If new data is added (e.g., a new team or market), re-parse the input.

    Returns:
      If new data was added, returns the re-parsed result.
      Otherwise, returns None.

    :param unrecognized_list: A list of unrecognized segments.
    :param data_manager: DataManager instance for classification.
    :param input_str: The original user input.
    :param markets_data: Current markets data dictionary.
    :param teams_data: Current teams data dictionary.
    :return: The updated parse result if data changed, else None.
    """
    logging.debug(f"Handling unrecognized segments: {unrecognized_list}")
    if not unrecognized_list:
        return None

    new_data_added = False
    for seg in unrecognized_list:
        print(f"\nCurrent unrecognized segment: '{seg}'", flush=True)
        while True:
            action = input("Select action: (S)elect substring/(I)gnore remainder/(D)one/(Q)uit handling: ").strip().lower()
            if action == 's':
                chosen_substring = input("Type the substring you want to classify: ").strip()
                if chosen_substring:
                    result = prompt_user_for_classification(chosen_substring, data_manager)
                    logging.debug(f"Classification result for '{chosen_substring}': {result}")
                    if result in ['team', 'market', 'player', 'team_existing', 'market_existing']:
                        new_data_added = True
            elif action == 'i':
                print(f"Ignoring remainder of '{seg}'.", flush=True)
                break
            elif action == 'd':
                print("Done with this segment.", flush=True)
                break
            elif action == 'q':
                print("Quitting handling unrecognized segments.", flush=True)
                return None
            else:
                print("Invalid choice. Please choose (S), (I), (D), or (Q).", flush=True)

    if new_data_added:
        print("Re-parsing the input after adding new data...", flush=True)
        logging.debug("Data changed, re-parsing input.")
        cleaned_input = preprocess_input(input_str)
        re_result = parse_bet(cleaned_input, markets_data, teams_data, data_manager, prompt_user_for_classification)
        return re_result
    return None

def parse_user_input(user_input: str) -> tuple[str, str, str, float, bool]:
    """
    Parse user input line to potentially extract bookmaker, sport, bet_string, and odds 
    if provided in the format:
      "bookmaker - sport - bet_string - odds"

    If odds aren't parsed successfully, prompts user for odds.

    :param user_input: The raw user input line.
    :return: A tuple (bookmaker, given_sport, bet_string, odds, explicit_format)
             bookmaker: str or None
             given_sport: str or None
             bet_string: The parsed bet string
             odds: float representing the odds
             explicit_format: bool indicating if user provided the full format
    """
    import re
    logging.debug(f"Parsing user input: {user_input}")

    # Check how many times " - " appears.
    # We require exactly 3 of these as separators to parse the advanced format.
    occurrences = len(re.findall(r'\s-\s', user_input))

    bookmaker, given_sport, bet_string, odds = (None, None, user_input, None)
    explicit_format = False

    if occurrences == 3:
        # Split on " - " exactly three times, giving us 4 parts
        parts = re.split(r'\s-\s', user_input, maxsplit=3)
        bookmaker, given_sport, bet_string, odds_str = [p.strip() for p in parts]

        try:
            odds_val = float(odds_str)
            if odds_val <= 0:
                print("Warning: Odds must be positive. Treating as normal bet string.", flush=True)
                odds_val = prompt_for_odds()
            else:
                print(f"Detected format: Bookmaker='{bookmaker}', Sport='{given_sport}', "
                      f"BetString='{bet_string}', Odds={odds_val}", flush=True)
                explicit_format = True
            odds = odds_val
        except ValueError:
            print("Warning: Odds not recognized as a positive decimal number.", flush=True)
            odds = prompt_for_odds()
    else:
        # Fallback: treat entire input as bet_string, prompt user for odds
        odds = prompt_for_odds()

    logging.debug(f"Parsed input -> Bookmaker: {bookmaker}, "
                  f"Sport: {given_sport}, BetString: {bet_string}, "
                  f"Odds: {odds}, Explicit: {explicit_format}")
    return bookmaker, given_sport, bet_string, odds, explicit_format

def handle_multiple_matches_scenario(user_input: str) -> str:
    logging.debug(f"Handling multiple matches scenario for input: {user_input}")
    home_teams = parse_multiple_matches(user_input, pick="home")

    # Identify leftover text by removing matched segments from original input.
    # A simple (though not perfect) approach:
    # 1. Extract all matches (home and away) for clarity.
    all_home_teams = parse_multiple_matches(user_input, pick="home")
    all_away_teams = parse_multiple_matches(user_input, pick="away")
    
    # Build a regex pattern to remove matched teams and 'v' from original input
    # This assumes matches are well-formed. Be careful with teams containing spaces.
    pattern = r"(?i)" + r"|".join([re.escape(ht) for ht in all_home_teams] + [re.escape(at) for at in all_away_teams] + ["v"])
    
    leftover = re.sub(pattern, "", user_input).strip(", ").strip()
    
    # Now leftover should contain "o2.5 goals" and possibly some extra punctuation/whitespace.
    # Combine teams (home_teams) with leftover text
    full_string = " ".join(home_teams)
    if leftover:
        full_string += " " + leftover
    
    cleaned_input = preprocess_input(full_string)
    logging.debug(f"Simplified bet string after handling multiple matches: {cleaned_input}")
    return cleaned_input

def reparse_if_unrecognized(result, user_input, data_manager):
    """
    After initial parsing, if there are unrecognized segments, give the user a chance to classify them.
    If new data is added, re-parse the input and return updated results.

    :param result: The initial parse result dictionary.
    :param user_input: The original user input.
    :param data_manager: DataManager instance for classification.
    :return: The possibly updated result after handling unrecognized segments.
    """
    logging.debug("Checking if re-parsing is needed due to unrecognized segments.")
    if result.get("unrecognized"):
        logging.debug(f"Unrecognized segments found: {result['unrecognized']}")
        re_result = handle_unrecognized_segments(result["unrecognized"], data_manager, user_input, data_manager.markets, data_manager.teams)
        if re_result is not None:
            result = re_result
            print("Parsed after re-parsing:", result, flush=True)
            print("-" * 60, flush=True)
    return result

def fetch_and_compute_lay_prices(result, data_manager, bookmaker, given_sport, bet_string, odds, explicit_format):
    """
    Given the parsed result (teams, markets, possibly scores), fetch events via BetfairIntegration
    and compute lay prices to determine if the bet is 'VALUE', '2PC', or 'NOT VALUE'.

    Steps:
      - Determine team sports.
      - If no identified markets, pick a default based on sport.
      - Fetch events, pick best events, find lay prices.
      - Multiply lay prices, compare with user's odds to decide value.
      - Prompt user to save bet if it's value and format wasn't explicit.

    Potential Future Improvements:
      - Separate logic for fetching events and computing lay prices into a separate module.
      - Introduce a BetEvaluator class that takes results and odds, returns a value assessment.

    :param result: The dictionary from parse_bet, containing 'teams', 'markets', and optionally 'scores'.
    :param data_manager: DataManager instance with loaded teams/markets data.
    :param bookmaker: The bookmaker name if provided.
    :param given_sport: The sport name if provided.
    :param bet_string: The original bet string.
    :param odds: The user's odds input.
    :param explicit_format: Boolean indicating if user provided the full format including odds.
    """
    logging.debug("Fetching events and computing lay prices.")
    teams = result.get("teams", [])
    identified_markets = result.get("markets", [])
    scores = result.get("scores", [])

    team_sports = {}
    for t in teams:
        if t in data_manager.teams:
            team_sports[t] = data_manager.teams[t]["sport"]
        else:
            team_sports[t] = "football"  # Default fallback

    # If no markets identified, assign a default based on the sport(s)
    if not identified_markets:
        unique_sports = set(team_sports.values())
        if len(unique_sports) == 1:
            single_sport = unique_sports.pop()
            default_market = {
                "football": "match odds",
                "nba": "moneyline_nba",
                "nfl": "moneyline_nfl",
                "nhl": "moneyline_nhl"
            }.get(single_sport, "match odds")
            identified_markets = [default_market]
            logging.debug(f"No identified markets, defaulting to: {default_market}")

    integration = BetfairIntegration()
    queried_events = set()
    lay_prices = []

    if identified_markets:
        # Try to find lay prices for each team/market combo
        for team in teams:
            sport_of_team = team_sports[team]
            compatible_markets = [
                m for m in identified_markets
                if m in data_manager.markets and data_manager.markets[m]["sport"] == sport_of_team
            ]
            if not compatible_markets:
                default_market = {
                    "football": "match odds",
                    "nba": "moneyline_nba",
                    "nfl": "moneyline_nfl",
                    "nhl": "moneyline_nhl"
                }.get(sport_of_team, "match odds")
                compatible_markets = [default_market]
                logging.debug(f"No compatible markets found for {team} ({sport_of_team}). Using default: {default_market}")

            from market_mapping import map_market_name_to_type
            sport_id = SPORT_EVENT_TYPE_IDS.get(sport_of_team, "1")
            events = integration.find_events_for_team(team, sport_id=sport_id)
            best_event = integration.pick_best_event(events, team)
            if not best_event:
                print(f"No suitable event found for team '{team}'. Stopping further processing.")
                return  # <-- STOP immediately if no event found

            event_id = best_event["event"]["id"]
            if event_id in queried_events:
                print(f"Skipping duplicate match for event {event_id}.")
                continue
            queried_events.add(event_id)

            price_found = None
            for market in compatible_markets:
                mtypes = map_market_name_to_type(market, sport=sport_of_team)
                if "CORRECT_SCORE" in mtypes and scores:
                    price_result = integration.fetch_best_lay_price_for_team_and_market(team, market, scores=scores)
                else:
                    price_result = integration.fetch_best_lay_price_for_team_and_market(team, market)

                if price_result is not None:
                    price_found = price_result
                    break

            if price_found is not None:
                lay_prices.append(price_found)
                logging.debug(f"Found lay price {price_found} for team {team} in market {market}")
            else:
                print(f"Could not find a suitable lay price for the given team/market: {team}/{compatible_markets[0]}")
                print("Stopping further processing.")
                return  # <-- STOP immediately if no lay price found
    else:
        # No identified markets, fallback to default markets for each team
        for team in teams:
            sport_of_team = team_sports[team]
            default_market = {
                "football": "match odds",
                "nba": "moneyline_nba",
                "nfl": "moneyline_nfl",
                "nhl": "moneyline_nhl"
            }.get(sport_of_team, "match odds")

            events = integration.find_events_for_team(team)
            best_event = integration.pick_best_event(events, team)
            if not best_event:
                print(f"No suitable event found for team '{team}'. Stopping further processing.")
                return  # <-- STOP immediately if no event found

            event_id = best_event["event"]["id"]
            if event_id in queried_events:
                print(f"Skipping duplicate match for event {event_id}.")
                continue
            queried_events.add(event_id)

            price = integration.fetch_best_lay_price_for_team_and_market(team, default_market)
            if price is not None:
                lay_prices.append(price)
                logging.debug(f"Found lay price {price} for team {team} in default market {default_market}")
            else:
                print(f"Could not find a suitable lay price for the given team/market: {team}/{default_market}")
                print("Stopping further processing.")
                return  # <-- STOP immediately if no lay price found

    # If we made it here, all teams had a lay price found
    if lay_prices:
        product = 1.0
        for p in lay_prices:
            product *= p
        product_3d = round(product, 3)
        product_2d = round(product_3d, 2)

        print(f"Multiplied Lay Price: {product_2d}", flush=True)

        value_status = "NOT VALUE"
        if product < 0.9999 * odds:
            value_status = "VALUE"
        elif product <= 1.0199 * odds:
            value_status = "2PC"

        print(value_status, flush=True)

        if value_status in ["VALUE", "2PC"] and not explicit_format:
            # Prompt user to save line
            save_choice = input("Do you want to save this bet? (y/n): ").strip().lower()
            if save_choice == 'y':
                if not bookmaker:
                    bookmaker = input("Enter the bookmaker name: ").strip()

                # If user didn't specify a sport, pick the unique sport or default to football
                final_sport = given_sport.lower() if given_sport else None
                if not final_sport:
                    unique_sports = set(team_sports.values())
                    if len(unique_sports) == 1:
                        final_sport = list(unique_sports)[0]
                    else:
                        final_sport = "football"

                # Format the sport name
                if final_sport.lower() == "nba":
                    final_sport_display = "NBA"
                elif final_sport.lower() == "nfl":
                    final_sport_display = "NFL"
                elif final_sport.lower() == "nhl":
                    final_sport_display = "NHL"
                else:
                    final_sport_display = final_sport.capitalize()

                final_bet_string = bet_string.strip()

                # Build the final line to be saved/printed
                final_line = f"{bookmaker} - {final_sport_display} - {final_bet_string} - {odds} / {product_2d}"
                if value_status == "2PC":
                    final_line += " 2pc"

                print("Saved line:", final_line, flush=True)
                logging.debug(f"Bet saved: {final_line}")
    else:
        print("No lay prices found or no valid bets parsed.", flush=True)
        logging.debug("No lay prices found.")

def main_loop(data_manager):
    """
    The main interaction loop of the application:
      - Prompts user for a bet input until 'quit' is entered.
      - Parses user input, handles multiple matches scenarios, and attempts to identify teams/markets.
      - Re-parses if new data is added for unrecognized segments.
      - Fetches and computes lay prices, determines if bet is value, and optionally saves.

    Potential Future Improvements:
      - Move user interaction logic (input prompts, prints) to a separate UI module.
      - Inject data_manager, bet_parser, and integration objects for testing.
      - Add error handling if parsing fails repeatedly.

    :param data_manager: DataManager instance with loaded data.
    """
    logging.debug("Starting main loop.")
    while True:
        user_input = input("Enter a bet (or 'quit' to exit): ").strip()
        if user_input.lower() == 'quit':
            logging.info("User chose to exit the application.")
            break

        bookmaker, given_sport, bet_string, odds, explicit_format = parse_user_input(user_input)

        # Handle multiple matches scenario if input seems to contain multiple 'v'
        if user_input.lower().count(" v ") > 1:
            cleaned_input = handle_multiple_matches_scenario(user_input)
            result = parse_bet(cleaned_input, data_manager.markets, data_manager.teams, data_manager, prompt_user_for_classification)
        else:
            cleaned_input = preprocess_input(bet_string)
            result = parse_bet(cleaned_input, data_manager.markets, data_manager.teams, data_manager, prompt_user_for_classification)

        print("Parsed:", result, flush=True)
        print("-" * 60, flush=True)

        result = reparse_if_unrecognized(result, user_input, data_manager)

        # Fetch events, compute lay prices, determine if the bet is value
        fetch_and_compute_lay_prices(result, data_manager, bookmaker, given_sport, bet_string, odds, explicit_format)
    logging.debug("Main loop ended.")


if __name__ == "__main__":
    from config import FUZZY_THRESHOLD, COMMON_FILLER_WORDS, SPORT_EVENT_TYPE_IDS
    # Initialize DataManager and BetfairIntegration after logging and config are set up
    data_manager = DataManager()
    integration = BetfairIntegration()

    # Example usage outputs shown at startup
    input_1 = "Ajax v Lazio & Rangers v Tottenham"
    input_2 = ("AC Omonia Nicosia v Rapid (20:00), Shamrock Rovers v FK Borac Banja Luka (20:00), "
               "St.Gallen v Vitória Guimarães (20:00), Paphos FC v NK Celje (20:00), Gent v TSC (20:00), "
               "The New Saints v Panathinaikos (20:00), FK Mla Boleslav v Jagiellonia Bialystok (20:00)")

    print("Home teams from input 1:", parse_multiple_matches(input_1, pick="home"))
    print("Home teams from input 2:", parse_multiple_matches(input_2, pick="home"))

    # Start the main loop
    main_loop(data_manager)
