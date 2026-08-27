import base64
import csv
import json
import os
import re
import time
from datetime import datetime
import pandas as pd
import requests
from Crypto.Cipher import AES
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

load_dotenv()

PRICES_CSV_PATH = os.path.join("livedata", "price_history.csv")
EBAY_CSV_PATH = os.path.join("livedata", "ebay_posts.csv")
POKEMON_SETS_JSON_PATH = os.path.join(".", "pokemon-sets.json")
TOKEN_FILE = "./ebay_token.json"

PRICES_HEADERS = [
    "t", "seriesId", "commercial_name", "hype_level", "age_level",
    "card_id", "name", "number", "rarity", "pokedex_id", "image",
    "current_offer", "current_demand", "cardmarket_price", "tcgplayer_price"
]

EBAY_HEADERS = [
    "card_id", "itemId", "title", "itemHref", "buyingOptions", "itemCreationDate", "price"
]

class EbayScraperPython:
    def __init__(self, marketplace_id="EBAY_FR"):
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.marketplace_id = marketplace_id
        self.french_labels = ["fr", "france", "français", "française", "🇫🇷"]

        if not self.client_id or not self.client_secret:
            raise ValueError("CLIENT_ID and CLIENT_SECRET must be set in .env")

    def get_ebay_token(self) -> str:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                token_data = json.load(f)
                if token_data.get("expires_at", 0) > int(time.time()):
                    return token_data["access_token"]

        response = requests.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}
        )
        response.raise_for_status()
        data = response.json()

        token_data = {
            "access_token": data["access_token"],
            "expires_at": int(time.time()) + data.get("expires_in", 7200)
        }
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f, indent=2)

        return data["access_token"]

    def search_fixed_price(self, query: str, only_french: bool = True):
        token = self.get_ebay_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            "Accept": "application/json"
        }
        params = {
            "q": query,
            "limit": "200",
            "filter": "conditionIds:{4000},buyingOptions:{FIXED_PRICE}"
        }

        resp = requests.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers=headers,
            params=params
        )
        if not resp.ok:
            return []

        data = resp.json()
        items = data.get("itemSummaries", [])

        if only_french:
            items = [
                item for item in items 
                if any(lbl in item.get("title", "").lower() for lbl in self.french_labels)
            ]

        return items

RARITIES_TO_EXCLUDE = [1, 2, 3, 4, 5, 6, 21, 32, 38, 39, 40]
RARITIES_LABEL = {
    1: [7],
    2: [33],
    3: [34],
    4: [35, 36, 43, 45, 47]
}

class PokecardexScraperPython:
    def __init__(self):
        self.key = os.getenv("KET", "").encode("utf-8")
        self.base_url = "https://www.pokecardex.com"
        
        # Standard HTTP session with desktop browser headers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def close(self):
        self.session.close()

    def decrypt_pokecardex(self, encrypted_payload: dict) -> dict:
        iv = base64.b64decode(encrypted_payload["iv"])
        ciphertext = base64.b64decode(encrypted_payload["data"])

        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        decrypted_raw = cipher.decrypt(ciphertext)

        pad_len = decrypted_raw[-1]
        if isinstance(pad_len, int) and pad_len <= 16:
            decrypted_raw = decrypted_raw[:-pad_len]

        return json.loads(decrypted_raw.decode("utf-8"))

    def fetch_and_decrypt_page(self, url: str) -> dict:
        response = self.session.get(url, timeout=15)
        response.raise_for_status()

        html = response.text
        marker = "window.__INITIAL_DATA_ENCRYPTED__"
        
        idx = html.find(marker)
        if idx == -1:
            raise ValueError(f"Could not find encrypted payload marker at {url}")

        start = html.find("{", idx)
        end = html.find("};", start)
        if start == -1 or end == -1:
            raise ValueError(f"Malformed payload indices at {url}")

        json_str = html[start : end + 1]
        encrypted_data = json.loads(json_str)

        return self.decrypt_pokecardex(encrypted_data)

    def scrape_card_by_id(self, card_id: int) -> dict:
        card_url = f"{self.base_url}/carte/{card_id}"
        card_data = self.fetch_and_decrypt_page(card_url)
    
        offers = [
            {"offer_id": o["id_possession"], "user_id": o["id_user"], "number": str(o["quantite"])}
            for o in card_data.get("ventes", [])
        ]
        demands = [
            {"demand_id": d["id_recherche"], "user_id": d["id_user"], "number": str(d["achat"])}
            for d in card_data.get("recherches", [])
        ]

        # Extract price histories
        cm_points = (
            card_data.get("carte", {})
            .get("priceHistory", {})
            .get("cardmarket", {})
            .get("180", {})
            .get("points", [])
        )
        tcg_points = (
            card_data.get("carte", {})
            .get("priceHistory", {})
            .get("tcgplayer", {})
            .get("180", {})
            .get("points", [])
        )

        price_evolution_cm = [
            {"date": p["date"], "price": p.get("v_null_normale_avg30")} 
            for p in cm_points
        ]
        price_evolution_tcg = [
            {"date": p["date"], "price": p.get("tcg_holofoil_market")} 
            for p in tcg_points
        ]

        return {
            "card_id": card_id,
            "offers": offers,
            "demands": demands,
            "priceEvolutionCM": price_evolution_cm,
            "priceEvolutionTCG": price_evolution_tcg
        }

def ensure_csv_headers():
    os.makedirs(os.path.dirname(PRICES_CSV_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(EBAY_CSV_PATH), exist_ok=True)

    if not os.path.exists(PRICES_CSV_PATH):
        with open(PRICES_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(PRICES_HEADERS)

    if not os.path.exists(EBAY_CSV_PATH):
        with open(EBAY_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(EBAY_HEADERS)

def get_latest_time_step() -> int:
    if not os.path.exists(PRICES_CSV_PATH):
        return 0
    try:
        df = pd.read_csv(PRICES_CSV_PATH)
        if df.empty or "t" not in df.columns:
            return 0
        return int(df["t"].max())
    except Exception:
        return 0

def load_scraped_sets_data():
    if os.path.exists(POKEMON_SETS_JSON_PATH):
        with open(POKEMON_SETS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def run_daily_pipeline():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"{today_str}")

    ensure_csv_headers()

    ebay_scraper = EbayScraperPython("EBAY_FR")
    cards_scraper = PokecardexScraperPython()

    series_cards = load_scraped_sets_data()

    if os.path.exists(PRICES_CSV_PATH) and os.path.getsize(PRICES_CSV_PATH) > 0:
        df = pd.read_csv(PRICES_CSV_PATH)
    else:
        return                

    print(f"Today's date: {today_str}")
    for series_id, series_data in series_cards.items():
        price_rows = []
        ebay_rows = []

        print(f"Processing series: {series_id} with {len(series_data.get('cards', []))} cards.")
        commercial_name = series_data.get("commercialName", "")
        hype_level = series_data.get("hypeLevel", 0)
        age_level = series_data.get("ageLevel", 0)

        cards = series_data.get("cards", [])
        for i, card in enumerate(cards):
            card_id = card.get("id")
            card_name = card.get("name", "")
            card_number = card.get("number", "")
            
            last_checked_date = card.get("lastCheckedDate", "")

            if last_checked_date == today_str:
                print(f"Skipping card {card_name} (#{card_number}): Already checked today ({today_str}).")
                continue

            print(f"Processing card: {card_name} (number: {card_number})")
            last_date_obj = datetime.strptime(last_checked_date, "%Y-%m-%d") if last_checked_date else None
            
            card_df = df[df["card_id"] == card_id]
            current_t = int(card_df["t"].max() if not card_df.empty else 0)

            scraped_card_data = cards_scraper.scrape_card_by_id(card_id)

            current_offer = sum(int(o.get("number", 0)) for o in scraped_card_data.get("offers", []))
            current_demand = sum(int(d.get("number", 0)) for d in scraped_card_data.get("demands", []))

            cm_dict = {p["date"]: p.get("price") for p in scraped_card_data.get("priceEvolutionCM", []) if "date" in p}
            tcg_dict = {p["date"]: p.get("price") for p in scraped_card_data.get("priceEvolutionTCG", []) if "date" in p}

            all_dates = sorted(list(set(cm_dict.keys()).union(set(tcg_dict.keys()))))

            for date_str in all_dates:
                price_date_obj = datetime.strptime(date_str, "%Y-%m-%d")

                if last_date_obj and price_date_obj <= last_date_obj:
                    continue

                cm_price = cm_dict.get(date_str, "")
                tcg_price = tcg_dict.get(date_str, "")

                current_t += 1
                price_rows.append([
                    current_t,
                    series_id,
                    commercial_name,
                    hype_level,
                    age_level,
                    card_id,
                    card_name,
                    card_number,
                    card.get("rarity", ""),
                    card.get("pokedexId", ""),
                    card.get("image", ""),
                    current_offer,
                    current_demand,
                    cm_price if cm_price is not None else "",
                    tcg_price if tcg_price is not None else ""
                ])

            card["lastCheckedDate"] = today_str

            existing_ebay_item_ids = set()
            if os.path.exists(EBAY_CSV_PATH) and os.path.getsize(EBAY_CSV_PATH) > 0:
                ebay_df = pd.read_csv(EBAY_CSV_PATH)
                if "itemId" in ebay_df.columns:
                    existing_ebay_item_ids = set(ebay_df["itemId"].astype(str).tolist())

            try:
                card_number_with_leading_zeros = str(card_number).zfill(3)
                query = f"Pokémon {card_name} {card_number_with_leading_zeros}"
                ebay_items = ebay_scraper.search_fixed_price(query, only_french=True)

                fetched_item_ids = set()

                for item in ebay_items:
                    item_id = str(item.get("itemId", ""))
                    fetched_item_ids.add(item_id)

                    # Skip if this item ID was already recorded in the CSV previously
                    if item_id in existing_ebay_item_ids:
                        continue

                    buying_options = "|".join(item.get("buyingOptions", []))
                    price_val = item.get("price", {}).get("value", "")

                    ebay_rows.append([
                        card_id,
                        item_id,
                        item.get("title", ""),
                        item.get("itemWebUrl", ""),
                        buying_options,
                        item.get("itemCreationDate", datetime.utcnow().isoformat()),
                        price_val
                    ])

                    existing_ebay_item_ids.add(item_id)

                if "trackedEbayItemIds" in card:
                    card["trackedEbayItemIds"] = [
                        i_id for i_id in card["trackedEbayItemIds"] 
                        if i_id in fetched_item_ids
                    ]
                else:
                    card["trackedEbayItemIds"] = list(fetched_item_ids)

            except Exception as e:
                print(f"Failed to fetch eBay posts for card {card_id}: {e}")

        with open(POKEMON_SETS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(series_cards, f, indent=2, ensure_ascii=False)

        if price_rows:
            with open(PRICES_CSV_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(price_rows)
                
        if ebay_rows:
            with open(EBAY_CSV_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(ebay_rows)

    time.sleep(60)
    print(f"Pipeline execution finished successfully.")

if __name__ == "__main__":
    max_attempts = 5
    current_attempt = 0

    # while current_attempt < max_attempts:
    #     print(f"Attempt {current_attempt + 1} of {max_attempts}")
    #     try:
    #         run_daily_pipeline()
    #     except Exception as e:
    #         current_attempt += 1
    #         print(f"Attempt {current_attempt} failed: {e}")
    #         time.sleep(100)
    #     else:
    #         break

    # Sort price history CSV by 'card_id' and 't' columns to ensure chronological order
    if os.path.exists(EBAY_CSV_PATH) and os.path.getsize(EBAY_CSV_PATH) > 0:
        try:
            df_colums = [
                "card_id", "item_id", "post_title", "url", "type", "date", "price"
            ]
            df_ebay = pd.read_csv(
                EBAY_CSV_PATH,
                header=None,
                names=df_colums
            )

            df_ebay = df_ebay[df_colums]
            df_ebay.sort_values(by=["card_id", "date"], inplace=True)

            df_ebay.to_csv(
                EBAY_CSV_PATH,
                index=False,
                header=True
            )

            print(f"Sorted {EBAY_CSV_PATH} by 'card_id' and 't' with column names.")
        except Exception as e:
            print(f"Failed to sort {EBAY_CSV_PATH}: {e}")

    if os.path.exists(PRICES_CSV_PATH) and os.path.getsize(PRICES_CSV_PATH) > 0:
            try:
                df_prices = pd.read_csv(PRICES_CSV_PATH)
                df_prices.sort_values(by=["card_id", "t"], inplace=True)
    
                df_prices.to_csv(
                    PRICES_CSV_PATH,
                    index=False,
                    header=True
                )
    
                print(f"Sorted {PRICES_CSV_PATH} by 'card_id' and 't' with column names.")
            except Exception as e:
                print(f"Failed to sort {PRICES_CSV_PATH}: {e}")

    if current_attempt == max_attempts:
        print("Pipeline execution failed after maximum attempts.")