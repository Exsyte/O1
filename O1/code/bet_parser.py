import re
import logging
from typing import List, Dict, Union
from difflib import get_close_matches
from rapidfuzz import fuzz

from config import FUZZY_THRESHOLD, COMMON_FILLER_WORDS
from data_manager import DataManager

def normalize_text(text: str) -> str:
    """
    Normalize text for alias matching.
    Steps:
      - Strip leading/trailing whitespace
      - Lowercase
      - Remove apostrophes and right single quotes (’ and ')
      - Retain hyphens

    :param text: The input string to normalize.
    :return: A normalized string suitable for fuzzy matching.
    """
    text = text.strip().lower()
    text = re.sub(r"[’']", "", text)
    return text

def fully_normalize_input(input_str: str) -> str:
    """
    Fully normalize an input string for parsing bets.
    Steps:
      - Lowercase
      - Replace '&' with 'and'
      - Remove all punctuation except letters, digits, spaces, dots, and hyphens
      - Collapse multiple spaces into one

    Example:
      Input: "Ajax & Lazio"
      Output: "ajax and lazio"

    :param input_str: The raw user input describing a bet.
    :return: A fully normalized string.
    """
    text = input_str.lower()
    text = re.sub(r"\b&\b", "and", text)
    text = re.sub(r"[^\w\s.\-]", "", text)
    text = " ".join(text.split())
    return text

def clean_token(token: str) -> str:
    """
    Clean a single token by removing leading/trailing non-word characters.
    Useful for stripping punctuation around words.

    :param token: A single token (word).
    :return: The cleaned token.
    """
    return re.sub(r"^[^\w]+|[^\w]+$", "", token, flags=re.UNICODE)

def find_sequence(haystack: List[str], needle: List[str]) -> int:
    """
    Find the starting index of a contiguous sequence of tokens (needle) in a list of tokens (haystack).
    Returns -1 if not found.

    Example:
      haystack = ["team", "wins", "the", "match"]
      needle = ["the", "match"]
      returns 2

    :param haystack: The list of tokens to search in.
    :param needle: The contiguous sequence of tokens to find.
    :return: Starting index if found, else -1.
    """
    length = len(needle)
    for i in range(len(haystack)-length+1):
        if haystack[i:i+length] == needle:
            return i
    return -1

def find_teams_in_segment(segment: str, team_map: Dict[str, str]) -> List[tuple]:
    """
    Identify teams mentioned in a segment of text by matching against a normalized team_map.

    :param segment: The text segment containing possible team names.
    :param team_map: A dictionary mapping normalized team aliases to their canonical names.
    :return: A list of tuples (team_name, matched_alias) for each identified team.
    """
    tokens = segment.split()
    cleaned_tokens = [clean_token(t) for t in tokens if t.strip()]

    found_teams = []
    used_indices = set()

    max_length = len(cleaned_tokens)
    for length in range(max_length, 0, -1):
        i = 0
        while i + length <= len(cleaned_tokens):
            if any((i + x) in used_indices for x in range(length)):
                i += 1
                continue

            candidate_tokens = cleaned_tokens[i:i+length]
            candidate = " ".join(candidate_tokens)
            c_norm = normalize_text(candidate)
            if c_norm in team_map:
                canonical_name = team_map[c_norm]
                found_teams.append((canonical_name, candidate))
                for x in range(length):
                    used_indices.add(i + x)
                i += length
            else:
                i += 1
    return found_teams

def find_closest_team_alias(alias: str, teams_data: Dict[str, Dict], cutoff=0.6) -> list:
    """
    Find the closest team aliases using difflib.get_close_matches.
    This function helps handle unknown or misspelled team names.

    :param alias: The team alias/user input to match.
    :param teams_data: Dictionary of team data with aliases.
    :param cutoff: The similarity cutoff for close matches.
    :return: A list of close matches.
    """
    alias = alias.lower().strip()
    all_team_names = list(teams_data.keys())
    for tname, tdata in teams_data.items():
        for a in tdata.get("aliases", []):
            if a.lower().strip() not in all_team_names:
                all_team_names.append(a.lower().strip())
    close = get_close_matches(alias, all_team_names, n=5, cutoff=cutoff)
    return close

def handle_unknown_team(team_alias: str, data_manager: DataManager, prompt_user_for_classification) -> str:
    """
    Handle the scenario where a parsed team name isn't found in the known data.
    Attempts fuzzy matching, and if not found, prompts user to classify a new team.

    :param team_alias: The unidentified team alias.
    :param data_manager: DataManager instance for accessing team data.
    :param prompt_user_for_classification: Function to prompt user for classification input.
    :return: The canonical team name once classified or created.
    """
    close_matches = find_closest_team_alias(team_alias, data_manager.teams, cutoff=0.6)
    if close_matches:
        # User-facing output - keep print
        print(f"Close team matches found for '{team_alias}':")
        indexed_matches = []
        for m in close_matches:
            main_team = data_manager.find_team_by_alias(m)
            sport = data_manager.teams[main_team]["sport"] if main_team else "unknown"
            indexed_matches.append((main_team, m, sport))
        for i, (main_team, m, sport) in enumerate(indexed_matches, start=1):
            print(f"{i}. {main_team or m} (Sport: {sport})")

        choice = input("Select a matching team by number, or (N)one to add as new team: ").strip().lower()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(indexed_matches):
                chosen_main = indexed_matches[idx-1][0]
                if team_alias.lower() not in [a.lower() for a in data_manager.teams[chosen_main]["aliases"]]:
                    data_manager.teams[chosen_main]["aliases"].append(team_alias.lower())
                    data_manager.save_all()
                    # User-facing output
                    print(f"Added '{team_alias}' as an alias to existing team '{chosen_main}'.")
                return chosen_main
        elif choice == 'n':
            pass
        else:
            print("Invalid choice, will prompt for new team.")

    print(f"No suitable existing team match found for '{team_alias}'. Let's classify this new team.")
    result = prompt_user_for_classification(team_alias, data_manager)
    main_team = data_manager.find_team_by_alias(team_alias)
    return main_team if main_team else team_alias.lower().strip()

def parse_bet(input_str: str, 
              markets_data: Dict, 
              teams_data: Dict, 
              data_manager: DataManager, 
              prompt_user_for_classification) -> Dict[str, Union[List[str], str]]:
    """
    Parse a betting-related input string to identify teams, markets, and possibly scores.

    This function:
      - Normalizes input.
      - Identifies teams from the text.
      - Removes known sport keywords and matched teams from leftover text.
      - Uses fuzzy logic to identify markets from leftover text.
      - Handles correct score scenarios.
      - Classifies unknown teams via user interaction if needed.

    Example:
      Input: "Manchester United v Chelsea match odds and over 2.5"
      Output (example):
        {
          "teams": ["manchester united", "chelsea"],
          "markets": ["match odds", "over/under 2.5 goals"],
          "unrecognized": []
        }

    Potential Errors/Handling:
      - If teams_data or markets_data are empty, logs a warning and attempts to parse anyway.
      - If no teams or markets are identified, returns minimal results.
      - If unknown teams are found, interacts with user to classify them.

    :param input_str: The raw user bet description string.
    :param markets_data: Dictionary of market data including aliases.
    :param teams_data: Dictionary of team data including aliases.
    :param data_manager: DataManager instance for accessing and updating team/market/player data.
    :param prompt_user_for_classification: Function to prompt user to classify unknown entities.
    :return: A dictionary with keys:
      - "teams": A list of identified team names.
      - "markets": A list of identified markets.
      - "unrecognized": A list of any leftover unrecognized tokens.
      - "scores" (optional): A list of identified scores if correct score scenario arises.
    """
    if not teams_data:
        logging.warning("No teams_data provided. Parsing will continue but may fail to identify teams.")
    if not markets_data:
        logging.warning("No markets_data provided. Parsing may fail to identify markets.")

    KNOWN_SPORT_KEYWORDS = {"nfl", "nba", "nhl", "football", "soccer"}

    text = fully_normalize_input(input_str)
    logging.debug(f"Starting parse_bet with input: {input_str}, Normalized: {text}")

    # Build a mapping of normalized team aliases to their canonical team names
    team_map = {}
    for team_name, data in teams_data.items():
        team_map[normalize_text(team_name)] = team_name
        for a in data.get("aliases", []):
            team_map[normalize_text(a)] = team_name

    team_matches = find_teams_in_segment(text, team_map)
    identified_teams = [t[0] for t in team_matches]
    logging.debug(f"Identified Teams: {identified_teams}")

    # Remove identified teams from leftover text
    leftover = text
    for canonical_name, matched_alias_str in team_matches:
        pattern = re.compile(r"\b" + re.escape(matched_alias_str) + r"\b", re.IGNORECASE)
        leftover = pattern.sub("", leftover)
    leftover = " ".join(leftover.split())
    logging.debug(f"After removing teams, leftover: {leftover}")

    # Remove known sport keywords
    leftover_tokens = leftover.split()
    leftover_tokens = [w for w in leftover_tokens if w not in KNOWN_SPORT_KEYWORDS]
    leftover = " ".join(leftover_tokens)
    logging.debug(f"After removing known sport keywords, leftover: {leftover}")

    # Prepare market aliases for fuzzy matching
    all_market_aliases = []
    for market_name, data in markets_data.items():
        aliases = data.get("aliases", [])
        if market_name not in aliases:
            aliases.append(market_name)
        for alias in aliases:
            alias_norm = normalize_text(alias)
            all_market_aliases.append((market_name, alias, alias_norm))

    identified_markets = []
    logging.debug(f"Starting fuzzy matching for markets. Initial leftover: {leftover}")

    # Attempt fuzzy matching for markets until no progress can be made
    while True:
        if not leftover.strip():
            logging.debug("Leftover empty, breaking market fuzzy loop.")
            break

        # Remove filler words before each attempt
        tokens_clean = [w for w in leftover.split() if w not in COMMON_FILLER_WORDS]
        if not tokens_clean:
            logging.debug("Only filler words left in leftover, stopping fuzzy matching.")
            break
        leftover = " ".join(tokens_clean)

        old_leftover = leftover
        best_score = 0
        best_match = None
        best_market_name = None

        if len(leftover) < 2:
            logging.debug("Leftover too short for meaningful fuzzy match, breaking.")
            break

        # Fuzzy match leftover against all known market aliases
        for (mkt_name, raw_alias, alias_norm) in all_market_aliases:
            score = fuzz.ratio(leftover, alias_norm)
            if score > best_score:
                best_score = score
                best_match = raw_alias
                best_market_name = mkt_name

        logging.debug(f"Best fuzzy match score: {best_score}, Market: {best_market_name}, Match: {best_match}")

        ADJUSTED_THRESHOLD = FUZZY_THRESHOLD
        if best_score >= ADJUSTED_THRESHOLD and best_match:
            if best_market_name not in identified_markets:
                identified_markets.append(best_market_name)
            match_tokens = best_match.lower().split()
            leftover_tokens2 = leftover.split()
            seq_idx = find_sequence([normalize_text(t) for t in leftover_tokens2],
                                    [normalize_text(mt) for mt in match_tokens])
            if seq_idx != -1:
                del leftover_tokens2[seq_idx:seq_idx+len(match_tokens)]
            else:
                # Token-by-token removal as fallback
                mt_copy = match_tokens[:]
                new_tokens = []
                for tok in leftover_tokens2:
                    ntok = normalize_text(tok)
                    if ntok in mt_copy:
                        mt_copy.remove(ntok)
                    else:
                        new_tokens.append(tok)
                leftover_tokens2 = new_tokens
            leftover = " ".join(leftover_tokens2)
            logging.debug(f"After removing matched market alias, leftover: {leftover}")
        else:
            logging.debug("No good market match found or score below threshold, breaking.")
            break

        if leftover == old_leftover:
            logging.debug("Leftover did not change this iteration, breaking to avoid infinite loop.")
            break

    # Remove filler words once more at the end
    leftover_tokens = [w for w in leftover.split() if w not in COMMON_FILLER_WORDS]
    logging.debug(f"Final leftover after market removal: {leftover_tokens}")

    final_teams = []
    for tm in identified_teams:
        if tm not in teams_data:
            logging.debug(f"Handling unknown team: {tm}")
            main_team = handle_unknown_team(tm, data_manager, prompt_user_for_classification)
            final_teams.append(main_team)
        else:
            final_teams.append(tm)

    # If no identified markets but we have teams and leftover includes "win", add "match odds"
    if not identified_markets and final_teams:
        if "win" in leftover_tokens:
            identified_markets.append("match odds")
            leftover_tokens = [t for t in leftover_tokens if t not in ("win","to")]

    identified = {
        "teams": final_teams,
        "markets": identified_markets,
        "unrecognized": []
    }

    # Correct score handling
    score_pattern = re.compile(r"(\d+)-(\d+)")
    logging.debug(f"Leftover tokens before score detection: {leftover_tokens}")
    scores_found = score_pattern.findall(" ".join(leftover_tokens))
    logging.debug(f"Scores found: {scores_found}")
    if scores_found:
        identified_scores = []
        for sg in scores_found:
            home_goals = int(sg[0])
            away_goals = int(sg[1])
            identified_scores.append((home_goals, away_goals))

        # Remove these scores from leftover_tokens
        new_tokens = leftover_tokens[:]
        for (hg, ag) in identified_scores:
            s_str = f"{hg}-{ag}"
            if s_str in new_tokens:
                new_tokens.remove(s_str)
        leftover_tokens = new_tokens

        identified["scores"] = identified_scores

        # If we found scores but not the "correct score" market
        if "correct score" not in identified_markets:
            identified_markets.append("correct score")
            identified["markets"] = identified_markets

    if leftover_tokens:
        identified["unrecognized"].append(" ".join(leftover_tokens))

    # If no teams or markets identified at all, log a warning (might indicate input issues)
    if not identified["teams"] and not identified["markets"]:
        logging.warning("No teams or markets identified. Check input or configuration.")

    logging.debug(f"parse_bet result: {identified}")
    return identified
