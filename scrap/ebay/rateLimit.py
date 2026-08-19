import os
import json
import base64
import requests

from dotenv import load_dotenv


load_dotenv()


CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")


# ============================================================
# Get OAuth token
# ============================================================

def get_access_token():

    credentials = (
        f"{CLIENT_ID}:{CLIENT_SECRET}"
    )

    encoded = base64.b64encode(
        credentials.encode()
    ).decode()

    headers = {
        "Content-Type":
            "application/x-www-form-urlencoded",

        "Authorization":
            f"Basic {encoded}"
    }

    data = {
        "grant_type":
            "client_credentials",

        "scope":
            "https://api.ebay.com/oauth/api_scope"
    }

    response = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers=headers,
        data=data
    )

    response.raise_for_status()

    return response.json()["access_token"]


# ============================================================
# Get rate limits
# ============================================================

def get_rate_limits(token):

    url = (
        "https://api.ebay.com/"
        "developer/analytics/v1_beta/rate_limit/?api_name=browse"
    )

    headers = {
        "Authorization":
            f"Bearer {token}"
    }

    response = requests.get(
        url,
        headers=headers
    )

    print(
        "HTTP status:",
        response.status_code
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# Main
# ============================================================

def main():

    if not CLIENT_ID:
        raise RuntimeError(
            "CLIENT_ID is not set in .env"
        )

    if not CLIENT_SECRET:
        raise RuntimeError(
            "CLIENT_SECRET is not set in .env"
        )

    print(
        "Authenticating with eBay..."
    )

    token = get_access_token()

    print(
        "Authentication successful."
    )

    print(
        "\nRetrieving API rate limits..."
    )

    rate_limits = get_rate_limits(
        token
    )

    print(
        json.dumps(
            rate_limits,
            indent=4
        )
    )


if __name__ == "__main__":
    main()