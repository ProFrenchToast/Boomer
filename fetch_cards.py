import requests
import json
import time
from typing import List, Dict, Set

SCRYFALL_API = "https://api.scryfall.com"
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

def fetch_high_inclusion_cards(threshold_percent: float = 20.0) -> List[Dict]:
    """
    Fetch cards with high inclusion rates in EDH decks.

    Note: Since EDHREC doesn't provide global inclusion rates easily,
    we'll use Scryfall's EDHREC rank as a proxy. Lower rank = higher inclusion.

    We'll fetch top N cards by EDHREC rank and estimate inclusion.
    """
    print(f"Fetching high-inclusion cards (>{threshold_percent}% inclusion)...")
    print("  Note: Using Scryfall EDHREC rank as proxy for inclusion rate")

    cards = []

    # Scryfall's EDHREC ranking goes from 1 (most played) upward
    # Approximately top 1000-1500 cards have >20% inclusion in the format
    # We'll fetch cards sorted by EDHREC rank and estimate inclusion

    # For simplicity, we'll fetch the top N cards by EDHREC rank
    # This is an approximation since exact inclusion % isn't readily available

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

    # Fetch top cards by EDHREC rank
    # We'll use an estimated cutoff based on rank
    # Typically, cards ranked < 1500 have >20% inclusion
    max_rank_for_threshold = 1500

    page = 1
    while url:
        print(f"  Fetching page {page}...")
        response = requests.get(url, params=params if page == 1 else None, headers=headers)

        if response.status_code != 200:
            print(f"  Error: {response.status_code} - {response.text}")
            break

        data = response.json()

        for card in data.get("data", []):
            edhrec_rank = card.get("edhrec_rank")

            if edhrec_rank and edhrec_rank <= max_rank_for_threshold:
                # Rough estimate: rank 1 = ~80% inclusion, rank 1500 = ~20% inclusion
                estimated_inclusion = max(20.0, 80.0 - (edhrec_rank / 25))

                cards.append({
                    "name": card.get("name"),
                    "oracle_text": card.get("oracle_text", ""),
                    "reason": f"high_inclusion: ~{estimated_inclusion:.1f}%",
                    "edhrec_rank": edhrec_rank
                })
            elif edhrec_rank and edhrec_rank > max_rank_for_threshold:
                # Once we pass the threshold, we can stop
                print(f"  Reached rank threshold ({edhrec_rank} > {max_rank_for_threshold}), stopping")
                url = None
                break

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
        else:
            if card["reason"] not in card_dict[name]["reasons"]:
                card_dict[name]["reasons"].append(card["reason"])
            if "edhrec_rank" in card:
                card_dict[name]["edhrec_rank"] = card["edhrec_rank"]

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
    high_inclusion = fetch_high_inclusion_cards(threshold_percent=20.0)

    merged_cards = merge_card_lists(commander_only, high_inclusion)

    output_file = "boomer_card_list.json"
    print(f"\nWriting results to {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_cards, f, indent=2, ensure_ascii=False)

    print(f"Done! Generated list with {len(merged_cards)} cards.")
    print(f"\nOutput saved to: {output_file}")

if __name__ == "__main__":
    main()
