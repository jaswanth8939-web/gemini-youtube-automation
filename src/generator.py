import os
import json
import time
import random
import requests
from io import BytesIO
from google import genai
from moviepy.editor import AudioFileClip, VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, vfx
from moviepy.config import change_settings
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

ASSETS_PATH = Path("assets")
FONT_FILE = ASSETS_PATH / "fonts/arial.ttf"
OUTPUT_DIR = Path("output")

# GitHub Actions compatibility for ImageMagick
if os.name == 'posix':
    change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})

def generate_curriculum(previous_titles=None):
    """Generates the entire course curriculum using Gemini."""
    print("🤖 No content plan found. Generating a new curriculum from scratch...")
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    history = ""
    if previous_titles:
        formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(previous_titles)])
        history = f"The following lessons have already been created:\n{formatted}\n\nPlease continue from where this series left off.\n"

    prompt = f"""
    You are an expert spiritual guide and viral YouTube strategist targeting a US/UK audience. 
    Generate a curriculum for a YouTube Shorts series focused on daily Christian prayers, spiritual warfare, Psalms, midnight blessings, and morning affirmations.
    {history}
    Use viral, urgent, and highly clickable titles similar to:
    - "Play This Psalm 91 Midnight Prayer"
    - "Listen Before 6AM For A Financial Miracle"
    - "Before Bed, Speak These 5 Words For An Overnight Miracle"
    - "The 3-Second Declaration That Strips Negativity From Your Home"

    Respond with ONLY a valid JSON object. The object must contain a key "lessons" which is a list of 20 lesson objects.
    Each lesson object must have these keys: "chapter", "part", "title", "status" (defaulted to "pending"), and "youtube_id" (defaulted to null).
    """
    
    for attempt in range(1, 6):
        try:
            response = client.models.generate_content(model='gemini-3.8-flash', contents=prompt)
            json_string = response.text.strip().replace("```json", "").replace("```", "")
            curriculum = json.loads(json_string)
            print("✅ New curriculum generated successfully!")
            return curriculum
        except Exception as e:
            print(f"⚠️ Curriculum Attempt {attempt}/5 failed: {e}")
            if attempt == 5:
                raise
            time.sleep(30)


# Prompt Gemini to exclusively ask for abstract/nature terms to avoid people
def generate_lesson_content(lesson_title):
    print(f"🤖 Generating content for lesson: '{lesson_title}'...")
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    
    prompt = f"""
    You are a viral YouTube scriptwriter in the Christian spirituality, midnight prayer, and daily blessings niche.
    Write a highly engaging script for the video titled: "{lesson_title}".
    
    CRITICAL INSTRUCTIONS:
    1. "long_form_slides": A list of exactly 25 to 30 slide objects. The "content" key for each slide must be a detailed paragraph of at least 70 to 100 words so the video length stretches to 10 minutes. 
    2. The "title" key for each slide MUST be a 1-2 word query for beautiful, abstract, or nature VIDEO backgrounds (e.g., 'nebula', 'ocean', 'forest', 'clouds', 'sunset', 'mountains'). ABSOLUTELY NO PEOPLE, FACES, CITIES, OR CHARACTERS to appeal to a broad US/UK audience.
    3. The final slide "content" MUST be exactly: "To unlock your personalized path, click the link in the comments for your Daily Prayer Guide."
    4. "short_form_highlight": A highly optimized YouTube Title (under 60 characters).
    5. "hashtags": A string of 5-7 relevant, space-separated viral hashtags (e.g. #Psalm91 #MidnightPrayer #Faith).

    Return only valid JSON.
    """
    for attempt in range(1, 6):
        try:
            response = client.models.generate_content(model='gemini-3.8-flash', contents=prompt)
            json_string = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(json_string)
        except Exception as e:
            print(f"⚠️ Attempt {attempt}/5 failed: {e}")
            if attempt == 5:
                raise
            time.sleep(30)


def get_pixabay_video(query):
    """Fetches a cinematic MP4 background video instead of a static image."""
    pixabay_api_key = os.getenv("PEXELS_API_KEY")
    if not pixabay_api_key: return None
    
    safe_query = requests.utils.quote(f"{query} nature background")
    try:
        url = f"https://pixabay.com/api/videos/?key={pixabay_api_key}&q={safe_query}&video_type=film"
        res = requests.get(url).json()
        if res.get('hits'):
            video_url = res['hits'][0]['videos']['medium']['url']
            vid_data = requests.get(video_url)
            path = OUTPUT_DIR / f"bg_{random.randint(10000,99999)}.mp4"
            with open(path, 'wb') as f:
                f.write(vid_data.content)
            return str(path)
    except Exception as e:
        print(f"❌ Failed to fetch video for {query}: {e}")
    return None


def generate_visuals(output_dir, video_type, slide_content=None, thumbnail_title=None, slide_number=0, total_slides=0):
    """Generates CapCut style text on a transparent PNG and fetches a background video."""
    output_dir.mkdir(exist_ok=True, parents=True)
    is_thumbnail = thumbnail_title is not None
    width, height = (1920, 1080) if video_type == 'long' else (1080, 1920)
    
    title = thumbnail_title if is_thumbnail else slide_content.get("title", "galaxy")
    
    # If it's a thumbnail, generate a static image. If it's a slide, just make a transparent text overlay.
    if is_thumbnail:
        bg_image = Image.new('RGBA', (width, height), color=(12, 17, 29))
        draw = ImageDraw.Draw(bg_image)
    else:
        bg_image = Image.new('RGBA', (width, height), (0, 0, 0, 0)) # Fully transparent
        draw = ImageDraw.Draw(bg_image)

    try:
        content_font = ImageFont.truetype(str(FONT_FILE), 55 if video_type == 'long' else 65)
    except IOError:
        content_font = ImageFont.load_default()

    content = slide_content.get("content", "") if not is_thumbnail else title
    words = content.split()
    lines, current_line = [], ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        if draw.textbbox((0, 0), test_line, font=content_font)[2] < width * 0.85:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)

    line_height = content_font.getbbox("A")[3] + 15
    y_text = (height - (len(lines) * line_height)) / 2

    # Draw CapCut style text: White fill with thick black stroke
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=content_font)
        x = (width - (bbox[2] - bbox[0])) / 2
        draw.text((x, y_text), line, font=content_font, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
        y_text += line_height

    text_overlay_path = output_dir / f"overlay_{slide_number}.png"
    bg_image.save(text_overlay_path)

    if is_thumbnail:
        return str(text_overlay_path)
    
    # Return both the text overlay AND the moving video background
    bg_video_path = get_pixabay_video(title)
    return {"text_image": str(text_overlay_path), "bg_video": bg_video_path}


def create_video(slide_data, audio_paths, output_path, video_type, thumbnail_path=None):
    """Composites the moving background video, the transparent CapCut text, and the Kokoro audio."""
    print(f"🎬 Assembling cinematic {video_type} video...")
    image_clips = []
    
    # HARDCODE THUMBNAIL HACK: Insert the static thumbnail as the first 1 second of the video
    if thumbnail_path and os.path.exists(thumbnail_path):
        print("🖼️ Injecting thumbnail as first video frame to bypass API limits...")
        thumb_clip = ImageClip(thumbnail_path).set_duration(1.0)
        image_clips.append(thumb_clip)

    for i, (visuals, audio_path) in enumerate(zip(slide_data, audio_paths)):
        audio_clip = AudioFileClip(str(audio_path))
        duration = audio_clip.duration + 0.5
        
        # Load moving background video
        if visuals['bg_video']:
            bg_clip = VideoFileClip(visuals['bg_video']).without_audio()
            if bg_clip.duration < duration:
                bg_clip = bg_clip.fx(vfx.loop, duration=duration)
            else:
                bg_clip = bg_clip.subclip(0, duration)
        else:
            from moviepy.editor import ColorClip
            bg_clip = ColorClip(size=(1920,1080) if video_type=='long' else (1080,1920), color=(12,17,29), duration=duration)

        # Layer the CapCut text on top
        txt_clip = ImageClip(visuals['text_image']).set_duration(duration)
        slide_clip = CompositeVideoClip([bg_clip, txt_clip]).set_audio(audio_clip).fadein(0.5).fadeout(0.5)
        image_clips.append(slide_clip)

    final_video = concatenate_videoclips(image_clips, method="compose")
    final_video.write_videofile(str(output_path), fps=24, codec="libx264", audio_codec="aac", preset="medium", threads=4)
