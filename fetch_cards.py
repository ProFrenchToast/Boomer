import requests
import json
import time
import re
from typing import List, Dict, Set, Optional

SCRYFALL_API = "https://api.scryfall.com"
EDHREC_JSON_API = "https://json.edhrec.com/pages/cards"
USER_AGENT = "Boomer-MTG-Format/1.0"
RATE_LIMIT_DELAY = 0.1

def fetch_commander_only_cards() -> List[Dict]:
    """
    Fetch all cards that were only printed in Commander sets.
    Uses Scryfall query: st:commander -in:booster
    """
    print("Fetching Commander-only cards from Scryfall...")

    cards = []
    query = "st:commander -in:booster"
    url = f"{SCRYFALL_API}/cards/search"
    params = {
        "q": query,
        "unique": "cards"
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }

    page = 1
    while url:
        print(f"  Fetching page {page}...")
        response = requests.get(url, params=params if page == 1 else None, headers=headers)

        if response.status_code != 200:
            print(f"  Error: {response.status_code} - {response.text}")
            break

        data = response.json()

        for card in data.get("data", []):
            cards.append({
                "name": card.get("name"),
                "oracle_text": card.get("oracle_text", ""),
                "reason": "commander_only"
            })

        if data.get("has_more", False):
            url = data.get("next_page")
            page += 1
            time.sleep(RATE_LIMIT_DELAY)
        else:
            url = None

    print(f"  Found {len(cards)} Commander-only cards")
    return cards

def sanitize_card_name(name: str) -> str:
    """
    Sanitize card name for EDHREC URL format.
    Example: "Uril, the Miststalker" -> "uril-the-miststalker"
    """
    sanitized = name.lower()
    sanitized = re.sub(r'[^a-z0-9\s-]', '', sanitized)
    sanitized = re.sub(r'\s+', '-', sanitized)
    sanitized = re.sub(r'-+', '-', sanitized)
    return sanitized.strip('-')

def get_edhrec_inclusion(card_name: str) -> Optional[float]:
    """
    Fetch actual inclusion percentage from EDHREC JSON API.
    Returns None if the data is not available.
    """
    sanitized = sanitize_card_name(card_name)
    url = f"{EDHREC_JSON_API}/{sanitized}.json"

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT})
        if response.status_code != 200:
            return None

        data = response.json()
        label = data.get("container", {}).get("json_dict", {}).get("card", {}).get("label", "")

        # Parse label like: "In 700 decks \n0.09% of 814495 decks"
        match = re.search(r'(\d+\.?\d*)%', label)
        if match:
            return float(match.group(1))

        return None
    except Exception as e:
        print(f"    Warning: Could not fetch EDHREC data for {card_name}: {e}")
        return None

def fetch_high_inclusion_cards(threshold_percent: float = 7.5) -> List[Dict]:
    """
    Fetch cards with high inclusion rates in EDH decks.
    Uses actual inclusion data from EDHREC JSON API.
    Stops when we encounter a card below the threshold.
    """
    print(f"Fetching high-inclusion cards (>{threshold_percent}% inclusion)...")
    print("  Using actual EDHREC inclusion data")

    cards = []

    url = f"{SCRYFALL_API}/cards/search"
    query = "format:commander"
    params = {
        "q": query,
        "order": "edhrec",
        "unique": "cards"
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }

    page = 1
    cards_checked = 0

    while url:
        print(f"  Fetching Scryfall page {page}...")
        response = requests.get(url, params=params if page == 1 else None, headers=headers)

        if response.status_code != 200:
            print(f"  Error: {response.status_code} - {response.text}")
            break

        data = response.json()

        for card in data.get("data", []):
            cards_checked += 1
            card_name = card.get("name")
            edhrec_rank = card.get("edhrec_rank")

            if cards_checked % 25 == 0:
                print(f"    Checked {cards_checked} cards, found {len(cards)} above threshold...")

            # Fetch actual inclusion from EDHREC
            inclusion_percent = get_edhrec_inclusion(card_name)

            if inclusion_percent is None:
                # Skip cards without EDHREC data
                continue

            if inclusion_percent >= threshold_percent:
                cards.append({
                    "name": card_name,
                    "oracle_text": card.get("oracle_text", ""),
                    "reason": f"high_inclusion: {inclusion_percent:.2f}%",
                    "edhrec_rank": edhrec_rank,
                    "inclusion_percent": inclusion_percent
                })
            else:
                # Once we find a card below threshold, stop
                print(f"  Reached inclusion threshold: {card_name} has {inclusion_percent:.2f}% < {threshold_percent}%")
                print(f"  Stopping after checking {cards_checked} cards")
                url = None
                break

            # Rate limit for EDHREC API
            time.sleep(RATE_LIMIT_DELAY)

        if url and data.get("has_more", False):
            url = data.get("next_page")
            page += 1
            time.sleep(RATE_LIMIT_DELAY)
        else:
            url = None

    print(f"  Found {len(cards)} high-inclusion cards")
    return cards

def merge_card_lists(commander_only: List[Dict], high_inclusion: List[Dict]) -> List[Dict]:
    """
    Merge the two card lists, creating a union and combining reasons for duplicates.
    """
    print("\nMerging card lists...")

    card_dict = {}

    for card in commander_only:
        name = card["name"]
        if name not in card_dict:
            card_dict[name] = {
                "name": name,
                "oracle_text": card["oracle_text"],
                "reasons": [card["reason"]]
            }
        else:
            if card["reason"] not in card_dict[name]["reasons"]:
                card_dict[name]["reasons"].append(card["reason"])

    for card in high_inclusion:
        name = card["name"]
        if name not in card_dict:
            card_dict[name] = {
                "name": name,
                "oracle_text": card["oracle_text"],
                "reasons": [card["reason"]]
            }
            if "edhrec_rank" in card:
                card_dict[name]["edhrec_rank"] = card["edhrec_rank"]
            if "inclusion_percent" in card:
                card_dict[name]["inclusion_percent"] = card["inclusion_percent"]
        else:
            if card["reason"] not in card_dict[name]["reasons"]:
                card_dict[name]["reasons"].append(card["reason"])
            if "edhrec_rank" in card:
                card_dict[name]["edhrec_rank"] = card["edhrec_rank"]
            if "inclusion_percent" in card:
                card_dict[name]["inclusion_percent"] = card["inclusion_percent"]

    merged_cards = list(card_dict.values())

    # Sort by name for easier browsing
    merged_cards.sort(key=lambda x: x["name"])

    print(f"  Total unique cards: {len(merged_cards)}")
    print(f"  Commander-only: {len(commander_only)}")
    print(f"  High-inclusion: {len(high_inclusion)}")
    print(f"  Overlap: {len(commander_only) + len(high_inclusion) - len(merged_cards)}")

    return merged_cards

def main():
    print("Starting MTG card list generation for new format...\n")

    commander_only = fetch_commander_only_cards()
    high_inclusion = fetch_high_inclusion_cards(threshold_percent=3.5)

    merged_cards = merge_card_lists(commander_only, high_inclusion)

    output_file = "boomer_card_list.json"
    print(f"\nWriting results to {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_cards, f, indent=2, ensure_ascii=False)

    print(f"Done! Generated list with {len(merged_cards)} cards.")
    print(f"\nOutput saved to: {output_file}")

if __name__ == "__main__":
    main()
