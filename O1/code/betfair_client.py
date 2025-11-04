import json
import os
import logging
import betfairlightweight
from betfairlightweight.filters import market_filter, price_projection

from config import DATA_PATH, config

# Load paths from config
CERT_PATH = config.get("cert_path", "C:/Valuebet/O1/certificates")
CREDENTIALS_PATH = os.path.join(DATA_PATH, config.get("credentials_path", "credentials.json"))

def load_credentials():
    """
    Load Betfair API credentials from the credentials file specified in config.

    The credentials file is expected to be a JSON with keys:
    {
      "username": "...",
      "password": "...",
      "app_key": "..."
    }

    If the file is missing or malformed, this function logs an error and returns an empty dict.
    Callers should check if credentials are present before attempting login.

    :return: A dictionary with keys 'username', 'password', 'app_key' if successful, else empty dict.
    """
    creds_path = CREDENTIALS_PATH
    try:
        logging.debug(f"Attempting to load credentials from {creds_path}")
        with open(creds_path, "r", encoding="utf-8") as f:
            creds = json.load(f)
        logging.debug("Credentials loaded successfully.")
        return creds
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading credentials: {e}")
        return {}


class BetfairClient:
    """
    A wrapper around Betfair's API client (betfairlightweight) to perform operations like:
    - Logging in with provided credentials
    - Listing events, market catalogues, and market books

    This class expects the following to be properly configured:
      - Credentials (username, password, app_key) via credentials_path in config.json
      - A certificate path (cert_path in config.json)

    Usage:
      - Instantiate BetfairClient()
      - Call .login() to authenticate
      - Use list_events(), list_market_catalogue(), list_market_book() to fetch data

    Error Handling:
      - If credentials are missing or invalid, login will fail with an error message.
      - If listing events/markets is attempted without login, the class will attempt to login again or log an error.
      - Network or API errors are logged as errors, and you may handle them by checking for empty results.
    """

    def __init__(self):
        logging.debug("Initializing BetfairClient with betfairlightweight.")
        self.creds = load_credentials()
        self.username = self.creds.get("username")
        self.password = self.creds.get("password")
        self.app_key = self.creds.get("app_key")
        self.trading = None

        if not self.username or not self.password or not self.app_key:
            logging.warning("Credentials incomplete or missing. Login attempts will fail until credentials are set properly.")

        logging.debug(f"BetfairClient initialized with username={self.username}, app_key={self.app_key}")

    def login(self):
        """
        Authenticate with the Betfair API using loaded credentials.

        If credentials are missing or invalid, logs an error and does not raise an exception.
        The caller should check if login was successful by checking if self.trading is not None.
        """
        if not (self.username and self.password and self.app_key):
            logging.error("Missing Betfair credentials (username/password/app_key). Check credentials configuration.")
            return

        logging.debug("Creating Betfair APIClient instance.")
        self.trading = betfairlightweight.APIClient(
            username=self.username,
            password=self.password,
            app_key=self.app_key,
            certs=CERT_PATH
        )

        try:
            logging.debug("Attempting login via betfairlightweight...")
            self.trading.login()
            logging.info("Login successful. Fetching prices from Betfair Exchange.")
        except betfairlightweight.exceptions.LoginError as e:
            logging.error(f"Login error: {e}. Please check your credentials.")
            self.trading = None
        except Exception as e:
            logging.error(f"Unexpected error during login: {e}")
            self.trading = None

    def list_events(self, filter_dict):
        """
        List events from Betfair based on a given filter.

        :param filter_dict: A dictionary with a "filter" key specifying eventTypeIds and/or textQuery.
                            Example:
                            {
                              "filter": {
                                "eventTypeIds": ["1"],
                                "textQuery": "Manchester"
                              }
                            }
        :return: A list containing a dictionary with "result" key. Example:
                 [{"result": [
                    {
                      "event": {"id": ..., "eventName": ..., "openDate": ...},
                      "marketCount": ...
                    }, ...
                 ]}]
                 If login fails or no trading session, returns [{"result": []}].
        """
        logging.debug(f"list_events called with filter_dict: {filter_dict}")
        if not self.trading:
            logging.warning("Not logged in. Attempting to login now.")
            self.login()
            if not self.trading:
                logging.error("Cannot list events without a successful login. Returning empty result.")
                return [{"result": []}]

        bf_filter = filter_dict.get("filter", {})
        eventTypeIds = bf_filter.get("eventTypeIds", [])
        textQuery = bf_filter.get("textQuery", "")

        m_filter = market_filter(
            event_type_ids=eventTypeIds if eventTypeIds else None,
            text_query=textQuery if textQuery else None
        )
        logging.debug(f"Constructed market_filter for list_events: {m_filter}")

        events = self.trading.betting.list_events(filter=m_filter)
        logging.debug(f"list_events returned {len(events)} events.")
        result = []
        for e in events:
            evt = e.event
            result.append({
                "event": {
                    "id": evt.id,
                    "eventName": evt.name,
                    "openDate": evt.open_date.isoformat()
                },
                "marketCount": e.market_count
            })
        return [{"result": result}]

    def list_market_catalogue(self, filter_dict):
        """
        List market catalogues for given events or market types.

        :param filter_dict: Should contain:
                            {
                              "filter": {
                                "eventIds": [...],
                                "marketTypeCodes": [...]
                              },
                              "maxResults": int,
                              "marketProjection": [...]
                            }
        :return: [{"result": [ { "marketId": ..., "marketName": ..., "runners": [...] }, ... ]}]
                 If not logged in, attempts login and returns empty result if still not available.
        """
        logging.debug(f"list_market_catalogue called with filter_dict: {filter_dict}")
        if not self.trading:
            logging.warning("Not logged in. Attempting to login now.")
            self.login()
            if not self.trading:
                logging.error("Cannot list market catalogue without a successful login. Returning empty result.")
                return [{"result": []}]

        bf_filter = filter_dict.get("filter", {})
        maxResults = filter_dict.get("maxResults", 100)
        marketProjection = filter_dict.get("marketProjection", [])

        m_filter = market_filter(
            event_ids=bf_filter.get("eventIds"),
            market_type_codes=bf_filter.get("marketTypeCodes")
        )
        logging.debug(f"Constructed market_filter for list_market_catalogue: {m_filter}")

        catalogues = self.trading.betting.list_market_catalogue(
            filter=m_filter,
            max_results=maxResults,
            market_projection=marketProjection
        )
        logging.debug(f"list_market_catalogue returned {len(catalogues)} catalogues.")

        result = []
        for c in catalogues:
            runners = []
            for r in c.runners:
                runners.append({
                    "selectionId": r.selection_id,
                    "runnerName": r.runner_name
                })
            result.append({
                "marketId": c.market_id,
                "marketName": c.market_name,
                "marketStartTime": c.market_start_time.isoformat() if c.market_start_time else None,
                "runners": runners
            })
        return [{"result": result}]

    def list_market_book(self, filter_dict):
        """
        List the current state of one or more markets (market book), including runner odds.

        :param filter_dict: Should contain:
                            {
                              "marketIds": [...],
                              "priceProjection": {
                                "priceData": ["EX_BEST_OFFERS", ...]
                              }
                            }
        :return: [{"result": [ { "marketId": ..., "runners": [...] }, ... ]}]
                 If not logged in, attempts login and returns empty result if still not available.
        """
        logging.debug(f"list_market_book called with filter_dict: {filter_dict}")
        if not self.trading:
            logging.warning("Not logged in. Attempting to login now.")
            self.login()
            if not self.trading:
                logging.error("Cannot list market book without a successful login. Returning empty result.")
                return [{"result": []}]

        marketIds = filter_dict.get("marketIds", [])
        priceProjectionDict = filter_dict.get("priceProjection", {})
        price_data_list = priceProjectionDict.get("priceData", [])
        pd = price_data_list if price_data_list else None

        logging.debug(f"Preparing to call betting.list_market_book with marketIds={marketIds}, priceData={pd}")

        books = self.trading.betting.list_market_book(
            market_ids=marketIds,
            price_projection=price_projection(price_data=pd) if pd else None
        )
        logging.debug(f"list_market_book returned {len(books)} market books.")

        result = []
        for b in books:
            runners = []
            for r in b.runners:
                lay = [{"price": l.price, "size": l.size} for l in (r.ex.available_to_lay or [])]
                back = [{"price": lb.price, "size": lb.size} for lb in (r.ex.available_to_back or [])]
                runners.append({
                    "selectionId": r.selection_id,
                    "ex": {
                        "availableToLay": lay,
                        "availableToBack": back
                    }
                })
            result.append({
                "marketId": b.market_id,
                "runners": runners
            })
        return [{"result": result}]
