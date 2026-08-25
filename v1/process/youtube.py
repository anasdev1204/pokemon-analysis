import json
import math
import os
from datetime import datetime, timezone

from transformers import pipeline


INPUT_PATH = (
    "/Users/anas/Projects/pkmn-analysis/data/youtube-set-videos.json"
)

OUTPUT_PATH = (
    "/Users/anas/Projects/pkmn-analysis/data/processed/youtube-index.json"
)


# =========================================================
# Configuration
# =========================================================

# Recency half-lives
HALF_LIFE_30 = 30
HALF_LIFE_90 = 90
HALF_LIFE_180 = 180

# Sentiment model
SENTIMENT_MODEL = (
    "cardiffnlp/twitter-roberta-base-sentiment-latest"
)

# =========================================================
# Helpers
# =========================================================

def parse_date(date_string):
    if not date_string:
        return None

    try:
        return datetime.fromisoformat(
            date_string.replace("Z", "+00:00")
        )
    except Exception:
        return None


def age_days(date_string):
    date = parse_date(date_string)

    if date is None:
        return None

    now = datetime.now(timezone.utc)

    return max(
        0,
        (now - date).total_seconds() / 86400
    )


def recency_weight(
    date_string,
    half_life
):
    age = age_days(date_string)

    if age is None:
        return 0.0

    return 2 ** (
        -age / half_life
    )


def safe_int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def sentiment_value(label):
    label = label.lower()

    if label == "positive":
        return 1.0

    if label == "negative":
        return -1.0

    return 0.0


# =========================================================
# Load sentiment model
# =========================================================

print("Loading sentiment model...")

sentiment_model = pipeline(
    "sentiment-analysis",
    model=SENTIMENT_MODEL
)

print("Sentiment model loaded.")


# =========================================================
# Load YouTube data
# =========================================================

with open(
    INPUT_PATH,
    "r",
    encoding="utf-8"
) as file:

    youtube_data = json.load(file)


processed_sets = {}


# =========================================================
# Process every set
# =========================================================

for set_name, videos in youtube_data.items():

    print(
        f"Processing {set_name}: "
        f"{len(videos)} videos"
    )

    processed_videos = []

    total_views = 0
    total_likes = 0
    total_comments = 0

    weighted_views_30 = 0
    weighted_views_90 = 0
    weighted_views_180 = 0

    weighted_engagement_30 = 0
    weighted_engagement_90 = 0
    weighted_engagement_180 = 0

    sentiment_weighted_total = 0
    sentiment_weight_total = 0

    positive_count = 0
    neutral_count = 0
    negative_count = 0

    # -----------------------------------------------------
    # Process videos
    # -----------------------------------------------------

    for video in videos:

        title = video.get(
            "title",
            ""
        ).strip()

        if not title:
            continue

        views = safe_int(
            video.get("view_count")
        )

        likes = safe_int(
            video.get("like_count")
        )

        comments = safe_int(
            video.get("comment_count")
        )

        publish_time = video.get(
            "publish_time"
        )

        # -------------------------------------------------
        # Engagement
        # -------------------------------------------------

        # Logarithmic engagement prevents viral videos
        # from completely dominating the index.

        engagement = (
            math.log1p(views)
            +
            math.log1p(likes)
            +
            math.log1p(comments)
        )

        # Engagement rate relative to views
        if views > 0:

            engagement_rate = (
                likes + comments
            ) / views

        else:

            engagement_rate = 0.0

        # -------------------------------------------------
        # Recency
        # -------------------------------------------------

        weight_30 = recency_weight(
            publish_time,
            HALF_LIFE_30
        )

        weight_90 = recency_weight(
            publish_time,
            HALF_LIFE_90
        )

        weight_180 = recency_weight(
            publish_time,
            HALF_LIFE_180
        )

        # -------------------------------------------------
        # Weighted views
        # -------------------------------------------------

        weighted_views_30 += (
            views * weight_30
        )

        weighted_views_90 += (
            views * weight_90
        )

        weighted_views_180 += (
            views * weight_180
        )

        # -------------------------------------------------
        # Weighted engagement
        # -------------------------------------------------

        weighted_engagement_30 += (
            engagement * weight_30
        )

        weighted_engagement_90 += (
            engagement * weight_90
        )

        weighted_engagement_180 += (
            engagement * weight_180
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

        # Weight sentiment by views and recency.
        #
        # A video with 500k views matters more than
        # a video with 20 views.

        sentiment_weight = (
            math.log1p(views)
            *
            weight_90
        )

        sentiment_weighted_total += (
            sentiment
            *
            confidence
            *
            sentiment_weight
        )

        sentiment_weight_total += (
            sentiment_weight
        )

        # -------------------------------------------------
        # Sentiment counts
        # -------------------------------------------------

        if sentiment_label == "positive":

            positive_count += 1

        elif sentiment_label == "negative":

            negative_count += 1

        else:

            neutral_count += 1

        # -------------------------------------------------
        # Totals
        # -------------------------------------------------

        total_views += views
        total_likes += likes
        total_comments += comments

        # -------------------------------------------------
        # Store processed video
        # -------------------------------------------------

        processed_videos.append({

            "id": video.get("id"),

            "title": title,

            "publish_time": publish_time,

            "views": views,

            "likes": likes,

            "comments": comments,

            "engagementRate": round(
                engagement_rate,
                8
            ),

            "engagementScore": round(
                engagement,
                6
            ),

            "recencyWeight30": round(
                weight_30,
                6
            ),

            "recencyWeight90": round(
                weight_90,
                6
            ),

            "recencyWeight180": round(
                weight_180,
                6
            ),

            "sentiment": sentiment_label,

            "sentimentConfidence": round(
                confidence,
                6
            ),

            "sentimentValue": sentiment
        })

    # =====================================================
    # Aggregate sentiment
    # =====================================================

    if sentiment_weight_total > 0:

        youtube_sentiment = (
            sentiment_weighted_total
            /
            sentiment_weight_total
        )

    else:

        youtube_sentiment = 0.0

    video_count = len(
        processed_videos
    )

    # =====================================================
    # Store set
    # =====================================================

    processed_sets[set_name] = {

        "videoCount": video_count,

        "totalViews": total_views,

        "totalLikes": total_likes,

        "totalComments": total_comments,

        "averageViews": (
            total_views / video_count
            if video_count > 0
            else 0
        ),

        "averageLikes": (
            total_likes / video_count
            if video_count > 0
            else 0
        ),

        "averageComments": (
            total_comments / video_count
            if video_count > 0
            else 0
        ),

        "weightedViews30": round(
            weighted_views_30,
            4
        ),

        "weightedViews90": round(
            weighted_views_90,
            4
        ),

        "weightedViews180": round(
            weighted_views_180,
            4
        ),

        "weightedEngagement30": round(
            weighted_engagement_30,
            4
        ),

        "weightedEngagement90": round(
            weighted_engagement_90,
            4
        ),

        "weightedEngagement180": round(
            weighted_engagement_180,
            4
        ),

        "youtubeSentiment": round(
            youtube_sentiment,
            6
        ),

        "positiveVideoCount": positive_count,

        "neutralVideoCount": neutral_count,

        "negativeVideoCount": negative_count,

        "positiveVideoRatio": round(
            positive_count /
            max(1, video_count),
            4
        ),

        "neutralVideoRatio": round(
            neutral_count /
            max(1, video_count),
            4
        ),

        "negativeVideoRatio": round(
            negative_count /
            max(1, video_count),
            4
        ),

        "videos": processed_videos
    }


# =========================================================
# Create YouTube popularity index
# =========================================================

print(
    "\nCalculating YouTube popularity index..."
)


raw_indices = {}


for set_name, data in processed_sets.items():

    # Use logarithms so a set with 10 million views
    # doesn't completely dominate a set with 1 million.

    raw_index = (

        math.log1p(
            data["videoCount"]
        )

        +

        math.log1p(
            data["weightedViews90"]
        )

        +

        math.log1p(
            data["weightedEngagement90"]
        )
    )

    raw_indices[set_name] = raw_index


# =========================================================
# Normalize to 0-100
# =========================================================

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

        youtube_index = 50.0

    else:

        youtube_index = (
            (
                raw_index - min_index
            )
            /
            (
                max_index - min_index
            )
            *
            100
        )

    data["youtubeIndex"] = round(
        youtube_index,
        4
    )


# =========================================================
# Save
# =========================================================

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
    f"\nWritten: {OUTPUT_PATH}"
)