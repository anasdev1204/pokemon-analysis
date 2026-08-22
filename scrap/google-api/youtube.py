import os
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

CLIENT_CREDENTIALS = "client-secrets3.json"

SETS_PATH = "/Users/anas/Projects/pkmn-analysis/scrap/puppeteer/cache/sets.json"
OUTPUT_PATH = "/Users/anas/Projects/pkmn-analysis/data/youtube-set-videos.json"


def get_credentials():
    credentials = None

    if os.path.exists("token.json"):
        credentials = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_CREDENTIALS,
                SCOPES
            )
            credentials = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(credentials.to_json())

    return credentials


def search_videos(youtube, search_name):
    videos = []

    request = youtube.search().list(
        part="snippet",
        maxResults=50,
        q=f"{search_name} pokemon",
        type="video",
        videoDuration="long"
    )

    while request:
        response = request.execute()

        for video in response.get("items", []):
            videos.append({
                "id": video["id"]["videoId"],
                "title": video["snippet"]["title"],
                "publish_time": video["snippet"]["publishedAt"]
            })

        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            break

        request = youtube.search().list(
            part="snippet",
            maxResults=50,
            q=f"{search_name} pokemon",
            type="video",
            videoDuration="long",
            pageToken=next_page_token
        )

    return videos


def add_video_statistics(youtube, videos):
    if not videos:
        return videos

    # YouTube allows up to 50 IDs per videos.list request
    for i in range(0, len(videos), 50):
        batch = videos[i:i + 50]

        video_ids = [video["id"] for video in batch]

        request = youtube.videos().list(
            part="statistics",
            id=",".join(video_ids)
        )

        response = request.execute()

        stats_by_id = {
            video["id"]: video.get("statistics", {})
            for video in response.get("items", [])
        }

        for video in batch:
            stats = stats_by_id.get(video["id"], {})

            video["view_count"] = int(
                stats.get("viewCount", 0)
            )

            video["like_count"] = int(
                stats.get("likeCount", 0)
            )

            video["comment_count"] = int(
                stats.get("commentCount", 0)
            )

    return videos

def load_existing_results():
    with open(OUTPUT_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    credentials = get_credentials()

    youtube = build(
        "youtube",
        "v3",
        credentials=credentials
    )

    # Load sets
    with open(SETS_PATH, "r", encoding="utf-8") as file:
        sets = json.load(file)

    results = {}

    already_processed_sets = load_existing_results()

    for index, pkmn_set in enumerate(sets, start=1):
        set_name = pkmn_set["name"]

        if set_name in already_processed_sets:
            print(
                f"[{index}/{len(sets)}] "
                f"Skipping {set_name} (already processed)"
            )
            results[set_name] = already_processed_sets[set_name]
            continue

        release_date = pkmn_set["releaseDate"]

        search_name = set_name + " pokemon tcg"

        print(
            f"[{index}/{len(sets)}] "
            f"Searching YouTube for {search_name}..."
        )

        try:
            videos = search_videos(
                youtube,
                search_name
            )

            videos = add_video_statistics(
                youtube,
                videos
            )

            # Add set-specific information
            for video in videos:
                video["set_name"] = set_name
                video["set_search_name"] = search_name
                video["set_release_date"] = release_date

            results[set_name] = videos

            print(
                f"Found {len(videos)} videos for {set_name}"
            )

        except Exception as error:
            print(
                f"Failed to process {set_name}: {error}"
            )

            results[set_name] = []

    # Make sure data directory exists
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

    print(f"\nWritten: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()