import os
import json
import base64
import requests

from dotenv import load_dotenv


load_dotenv()


# ============================================================
# Configuration
# ============================================================

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

SETS_PATH = (
    "/Users/anas/Projects/pkmn-analysis/"
    "data/pokemon-sets.json"
)

OUTPUT_PATH = (
    "/Users/anas/Projects/pkmn-analysis/"
    "data/ebay-listings.json"
)

MARKETPLACE_ID = "EBAY_US"


# ============================================================
# eBay authentication
# ============================================================

credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"

encoded = base64.b64encode(
    credentials.encode()
).decode()


headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Authorization": f"Basic {encoded}"
}


data = {
    "grant_type": "client_credentials",
    "scope": "https://api.ebay.com/oauth/api_scope"
}


response = requests.post(
    "https://api.ebay.com/identity/v1/oauth2/token",
    headers=headers,
    data=data
)

response.raise_for_status()

token = response.json()["access_token"]

print("Successfully authenticated with eBay.")


# ============================================================
# eBay search
# ============================================================

def search_ebay(
    token,
    query
):
    url = (
        "https://api.ebay.com/"
        "buy/browse/v1/item_summary/search"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID
    }

    items = []

    offset = 0

    while True:

        params = {
            "q": query,
            "offset": offset,
            "limit": 200
        }

        response = requests.get(
            url,
            headers=headers,
            params=params
        )

        response.raise_for_status()

        data = response.json()

        batch = data.get(
            "itemSummaries",
            []
        )

        items.extend(batch)

        print(
            f"    Retrieved {len(batch)} items "
            f"(total: {len(items)})"
        )

        if not data.get("next"):
            break

        if not batch:
            break

        offset += len(batch)

    return items


# ============================================================
# Load existing results
# ============================================================

def load_existing_results():

    if not os.path.exists(OUTPUT_PATH):
        return {}

    try:

        with open(
            OUTPUT_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return {}


# ============================================================
# Save results
# ============================================================

def save_results(results):

    os.makedirs(
        os.path.dirname(OUTPUT_PATH),
        exist_ok=True
    )

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# Load Pokémon sets
# ============================================================

with open(
    SETS_PATH,
    "r",
    encoding="utf-8"
) as file:

    pokemon_sets = json.load(file)


results = load_existing_results()


# ============================================================
# Process every card
# ============================================================

total_cards = 0

for pokemon_set in pokemon_sets.values():

    set_name = pokemon_set["name"]

    print(
        f"\n=========================================="
    )

    print(
        f"Set: {set_name}"
    )

    print(
        f"=========================================="
    )

    hits_rarities = pokemon_set.get(
        "hitsRarities",
        []
    )

    for rarity in hits_rarities:

        concerned_cards = rarity.get(
            "concernedCards",
            []
        )

        for card in concerned_cards:

            card_name = card["name"]
            card_number = card["number"]

            total_cards += 1

            # ------------------------------------------------
            # Create search query
            # ------------------------------------------------

            query = (
                f"{card_name} "
                f"{card_number} "
                f"{set_name}"
            )

            print(
                f"\nSearching:"
            )

            print(
                f"  {query}"
            )

            # ------------------------------------------------
            # Check cache
            # ------------------------------------------------

            if (
                set_name in results
                and card_number in results[set_name]
            ):

                print(
                    "  Already searched. Skipping."
                )

                continue

            # ------------------------------------------------
            # Search eBay
            # ------------------------------------------------

            try:

                items = search_ebay(
                    token,
                    query
                )

                processed_items = []

                for item in items:
                    processed_item = {
                        "itemId": item.get("itemId"),
                        "title": item.get("title"),
                        "publishDate": item.get("itemCreationDate"),
                        "price": item.get("price", {}).get("value") + " " + item.get("price", {}).get("currency"),
                        "condition": item.get("condition"),
                        "itemWebUrl": item.get("itemWebUrl")
                    }

                    processed_items.append(processed_item)

                # ------------------------------------------------
                # Save result
                # ------------------------------------------------

                if set_name not in results:

                    results[set_name] = {}

                results[set_name][card_number] = {

                    "cardName": card_name,

                    "cardNumber": card_number,

                    "setName": set_name,

                    "query": query,

                    "itemCount": len(items),

                    "items": processed_items
                }

                # Save immediately
                save_results(results)

                print(
                    f"  Found {len(items)} listings."
                )

            except requests.exceptions.HTTPError as error:

                print(
                    f"  eBay request failed: {error}"
                )

                # Don't mark failed requests as complete.
                # They can be retried next run.
                continue

            except Exception as error:

                print(
                    f"  Unexpected error: {error}"
                )

                continue


print(
    f"\nFinished processing {total_cards} cards."
)

print(
    f"Results written to: {OUTPUT_PATH}"
)