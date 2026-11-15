import os
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_youtube_service():
    """Authenticates and returns the YouTube Data API service."""
    creds = Credentials.from_authorized_user_file('token.json')
    return build('youtube', 'v3', credentials=creds)

def upload_to_youtube(video_path, title, description, tags, thumbnail_path=None, publish_at=None):
    """Uploads video to YouTube, supports Scheduled Publishing, and attempts custom thumbnail."""
    youtube = get_youtube_service()
    is_short = "#shorts" in title.lower() or "shorts" in tags.lower()
    
    # If a publish time is provided, the API strictly requires the video to be uploaded as 'private'
    privacy = 'private' if publish_at else 'public'
    
    status_obj = {
        'privacyStatus': privacy,
        'selfDeclaredMadeForKids': False
    }
    
    if publish_at:
        status_obj['publishAt'] = publish_at
        print(f"⏰ Scheduling video to go public at: {publish_at} (UTC)")
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags.split(','),
            'categoryId': '22'  # People & Blogs
        },
        'status': status_obj
    }
    
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype='video/mp4')
    request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
    
    print(f"⏳ Uploading video: {title}")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"   Uploaded {int(status.progress() * 100)}%")
            
    video_id = response.get('id')
    print(f"✅ Upload Complete! Video ID: {video_id}")
    
    if thumbnail_path and os.path.exists(thumbnail_path):
        if is_short:
            print("⚠️ Skipping custom thumbnail upload for Shorts (Blocked by YouTube API).")
        else:
            print("🖼️ Attempting to set custom thumbnail via API...")
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_path))
                ).execute()
                print("✅ Custom thumbnail uploaded successfully!")
            except Exception as e:
                print(f"❌ Thumbnail upload failed (Often requires Phone Verification): {e}")

    return video_id
