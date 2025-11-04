import re
import logging

def parse_multiple_matches(input_str: str, pick="home"):
    """
    Parse an input string containing multiple matches and return selected teams based on the 'pick' parameter.

    **What it Does:**
    - Splits the input by commas and ampersands (&) to handle multiple matches.
    - Removes optional time annotations (e.g. "(20:00)").
    - Extracts home and away teams from segments in the form "TeamA v TeamB".
    - Based on the 'pick' parameter, returns either the home or away teams for each match.

    **Parameters:**
    - input_str (str): A string containing one or more matches separated by commas or '&'.
      Matches are typically in the format "HomeTeam v AwayTeam".
    - pick (str): Determines which team to return from each match.
      - "home" returns the home teams.
      - "away" returns the away teams.
      Defaults to "home".

    **Example Inputs:**
      - "Ajax v Lazio & Rangers v Tottenham"
        If pick="home", returns ["Ajax", "Rangers"].
        If pick="away", returns ["Lazio", "Tottenham"].
      
      - "AC Omonia Nicosia v Rapid (20:00), Shamrock Rovers v FK Borac Banja Luka (20:00)"
        Removes times, then:
        If pick="home", returns ["AC Omonia Nicosia", "Shamrock Rovers"].

    **Return Value:**
    - A list of teams (strings) corresponding to the chosen side (home or away) from each identified match.
    - If a segment doesn't contain " v ", it's ignored.
    - If no matches are found, returns an empty list.

    **Error Handling:**
    - If 'pick' is not "home" or "away", logs a warning and defaults to "home".
    - If no valid matches are found, returns an empty list without raising errors.

    **Future Improvements:**
    - Allow configurable delimiters or time patterns from a config file.
    - Introduce fuzzy matching if team names are not well-formed.
    - Split logic into separate functions for removing times, splitting matches, and extracting teams for better testability.

    :param input_str: A string containing one or more matches.
    :param pick: "home" or "away", determining which team from each match to return.
    :return: A list of selected teams according to the 'pick' parameter.
    """
    logging.debug(f"Parsing multiple matches from input: '{input_str}' with pick='{pick}'")

    # Validate 'pick' parameter
    if pick not in ["home", "away"]:
        logging.warning(f"Invalid pick value '{pick}'. Defaulting to 'home'.")
        pick = "home"

    # Replace '&' with ',' for uniform splitting
    input_str = input_str.replace("&", ",")
    segments = [seg.strip() for seg in input_str.split(",") if seg.strip()]

    matches = []
    time_pattern = re.compile(r"\(\d{1,2}:\d{2}\)")

    for seg in segments:
        seg_no_time = time_pattern.sub("", seg).strip()
        logging.debug(f"Processing segment: '{seg_no_time}'")

        # Split by " v "
        if " v " in seg_no_time:
            home_team, away_team = seg_no_time.split(" v ", 1)
            home_team = home_team.strip()
            away_team = away_team.strip()
            logging.debug(f"Found match: Home='{home_team}', Away='{away_team}'")

            # Based on the 'pick' parameter, choose home or away
            chosen = home_team if pick == "home" else away_team
            matches.append(chosen)
            logging.debug(f"Selected team: '{chosen}'")
        else:
            logging.debug(f"No ' v ' found in segment '{seg_no_time}'. Ignoring this segment.")

    logging.debug(f"Final extracted teams: {matches}")
    return matches

# Example usage:
# input_1 = "Ajax v Lazio & Rangers v Tottenham"
# print("Home teams from input 1:", parse_multiple_matches(input_1, pick="home"))
# print("Away teams from input 1:", parse_multiple_matches(input_1, pick="away"))
#
# input_2 = ("AC Omonia Nicosia v Rapid (20:00), Shamrock Rovers v FK Borac Banja Luka (20:00), "
#            "St.Gallen v Vitória Guimarães (20:00), Paphos FC v NK Celje (20:00), Gent v TSC (20:00), "
#            "The New Saints v Panathinaikos (20:00), FK Mla Boleslav v Jagiellonia Bialystok (20:00)")
# print("Home teams from input 2:", parse_multiple_matches(input_2, pick="home"))
