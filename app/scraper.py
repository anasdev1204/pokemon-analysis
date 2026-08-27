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
        print(f"Fetching: {url}")
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
        print(f"Scraping Card ID: {card_id}")
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
    print(f"Starting daily pipeline...")
    ensure_csv_headers()

    current_t = get_latest_time_step() + 1
    print(f"Assigned Time Step (t): {current_t}")

    ebay_scraper = EbayScraperPython("EBAY_FR")
    cards_scraper = PokecardexScraperPython()

    series_cards = load_scraped_sets_data()

    if os.path.exists(PRICES_CSV_PATH) and os.path.getsize(PRICES_CSV_PATH) > 0:
        df = pd.read_csv(PRICES_CSV_PATH)
        if not df.empty:
            if "t" in df.columns and df["t"].notnull().any():
                current_t = int(df["t"].max())
    else:
        return                

    for series_id, series_data in series_cards.items():
        price_rows = []
        ebay_rows = []

        print(f"Processing series: {series_id} with {len(series_data.get('cards', []))} cards.")
        commercial_name = series_data.get("commercialName", "")
        hype_level = series_data.get("hypeLevel", 0)
        age_level = series_data.get("ageLevel", 0)


        for card in series_data.get("cards", []):
            print(f"Processing card: {card.get('name', '')} (number: {card.get('number', '')})")
            card_id = card.get("id")
            card_name = card.get("name", "")
            card_number = card.get("number", "")
            last_checked_date = card.get("lastCheckedDate", "")
            last_date_obj = datetime.strptime(last_checked_date, "%Y-%m-%d") if last_checked_date else None
            
            card_df = df[df["card_id"] == card_id]
            current_t = current_t = int(card_df["t"].max())
            print(f"Current Time Step (t) for card {card_id}: {current_t}")

            scraped_card_data = cards_scraper.scrape_card_by_id(card_id)

            cm_map = scraped_card_data["priceEvolutionCM"]
            prices_to_add = []

            for price in cm_map:
                price_date = price.get("date")
                price_value = price.get("price")

                is_date_after_last_checked = last_date_obj is None or (price_date and datetime.strptime(price_date, "%Y-%m-%d") > last_date_obj)

                if price_value is not None and is_date_after_last_checked:
                    prices_to_add.append(price_value)

            tcg_map = scraped_card_data["priceEvolutionTCG"]

            for price in tcg_map:
                price_date = price.get("date")
                price_value = price.get("price")

                is_date_after_last_checked = last_date_obj is None or (price_date and datetime.strptime(price_date, "%Y-%m-%d") > last_date_obj)

                if price_value is not None and is_date_after_last_checked:
                    prices_to_add.append(price_value)

            current_offer = sum(int(o.get("number", 0)) for o in scraped_card_data["offers"])
            current_demand = sum(int(d.get("number", 0)) for d in scraped_card_data["demands"])

            print(len(prices_to_add), f"new price points found for card {card_id}.")

            for cmprice, tcgprice in zip(cm_map, tcg_map):
                if cmprice.get("date") == tcgprice.get("date"):
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
                        cmprice.get("price", ""),
                        tcgprice.get("price", "")
                    ])

            try:
                card_number_with_leading_zeros = str(card_number).zfill(3)
                query = f"Pokémon {card_name} {card_number_with_leading_zeros}"
                print(f"Searching eBay for card: {query}")
                ebay_items = ebay_scraper.search_fixed_price(query, only_french=True)

                for item in ebay_items:
                    buying_options = "|".join(item.get("buyingOptions", []))
                    price_val = item.get("price", {}).get("value", "")

                    ebay_rows.append([
                        card_id,
                        item.get("itemId", ""),
                        item.get("title", ""),
                        item.get("itemWebUrl", ""),
                        buying_options,
                        item.get("itemCreationDate", datetime.utcnow().isoformat()),
                        price_val
                    ])
            except Exception as e:
                print(f"Failed to fetch eBay posts for card {card_id}: {e}")

        if price_rows:
            with open(PRICES_CSV_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(price_rows)
            print(f"Appended {len(price_rows)} rows to {PRICES_CSV_PATH}")

        if ebay_rows:
            with open(EBAY_CSV_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(ebay_rows)
            print(f"Appended {len(ebay_rows)} rows to {EBAY_CSV_PATH}")

        time.sleep(60)

    print(f"Pipeline execution finished successfully.")

if __name__ == "__main__":
    run_daily_pipeline()