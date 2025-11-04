import re
import logging

def normalize_text(text: str) -> str:
    """
    Normalize text for alias matching.

    Steps performed:
      - Strip leading/trailing whitespace.
      - Convert to lowercase.
      - Remove apostrophes and right single quotes (’ and '), as these often don't matter for matching.
      - Retain hyphens and other characters that might distinguish certain aliases.
    
    Use Cases:
      - Pre-processing team, market, or player names before storing or matching against aliases.
    
    Example:
      Input: "  The O'Neill's "
      Output: "the oneills"

    :param text: The input string to normalize.
    :return: A normalized string suitable for fuzzy or direct alias matching.
    """
    logging.debug(f"Normalizing text: '{text}'")
    original = text
    text = text.strip().lower()
    text = re.sub(r"[’']", "", text)
    logging.debug(f"Normalized '{original}' to '{text}'")
    return text

def fully_normalize_input(input_str: str) -> str:
    """
    Fully normalize an input string for parsing bets or commands.

    Steps performed:
      - Convert to lowercase.
      - Replace standalone '&' with 'and'.
      - Remove all punctuation except letters, digits, spaces, dots, and hyphens.
      - Collapse multiple spaces into one.

    Use Cases:
      - Preparing complex user input (e.g. "Ajax & Lazio!!!") for parsing by removing unnecessary punctuation.
      - Ensuring consistent formatting for further processing by parsing logic (e.g., bet_parser).

    Example:
      Input: "  Ajax & Lazio!!! "
      Output: "ajax and lazio"

    :param input_str: The raw user input string.
    :return: A fully normalized string with simplified and consistent formatting.
    """
    logging.debug(f"Fully normalizing input: '{input_str}'")
    original = input_str
    text = input_str.lower()
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"\b&\b", "and", text)
    text = re.sub(r"[^\w\s.\-]", "", text)
    text = " ".join(text.split())
    logging.debug(f"Fully normalized '{original}' to '{text}'")
    return text
