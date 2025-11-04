# betfair_integration.py

import re
import math
import logging
from datetime import datetime
from typing import List, Dict
from rapidfuzz import fuzz
from betfair_client import BetfairClient
from market_mapping import map_market_name_to_type
from config import config

# Load SPORT_EVENT_TYPE_IDS from config to allow easy changes in config.json
SPORT_EVENT_TYPE_IDS = config.get("sport_event_type_ids", {
    "football": "1",
    "nba": "7522",
    "nfl": "6423",
    "nhl": "7524"
})

def infer_sport_from_market(market: str) -> str:
    """
    Infer the sport from a given market string by checking for known sport indicators in the market name.

    :param market: The market name string.
    :return: The inferred sport name (e.g., 'football', 'nba', 'nfl', 'nhl').
    """
    market = market.lower()
    if "_nba" in market or "nba" in market:
        return "nba"
    elif "_nfl" in market or "nfl" in market:
        return "nfl"
    elif "_nhl" in market or "nhl" in market:
        return "nhl"
    return "football"


class BetfairIntegration:
    """
    Provides a higher-level interface to fetch events and market data from Betfair,
    integrating with BetfairClient for API access and performing additional logic like:
      - Finding events for a given team
      - Scoring events based on how closely they match a team name
      - Picking the best event, market, and runner based on fuzzy logic and given criteria
      - Fetching lay prices for specific runners

    Dependencies:
      - Relies on BetfairClient for API calls.
      - Uses SPORT_EVENT_TYPE_IDS from config, making it easy to adapt to new sports.

    Potential Future Improvements:
      - Inject BetfairClient as a dependency for easier testing.
      - Extract scoring logic into separate functions or classes.
      - Handle more sports or market variations by reading from config instead of hardcoding logic here.
    """

    def __init__(self):
        self.client = BetfairClient()
        self.client.login()

    def find_events_for_team(self, team_name: str, sport_id="1") -> List[dict]:
        """
        Find events from Betfair that match a given team name.

        :param team_name: The name of the team to search events for.
        :param sport_id: The eventTypeId from Betfair's API (e.g., '1' for football).
        :return: A list of event dictionaries if found, else an empty list.
        """
        filter_dict = {
            "filter": {
                "eventTypeIds": [sport_id],
                "textQuery": team_name
            }
        }
        response = self.client.list_events(filter_dict)
        if response and len(response) > 0 and "result" in response[0]:
            return response[0]["result"]
        logging.debug(f"No events found for team '{team_name}' and sport_id '{sport_id}'. Returning empty list.")
        return []

    def score_team_in_name(self, side_name: str, team_name: str) -> int:
        """
        Score how closely a side_name (e.g., from an event) matches the given team_name.
        High score means a closer match.

        Logic:
          - Exact match returns a high score (300).
          - If side_name starts with team_name, score is high but reduced by length difference.
          - Else, use fuzzy matching (ratio).

        :param side_name: The team/side name from an event.
        :param team_name: The team name we are searching for.
        :return: An integer score.
        """
        side = side_name.lower().strip()
        team = team_name.lower().strip()
        if side == team:
            return 300
        elif side.startswith(team):
            diff = len(side) - len(team)
            return max(1, 250 - diff * 10)
        else:
            fuzzy_score = fuzz.ratio(team, side)
            return fuzzy_score

    def score_event(self, event_name: str, team_name: str) -> int:
        # Split on “ v ”, “ vs ” or “ @ ” (case-insensitive)
        parts = re.split(r"\s+v\s+|\s+vs\s+|\s+@\s+", event_name, flags=re.IGNORECASE)
        if len(parts) == 2:
            side1, side2 = parts
            score1 = self.score_team_in_name(side1, team_name)
            score2 = self.score_team_in_name(side2, team_name)
            return max(score1, score2)
        else:
            return self.score_team_in_name(event_name, team_name)

    def pick_best_event(self, events: List[dict], team_name: str) -> dict:
        """
        From a list of events, pick the best one that matches the given team_name.

        Sorts events by score (descending) and by start time (ascending) to pick the most relevant upcoming event.

        :param events: A list of event dictionaries (as returned by Betfair).
        :param team_name: The team name to match.
        :return: The best matching event dictionary or None if none are suitable.
        """
        if not events:
            logging.debug("No events provided to pick_best_event. Returning None.")
            return None
        scored = []
        for e in events:
            evt = e["event"]
            s = self.score_event(evt["eventName"], team_name)
            start_time = datetime.fromisoformat(evt["openDate"].replace('Z', '+00:00'))
            scored.append((s, start_time, e))
        scored.sort(key=lambda x: (-x[0], x[1]))
        best = scored[0]
        if best[0] < 1:
            logging.debug(f"No event scored above 1 for team '{team_name}'. Returning None.")
            return None
        return best[2]

    def find_market_catalogues(self, event_id: str, market_types: List[str]) -> List[dict]:
        """
        Find market catalogues for a specific event and given market types.

        :param event_id: The ID of the event to search markets for.
        :param market_types: A list of market type codes.
        :return: A list of market catalogue dictionaries if found, else empty.
        """
        filter_dict = {
            "filter": {
                "eventIds": [event_id],
                "marketTypeCodes": market_types
            },
            "maxResults": 100,
            "marketProjection": ["RUNNER_DESCRIPTION"]
        }
        response = self.client.list_market_catalogue(filter_dict)
        if response and len(response) > 0 and "result" in response[0]:
            return response[0]["result"]
        logging.debug(f"No market catalogues found for event_id={event_id} and market_types={market_types}")
        return []

    def pick_best_market(self, catalogues: List[dict], desired_market: str) -> dict:
        """
        Choose the best market from a list of catalogues for the desired market name.

        Currently returns the first catalogue. In the future, you could add logic
        to pick the closest match or apply more sophisticated selection criteria.

        :param catalogues: A list of market catalogue dictionaries.
        :param desired_market: A human-readable market name requested by the user.
        :return: The chosen market catalogue dictionary or None if none found.
        """
        if not catalogues:
            logging.debug(f"No catalogues provided to pick_best_market for '{desired_market}'. Returning None.")
            return None
        return catalogues[0]

    def get_best_lay_price_for_runner(self, market_id: str, selection_id: int) -> float:
        """
        Get the best available lay price for a given runner in a specified market.

        :param market_id: The ID of the market.
        :param selection_id: The selection ID for the runner.
        :return: The best lay price as a float, or None if not available.
        """
        book_req = {
            "marketIds": [market_id],
            "priceProjection": {
                "priceData": ["EX_BEST_OFFERS"]
            }
        }
        response = self.client.list_market_book(book_req)
        if response and len(response) > 0 and "result" in response[0]:
            result = response[0]["result"]
            if result and len(result) > 0:
                market_book = result[0]
                if "runners" in market_book:
                    for runner in market_book["runners"]:
                        if runner["selectionId"] == selection_id:
                            lay_offers = runner["ex"].get("availableToLay", [])
                            if lay_offers:
                                return lay_offers[0]["price"]
        logging.debug(f"No lay price found for runner {selection_id} in market {market_id}.")
        return None

    def pick_best_runner(self, runners: List[dict], team_name: str, market_types: List[str], market_name: str, event_name: str) -> dict:
        """
        Given a list of runners and a team, pick the best runner that matches the team and market criteria.

        Logic:
          - If HALF_TIME_FULL_TIME market, tries to match patterns like "Home/Home".
          - If MATCH_ODDS, tries exact match, else fuzzy logic.
          - If MATCH_ODDS_AND_BTTS or MATCH_ODDS_AND_OU_xx, attempts to find "team/yes" or "team/over" runners.
          - If OVER_UNDER_xx goals/corners, looks for 'over' runner.
          - If no direct or pattern match, attempts fuzzy logic as a last resort.

        This could be further modularized by extracting individual logic for each market type.

        :param runners: A list of runner dictionaries from a market catalogue.
        :param team_name: The team we are trying to match.
        :param market_types: The list of market type codes determined by map_market_name_to_type.
        :param market_name: The original market name requested by the user (may contain clues for certain markets).
        :param event_name: The event name to infer home/away sides if needed.
        :return: The chosen runner dictionary or None if no suitable match found.
        """
        team = team_name.lower().strip()

        # Extract home/away sides from event_name to determine context
        parts = re.split(r"\sv\s", event_name, flags=re.IGNORECASE)
        home_team = parts[0].strip() if len(parts) == 2 else None
        away_team = parts[1].strip() if len(parts) == 2 else None

        # Determine which side 'team_name' matches more closely
        # If no event sides or can't determine, default to home
        is_home_side = True
        if home_team and away_team:
            score_home = self.score_team_in_name(home_team, team_name)
            score_away = self.score_team_in_name(away_team, team_name)
            is_home_side = (score_home >= score_away)

         # If half-time/full-time market:
        if "HALF_TIME_FULL_TIME" in market_types:
            norm_home = home_team.lower().strip() if home_team else None
            norm_away = away_team.lower().strip() if away_team else None
            norm_team = team.lower().strip()

            team_side_name = norm_home if is_home_side and norm_home else (norm_away if norm_away else norm_team)
            other_side_name = norm_away if is_home_side and norm_away else (norm_home if norm_home else None)

            candidates = [
                f"{team_side_name.capitalize()}/{team_side_name.capitalize()}",
                f"{team_side_name.capitalize()}/Draw",
                f"{team_side_name.capitalize()}/{other_side_name.capitalize() if other_side_name else ''}",
                f"Draw/{team_side_name.capitalize()}",
                f"{other_side_name.capitalize() if other_side_name else ''}/{team_side_name.capitalize()}"
            ]

            candidates = [c for c in candidates if "/" in c and not c.endswith("/") and not c.startswith("/")]

            for candidate in candidates:
                for r in runners:
                    if r["runnerName"].strip().lower() == candidate.lower():
                        return r
            # fallback to fuzzy logic below

        # If it's match odds, try exact match first
        if "MATCH_ODDS" in market_types:
            for r in runners:
                runner_name = r["runnerName"].lower().strip()
                if runner_name == team:
                    return r

            # If no exact match found, fallback to fuzzy
            best_runner = None
            best_score_val = -1
            for r in runners:
                rname = r["runnerName"].lower().strip()
                score = fuzz.ratio(team, rname)
                if score > best_score_val:
                    best_score_val = score
                    best_runner = r
            return best_runner
        
        if "MATCH_ODDS_AND_BTTS" in market_types:
            desired_runner_name = f"{team}/yes"
            for r in runners:
                if r["runnerName"].lower().strip() == desired_runner_name.lower():
                    return r
            # fallback
            for r in runners:
                rn = r["runnerName"].lower()
                if team in rn and ("yes" in rn or "over" in rn):
                    return r

        if any(mt.startswith("MATCH_ODDS_AND_OU_") for mt in market_types):
            m = re.search(r"over\s*([0-9]+\.[0-9])\s*goals", market_name.lower())
            if m:
                ou_line = f"over {m.group(1)}"
                desired_runner_name = f"{team}/{ou_line}"
                for r in runners:
                    if r["runnerName"].lower().strip() == desired_runner_name.lower():
                        return r
            for r in runners:
                rn = r["runnerName"].lower()
                if team in rn and "over" in rn:
                    return r

        if any(mt.startswith("OVER_UNDER_") for mt in market_types):
            for r in runners:
                if "over" in r["runnerName"].lower():
                    return r

        if "TEAM_A_WIN_TO_NIL" in market_types or "TEAM_B_WIN_TO_NIL" in market_types:
            for r in runners:
                if r["runnerName"].lower().strip() == "yes":
                    return r

        if any("cornr" in mt.lower() for mt in market_types):
            for r in runners:
                if "over" in r["runnerName"].lower():
                    return r

        if any("first_half_goals" in mt.lower() for mt in market_types):
            for r in runners:
                if "over" in r["runnerName"].lower():
                    return r

        # fallback: "yes" or "over"
        for r in runners:
            rn = r["runnerName"].lower().strip()
            if "yes" in rn or "over" in rn:
                return r

        # final fallback: fuzzy match the team name

        # If no runner found by special logic, fallback to fuzzy
        best_runner = None
        best_score_val = -1
        for r in runners:
            rname = r["runnerName"].lower().strip()
            score = fuzz.ratio(team, rname)
            if score > best_score_val:
                best_score_val = score
                best_runner = r
        if not best_runner:
            logging.debug(f"No runner found that matches team '{team_name}' in market '{market_name}'.")
        return best_runner

    def fetch_best_lay_price_for_team_and_market(self, team_name: str, market_name: str, scores=None):
        """
        High-level method to find the best lay price for a given team and market scenario.

        Steps:
          - Infer sport from market name.
          - Find events for team and pick best event.
          - Determine market types from market_name and retrieve catalogue.
          - Pick best market and runner.
          - If CORRECT_SCORE and multiple scores, compute combined odds.
          - Otherwise, return the single best lay price.

        :param team_name: The team name requested by user.
        :param market_name: The human-readable market name requested by user.
        :param scores: Optional list of score tuples if user requested correct score scenario.
        :return: Best lay price as float, combined odds if multiple correct scores, or None if not found.
        """
        sport = infer_sport_from_market(market_name)
        sport_id = SPORT_EVENT_TYPE_IDS.get(sport, "1")

        logging.debug(f"Fetching events for team '{team_name}' and market '{market_name}' (sport: {sport})...")
        events = self.find_events_for_team(team_name, sport_id=sport_id)
        best_event = self.pick_best_event(events, team_name)
        if not best_event:
            logging.debug(f"No suitable event found for team '{team_name}' in sport '{sport}'. Returning None.")
            return None

        evt = best_event["event"]
        logging.info(f"Selected Event: '{evt['eventName']}' (ID={evt['id']}, Start={evt['openDate']})")

        original_market_name = market_name.strip().lower()
        market_types = map_market_name_to_type(market_name, sport=sport)

        # Handle "to win to nil" special case
        if original_market_name == "to win to nil":
            event_name = evt["eventName"]
            parts = re.split(r"\sv\s", event_name, flags=re.IGNORECASE)
            if len(parts) == 2:
                side1, side2 = parts
                s1 = self.score_team_in_name(side1, team_name)
                s2 = self.score_team_in_name(side2, team_name)
                if s1 >= s2:
                    market_types = ["TEAM_A_WIN_TO_NIL"]
                else:
                    market_types = ["TEAM_B_WIN_TO_NIL"]
            else:
                market_types = ["TEAM_A_WIN_TO_NIL"]

        catalogues = self.find_market_catalogues(evt["id"], market_types)
        if not catalogues:
            logging.info(f"No suitable market found for '{market_name}' in event {evt['eventName']}. Returning None.")
            return None

        logging.debug(f"Found {len(catalogues)} market catalogue(s) for the event.")
        for c in catalogues:
            logging.debug(f"  MarketName='{c['marketName']}', MarketId={c['marketId']}, StartTime={c.get('marketStartTime')}")

        best_market = self.pick_best_market(catalogues, market_name)
        if not best_market:
            logging.debug(f"No suitable market found for '{market_name}' after filtering. Returning None.")
            return None

        logging.info(f"Selected Market: '{best_market['marketName']}' (ID={best_market['marketId']})")

        runners = best_market.get("runners", [])
        if not runners:
            logging.debug("No runners found in the selected market. Returning None.")
            return None

        if "CORRECT_SCORE" in market_types and scores:
            # Multiple correct scores scenario
            all_prices = []
            event_name = evt["eventName"]
            parts = re.split(r"\sv\s", event_name, flags=re.IGNORECASE)
            is_home = True
            if len(parts) == 2:
                side1, side2 = parts
                s1 = self.score_team_in_name(side1, team_name)
                s2 = self.score_team_in_name(side2, team_name)
                if s2 > s1:
                    is_home = False

            for score in scores:
                user_home_goals, user_away_goals = score
                if not is_home:
                    user_home_goals, user_away_goals = user_away_goals, user_home_goals

                runner_name = f"{user_home_goals} - {user_away_goals}"
                best_runner = None
                for r in runners:
                    if r["runnerName"].strip().lower() == runner_name.lower():
                        best_runner = r
                        break

                if not best_runner:
                    logging.info(f"No suitable runner found for score '{runner_name}' in correct score market.")
                    continue

                logging.info(f"Selected Runner: '{best_runner['runnerName']}' (SelectionId={best_runner['selectionId']}) for score {score}")
                price = self.get_best_lay_price_for_runner(best_market["marketId"], best_runner["selectionId"])
                if price is not None:
                    logging.info(f"Best Lay Price for {runner_name}: {price}")
                    all_prices.append(price)
                else:
                    logging.info(f"No lay price found for {runner_name}.")

            if not all_prices:
                logging.debug("No lay prices found for any of the given correct scores. Returning None.")
                return None

            # Combine probabilities for multiple correct scores
            probabilities = [1.0/p for p in all_prices]
            total_prob = sum(probabilities)
            combined_odds = 1.0 / total_prob
            combined_odds_rounded = math.ceil(combined_odds * 10) / 10.0

            logging.debug("Multiple correct scores found. Combined probability calculation:")
            logging.debug(f"Prices: {all_prices}")
            logging.debug(f"Probabilities: {[round(prob,4) for prob in probabilities]}")
            logging.debug(f"Total Probability: {round(total_prob,4)}")
            logging.debug(f"Combined Odds (rounded up): {combined_odds_rounded}")

            return combined_odds_rounded
        else:
            # Normal scenario
            best_runner = self.pick_best_runner(runners, team_name, market_types, market_name, evt["eventName"])
            if not best_runner:
                logging.debug(f"No suitable runner found for team '{team_name}' in market '{market_name}'. Returning None.")
                return None

            logging.info(f"Selected Runner: '{best_runner['runnerName']}' (SelectionId={best_runner['selectionId']})")
            price = self.get_best_lay_price_for_runner(best_market["marketId"], best_runner["selectionId"])
            if price is not None:
                logging.info(f"Best Lay Price: {price}")
            else:
                logging.debug("No lay price found for the selected runner. Returning None.")
            return price
