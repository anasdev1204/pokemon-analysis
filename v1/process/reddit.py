import json
import math
import os
from datetime import datetime, timezone
from transformers import pipeline


INPUT_PATH = "/Users/anas/Projects/pkmn-analysis/data/reddit-set-posts.json"

OUTPUT_PATH = "/Users/anas/Projects/pkmn-analysis/data/processed/reddit-index.json"


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

# Recency half-life in days.
# A post loses half of its influence every 90 days.
HALF_LIFE_DAYS = 90

# Relative importance of comments compared with upvotes.
COMMENT_WEIGHT = 2.0

# Sentiment model.
#
# This is a general English sentiment model.
# You can later replace this with a Reddit-specific model.
SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def recency_weight(
    post_date: str,
    half_life_days: float = HALF_LIFE_DAYS
) -> float:

    if not post_date:
        return 0.0

    try:
        date = datetime.fromisoformat(
            post_date.replace("Z", "+00:00")
        )

        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        age_days = max(
            0,
            (now - date).total_seconds() / 86400
        )

        return 2 ** (
            -age_days / half_life_days
        )

    except Exception:
        return 0.0


def engagement_score(
    upvotes: int,
    comments: int
) -> float:

    return (
        math.log1p(max(0, upvotes))
        +
        COMMENT_WEIGHT *
        math.log1p(max(0, comments))
    )


def sentiment_value(
    label: str
) -> float:

    label = label.lower()

    if label == "positive":
        return 1.0

    if label == "negative":
        return -1.0

    return 0.0


# ---------------------------------------------------------
# Sentiment model
# ---------------------------------------------------------

print("Loading sentiment model...")

sentiment_model = pipeline(
    "sentiment-analysis",
    model=SENTIMENT_MODEL
)

print("Sentiment model loaded.")


# ---------------------------------------------------------
# Load Reddit data
# ---------------------------------------------------------

with open(
    INPUT_PATH,
    "r",
    encoding="utf-8"
) as file:
    reddit_data = json.load(file)


# ---------------------------------------------------------
# Process posts
# ---------------------------------------------------------

processed_sets = {}


for set_name, set_data in reddit_data.items():

    print(
        f"Processing {set_name}..."
    )

    posts = set_data.get(
        "posts",
        []
    )

    processed_posts = []

    weighted_engagement_total = 0.0
    weighted_sentiment_total = 0.0

    weighted_upvotes = 0.0
    weighted_comments = 0.0

    positive_posts = 0
    neutral_posts = 0
    negative_posts = 0

    for post in posts:

        title = post.get(
            "title",
            ""
        ).strip()

        if not title:
            continue

        upvotes = int(
            post.get(
                "upvotes",
                0
            ) or 0
        )

        comments = int(
            post.get(
                "comments",
                0
            ) or 0
        )

        post_date = post.get(
            "postDate"
        )

        # -------------------------------------------------
        # Engagement
        # -------------------------------------------------

        engagement = engagement_score(
            upvotes,
            comments
        )

        # -------------------------------------------------
        # Recency
        # -------------------------------------------------

        recency = recency_weight(
            post_date
        )

        # -------------------------------------------------
        # Sentiment
        # -------------------------------------------------

        sentiment_result = sentiment_model(
            title
        )[0]

        sentiment_label = (
            sentiment_result["label"]
            .lower()
        )

        confidence = float(
            sentiment_result["score"]
        )

        sentiment = sentiment_value(
            sentiment_label
        )

        # -------------------------------------------------
        # Weighted values
        # -------------------------------------------------

        weighted_engagement = (
            engagement *
            recency
        )

        weighted_sentiment = (
            sentiment *
            confidence *
            weighted_engagement
        )

        weighted_engagement_total += (
            weighted_engagement
        )

        weighted_sentiment_total += (
            weighted_sentiment
        )

        weighted_upvotes += (
            upvotes *
            recency
        )

        weighted_comments += (
            comments *
            recency
        )

        # -------------------------------------------------
        # Sentiment counts
        # -------------------------------------------------

        if sentiment_label == "positive":
            positive_posts += 1

        elif sentiment_label == "negative":
            negative_posts += 1

        else:
            neutral_posts += 1

        # -------------------------------------------------
        # Store processed post
        # -------------------------------------------------

        processed_posts.append({
            "id": post.get("id"),

            "title": title,

            "postDate": post_date,

            "upvotes": upvotes,

            "comments": comments,

            "engagementScore": round(
                engagement,
                4
            ),

            "recencyWeight": round(
                recency,
                6
            ),

            "weightedEngagement": round(
                weighted_engagement,
                4
            ),

            "sentiment": sentiment_label,

            "sentimentConfidence": round(
                confidence,
                4
            ),

            "sentimentValue": sentiment,

            "weightedSentiment": round(
                weighted_sentiment,
                4
            )
        })

    # -----------------------------------------------------
    # Aggregate sentiment
    # -----------------------------------------------------

    if weighted_engagement_total > 0:

        reddit_sentiment = (
            weighted_sentiment_total /
            weighted_engagement_total
        )

    else:

        reddit_sentiment = 0.0

    # -----------------------------------------------------
    # Store
    # -----------------------------------------------------

    processed_sets[set_name] = {

        "postCount": len(posts),

        "processedPostCount": len(
            processed_posts
        ),

        "weightedPostCount": round(
            sum(
                p["recencyWeight"]
                for p in processed_posts
            ),
            4
        ),

        "weightedUpvotes": round(
            weighted_upvotes,
            4
        ),

        "weightedComments": round(
            weighted_comments,
            4
        ),

        "weightedEngagement": round(
            weighted_engagement_total,
            4
        ),

        "redditSentiment": round(
            reddit_sentiment,
            6
        ),

        "positivePostCount": positive_posts,

        "neutralPostCount": neutral_posts,

        "negativePostCount": negative_posts,

        "positivePostRatio": round(
            positive_posts /
            max(1, len(processed_posts)),
            4
        ),

        "neutralPostRatio": round(
            neutral_posts /
            max(1, len(processed_posts)),
            4
        ),

        "negativePostRatio": round(
            negative_posts /
            max(1, len(processed_posts)),
            4
        ),

        "posts": processed_posts
    }


# ---------------------------------------------------------
# Reddit activity index
# ---------------------------------------------------------

print("Calculating Reddit index...")


raw_indices = {}


for set_name, data in processed_sets.items():

    weighted_posts = data[
        "weightedPostCount"
    ]

    weighted_upvotes = data[
        "weightedUpvotes"
    ]

    weighted_comments = data[
        "weightedComments"
    ]

    # Log prevents very large sets from dominating.
    index = (
        math.log1p(weighted_posts)
        +
        math.log1p(weighted_upvotes)
        +
        math.log1p(weighted_comments)
    )

    raw_indices[set_name] = index


# ---------------------------------------------------------
# Normalize 0-100
# ---------------------------------------------------------

if raw_indices:

    min_index = min(
        raw_indices.values()
    )

    max_index = max(
        raw_indices.values()
    )

else:

    min_index = 0
    max_index = 0


for set_name, data in processed_sets.items():

    raw_index = raw_indices[
        set_name
    ]

    if max_index == min_index:

        reddit_index = 50.0

    else:

        reddit_index = (
            (raw_index - min_index)
            /
            (max_index - min_index)
            *
            100
        )

    data["redditIndex"] = round(
        reddit_index,
        4
    )


# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

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
        processed_sets,
        file,
        indent=2,
        ensure_ascii=False
    )


print(
    f"Written: {OUTPUT_PATH}"
)