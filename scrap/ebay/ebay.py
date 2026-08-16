import os
from dotenv import load_dotenv
import requests
import base64
import json

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

print(f"CLIENT_ID: {CLIENT_ID}")
print(f"CLIENT_SECRET: {CLIENT_SECRET}")

credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
encoded = base64.b64encode(credentials.encode()).decode()

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

token = response.json()["access_token"]

def search_ebay(token, query):
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
    }

    items = []
    offset = 0

    while True:

        params = {
            "q": query,
            "offset": offset
        }

        response = requests.get(
            url,
            headers=headers,
            params=params
        )

        response.raise_for_status()

        data = response.json()

        batch = data.get("itemSummaries", [])
        items.extend(batch)

        if not data.get("next"):
            break

        offset += len(batch)

    return items

items = search_ebay(
    token,
    "Cynthia's Roserade 184/182"
)

print(len(items))

print(
    json.dumps(items[0], indent=4)
)