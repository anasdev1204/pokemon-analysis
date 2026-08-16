import os
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]


def get_credentials():
    credentials = None

    # Reuse previously obtained credentials
    if os.path.exists("token.json"):
        credentials = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    if not credentials.valid:
        if credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "client-secrets.json",
                SCOPES
            )
            credentials = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(credentials.to_json())

    return credentials

def main():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    credentials = get_credentials()

    youtube = build(
        "youtube",
        "v3",
        credentials=credentials
    )

    request = youtube.search().list(
        part="snippet",
        maxResults=50,
        q="destined rivals pokemon",
        type="video",
        videoDuration="long"
    )
    response = request.execute()

    totalResults = response['pageInfo']['totalResults']
    print(f"Total results: {totalResults}")

    videos = []
    for video in response['items']:
        id = video['id']['videoId']
        info = video['snippet']
        title = info['title']
        publish_time = info['publishedAt']
        videos.append({
            "id": id,
            "title": title,
            "publish_time": publish_time
        })

    video_ids = [video['id'] for video in videos]
    stats_request = youtube.videos().list(
        part="statistics,snippet",
        id=",".join(video_ids)
    )
    stats_response = stats_request.execute()   

    for video in stats_response['items']:
        id = video['id']
        stats = video['statistics']
        for v in videos:
            if v['id'] == id:
                v['view_count'] = stats.get('viewCount', 0)
                v['like_count'] = stats.get('likeCount', 0)
                v['comment_count'] = stats.get('commentCount', 0) 

    print(json.dumps(videos, indent=4))


if __name__ == "__main__":
    main()
