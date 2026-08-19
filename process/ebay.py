# ============================================================
# Parse listings
# ============================================================
import json
import math
import os
import statistics
from datetime import datetime, timezone


INPUT_PATH = (
    "/Users/anas/Projects/pkmn-analysis/data/ebay-listings.json"
)

OUTPUT_PATH = (
    "/Users/anas/Projects/pkmn-analysis/data/processed"
    "/ebay-card-features.json"
)


# ============================================================
# Helpers
# ============================================================

def parse_price(price_string):
    """
    Converts:

        "1.99 USD"

    into:

        1.99
    """

    if not price_string:
        return None

    try:
        return float(
            price_string.split()[0]
        )

    except (ValueError, IndexError):
        return None


def parse_date(date_string):
    if not date_string:
        return None

    try:
        return datetime.fromisoformat(
            date_string.replace(
                "Z",
                "+00:00"
            )
        )

    except ValueError:
        return None


def listing_age_days(date_string):

    date = parse_date(
        date_string
    )

    if date is None:
        return None

    now = datetime.now(
        timezone.utc
    )

    return max(
        0,
        (
            now - date
        ).total_seconds()
        / 86400
    )


def median_or_zero(values):

    if not values:
        return 0

    return statistics.median(
        values
    )


def mean_or_zero(values):

    if not values:
        return 0

    return statistics.mean(
        values
    )


def stdev_or_zero(values):

    if len(values) < 2:
        return 0

    return statistics.stdev(
        values
    )


def percentile(values, percentile):

    if not values:
        return 0

    values = sorted(values)

    index = (
        percentile / 100
    ) * (len(values) - 1)

    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return values[lower]

    weight = index - lower

    return (
        values[lower]
        * (1 - weight)
        +
        values[upper]
        * weight
    )


# ============================================================
# Market status index helpers
# ============================================================
#
# The index combines four 0-100 sub-scores into a single
# "marketIndex" that summarizes how active/healthy a card's
# eBay market currently looks:
#
#   - liquidityScore : how much supply/turnover this card has
#                       relative to every other card in the set
#   - momentumScore   : whether recent prices are trending up
#                       or down vs. the longer-run baseline
#   - stabilityScore  : how tight/consistent pricing is
#   - freshnessScore  : what share of listings are recent
#                       (an active market vs. a stale one)
#
# marketIndex = 0.30*liquidity + 0.30*momentum
#             + 0.20*stability + 0.20*freshness
# ============================================================

def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def rank_percentile(value, all_values):
    """
    Returns the percentile (0-100) that `value` falls at
    within `all_values`. Used to turn raw counts/velocities
    into a relative, cross-card score.
    """

    if not all_values:
        return 50

    count_at_or_below = sum(
        1
        for v in all_values
        if v <= value
    )

    return 100 * count_at_or_below / len(all_values)


def momentum_score(recent_median, baseline_median):
    """
    Compares a recent price window against a longer baseline.
    50 = no change, >50 = rising prices, <50 = falling prices.
    Swings are capped at +/-50% so a single outlier can't blow
    the scale out.
    """

    if baseline_median <= 0 or recent_median <= 0:
        return 50

    pct_change = (
        (recent_median - baseline_median)
        / baseline_median
    )

    pct_change = max(-0.5, min(0.5, pct_change))

    return 50 + (pct_change / 0.5) * 50


def stability_score(mean_price, stdev_price):
    """
    Based on the coefficient of variation (stdev / mean).
    CV of 0 -> perfectly stable (100). CV of 1.0+ -> very
    volatile (0).
    """

    if mean_price <= 0:
        return 0

    coefficient_of_variation = stdev_price / mean_price

    return clamp(
        100 * (1 - min(coefficient_of_variation, 1))
    )


def freshness_score(recent_listing_ratio_30d):
    return clamp(recent_listing_ratio_30d * 100)


def market_status_label(market_index, listing_count):

    if listing_count == 0:
        return "No Data"

    if market_index >= 75:
        return "Hot"

    if market_index >= 60:
        return "Rising"

    if market_index >= 40:
        return "Stable"

    if market_index >= 25:
        return "Cooling"

    return "Illiquid"


# ============================================================
# Load data
# ============================================================

with open(
    INPUT_PATH,
    "r",
    encoding="utf-8"
) as file:

    ebay_data = json.load(file)


results = {}

# ============================================================
# Process sets
# ============================================================

for set_name, cards in ebay_data.items():

    print(
        f"\nProcessing set: {set_name}"
    )

    results[set_name] = {}

    # ========================================================
    # Process cards
    # ========================================================

    for card_number, card_data in cards.items():

        card_name = card_data.get(
            "cardName",
            ""
        )

        items = card_data.get(
            "items",
            []
        )

        print(
            f"  {card_name} "
            f"({card_number}) - "
            f"{len(items)} listings"
        )

        # ====================================================
        # Parse listings
        # ====================================================

        listings = []

        for item in items:

            price = parse_price(
                item.get("price")
            )

            if price is None:
                continue

            publish_date = item.get(
                "publishDate"
            )

            age = listing_age_days(
                publish_date
            )

            condition = (
                item.get("condition")
                or "Unknown"
            )

            listings.append({

                "itemId": item.get(
                    "itemId"
                ),

                "price": price,

                "condition": condition,

                "publishDate": publish_date,

                "ageDays": age,

                "title": item.get(
                    "title"
                ),

                "itemWebUrl": item.get(
                    "itemWebUrl"
                )
            })


        # ============================================================
        # Remove extreme overpriced listings
        # ============================================================

        initial_prices = [
            listing["price"]
            for listing in listings
        ]

        initial_median = median_or_zero(
            initial_prices
        )

        price_threshold = (
            initial_median * 2
        )


        valid_listings = [
            listing
            for listing in listings
            if listing["price"] <= price_threshold
        ]


        invalid_listings = [
            listing
            for listing in listings
            if listing["price"] > price_threshold
        ]


        print(
            f"    Initial listings: {len(listings)}"
        )

        print(
            f"    Initial median: ${initial_median:.2f}"
        )

        print(
            f"    Price threshold: ${price_threshold:.2f}"
        )

        print(
            f"    Valid listings: {len(valid_listings)}"
        )

        print(
            f"    Invalid listings: {len(invalid_listings)}"
        )


        # ============================================================
        # Use ONLY valid listings from this point onwards
        # ============================================================

        listings = valid_listings


        # ====================================================
        # Basic statistics
        # ====================================================

        prices = [
            listing["price"]
            for listing in listings
        ]


        # ====================================================
        # Recent listings
        # ====================================================

        listings_7d = [
            listing
            for listing in listings
            if listing["ageDays"] is not None
            and listing["ageDays"] <= 7
        ]

        listings_30d = [
            listing
            for listing in listings
            if listing["ageDays"] is not None
            and listing["ageDays"] <= 30
        ]

        listings_90d = [
            listing
            for listing in listings
            if listing["ageDays"] is not None
            and listing["ageDays"] <= 90
        ]


        # ====================================================
        # Condition distributions
        # ====================================================

        condition_prices = {}

        condition_counts = {}

        for listing in listings:

            condition = listing[
                "condition"
            ]

            condition_prices.setdefault(
                condition,
                []
            ).append(
                listing["price"]
            )

            condition_counts[
                condition
            ] = (
                condition_counts.get(
                    condition,
                    0
                )
                + 1
            )


        # ====================================================
        # Condition statistics
        # ====================================================

        condition_statistics = {}

        for condition, values in condition_prices.items():

            condition_statistics[
                condition
            ] = {

                "count": len(values),

                "medianPrice": round(
                    median_or_zero(values),
                    4
                ),

                "meanPrice": round(
                    mean_or_zero(values),
                    4
                ),

                "minPrice": round(
                    min(values),
                    4
                ),

                "maxPrice": round(
                    max(values),
                    4
                )
            }


        # ====================================================
        # Recent price statistics
        # ====================================================

        prices_7d = [
            listing["price"]
            for listing in listings_7d
        ]

        prices_30d = [
            listing["price"]
            for listing in listings_30d
        ]

        prices_90d = [
            listing["price"]
            for listing in listings_90d
        ]


        # ====================================================
        # Price distribution
        # ====================================================

        p10 = percentile(
            prices,
            10
        )

        p25 = percentile(
            prices,
            25
        )

        p50 = percentile(
            prices,
            50
        )

        p75 = percentile(
            prices,
            75
        )

        p90 = percentile(
            prices,
            90
        )


        # ====================================================
        # Listing age
        # ====================================================

        ages = [
            listing["ageDays"]
            for listing in listings
            if listing["ageDays"] is not None
        ]


        # ====================================================
        # Construct result
        # ====================================================

        results[set_name][
            card_number
        ] = {

            "cardName": card_name,

            "cardNumber": card_number,

            "setName": set_name,


            # ------------------------------------------------
            # Listing counts
            # ------------------------------------------------

            "listingCount": len(
                listings
            ),

            "listingCount7d": len(
                listings_7d
            ),

            "listingCount30d": len(
                listings_30d
            ),

            "listingCount90d": len(
                listings_90d
            ),


            # ------------------------------------------------
            # Price
            # ------------------------------------------------

            "medianPrice": round(
                median_or_zero(prices),
                4
            ),

            "meanPrice": round(
                mean_or_zero(prices),
                4
            ),

            "minPrice": round(
                min(prices)
                if prices
                else 0,
                4
            ),

            "maxPrice": round(
                max(prices)
                if prices
                else 0,
                4
            ),

            "priceStdDev": round(
                stdev_or_zero(prices),
                4
            ),


            # ------------------------------------------------
            # Price percentiles
            # ------------------------------------------------

            "priceP10": round(
                p10,
                4
            ),

            "priceP25": round(
                p25,
                4
            ),

            "priceP50": round(
                p50,
                4
            ),

            "priceP75": round(
                p75,
                4
            ),

            "priceP90": round(
                p90,
                4
            ),


            # ------------------------------------------------
            # Recent prices
            # ------------------------------------------------

            "medianPrice7d": round(
                median_or_zero(
                    prices_7d
                ),
                4
            ),

            "medianPrice30d": round(
                median_or_zero(
                    prices_30d
                ),
                4
            ),

            "medianPrice90d": round(
                median_or_zero(
                    prices_90d
                ),
                4
            ),


            # ------------------------------------------------
            # Listing velocity
            # ------------------------------------------------

            "listingVelocity7d": round(
                len(listings_7d) / 7,
                4
            ),

            "listingVelocity30d": round(
                len(listings_30d) / 30,
                4
            ),

            "listingVelocity90d": round(
                len(listings_90d) / 90,
                4
            ),


            # ------------------------------------------------
            # Recent listing ratios
            # ------------------------------------------------

            "recentListingRatio7d": round(
                len(listings_7d)
                /
                max(1, len(listings)),
                4
            ),

            "recentListingRatio30d": round(
                len(listings_30d)
                /
                max(1, len(listings)),
                4
            ),

            "recentListingRatio90d": round(
                len(listings_90d)
                /
                max(1, len(listings)),
                4
            ),


            # ------------------------------------------------
            # Condition
            # ------------------------------------------------

            "conditionCounts":
                condition_counts,

            "conditionStatistics":
                condition_statistics,


            # ------------------------------------------------
            # Listing age
            # ------------------------------------------------

            "medianListingAgeDays": round(
                median_or_zero(ages),
                4
            ),

            "meanListingAgeDays": round(
                mean_or_zero(ages),
                4
            )
        }


# ============================================================
# Compute market status index
# ============================================================
#
# Liquidity is relative, so it needs the full distribution of
# listing counts/velocities across every card before it can be
# scored. This has to run as a second pass, after every card in
# every set has been processed above.
# ============================================================

print("\nComputing market status index...")

all_listing_counts_90d = []
all_listing_velocities_30d = []

for cards in results.values():
    for card in cards.values():
        all_listing_counts_90d.append(
            card["listingCount90d"]
        )
        all_listing_velocities_30d.append(
            card["listingVelocity30d"]
        )

for set_name, cards in results.items():

    for card_number, card in cards.items():

        listing_count = card["listingCount"]

        if listing_count == 0:

            card["marketIndexComponents"] = {
                "liquidityScore": 0,
                "momentumScore": 50,
                "stabilityScore": 0,
                "freshnessScore": 0
            }

            card["marketIndex"] = 0
            card["marketStatus"] = market_status_label(
                0,
                listing_count
            )

            continue

        liquidity_count_score = rank_percentile(
            card["listingCount90d"],
            all_listing_counts_90d
        )

        liquidity_velocity_score = rank_percentile(
            card["listingVelocity30d"],
            all_listing_velocities_30d
        )

        liquidity = (
            liquidity_count_score
            + liquidity_velocity_score
        ) / 2

        recent_median = (
            card["medianPrice7d"]
            or card["medianPrice"]
        )

        baseline_median = (
            card["medianPrice90d"]
            or card["medianPrice"]
        )

        momentum = momentum_score(
            recent_median,
            baseline_median
        )

        stability = stability_score(
            card["meanPrice"],
            card["priceStdDev"]
        )

        freshness = freshness_score(
            card["recentListingRatio30d"]
        )

        market_index = round(
            0.30 * liquidity
            + 0.30 * momentum
            + 0.20 * stability
            + 0.20 * freshness,
            2
        )

        card["marketIndexComponents"] = {
            "liquidityScore": round(liquidity, 2),
            "momentumScore": round(momentum, 2),
            "stabilityScore": round(stability, 2),
            "freshnessScore": round(freshness, 2)
        }

        card["marketIndex"] = market_index

        card["marketStatus"] = market_status_label(
            market_index,
            listing_count
        )


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


print(
    f"\nWritten: {OUTPUT_PATH}"
)