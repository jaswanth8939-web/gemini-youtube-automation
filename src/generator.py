import os
import json
import random
import urllib.parse
import requests
from pathlib import Path
from google import genai
from google.genai import types
from pydantic import BaseModel
from gtts import gTTS

# ==========================================
# CONFIGURATION & API SETUP
# ==========================================
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY") # Used for Pixabay API

if not GOOGLE_API_KEY:
    raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable is not set.")

client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL_ID = 'gemini-2.5-flash'

PLAN_FILE = Path('content_plan.json')
OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(exist_ok=True)

# ==========================================
# DATA MODELS (JSON SCHEMAS)
# ==========================================
class Lesson(BaseModel):
    chapter: int
    part: int
    title: str
    status: str = "pending"
    youtube_id: str | None = None

class Curriculum(BaseModel):
    lessons: list[Lesson]

class Slide(BaseModel):
    image_search_query: str
    narration_text: str

class VideoScript(BaseModel):
    youtube_title: str
    youtube_description: str
    youtube_tags: str
    slides: list[Slide]

# ==========================================
# CORE FUNCTIONS
# ==========================================
def fetch_pixabay_image(query: str, save_path: str):
    """Fetches an image from Pixabay using the mapped PEXELS_API_KEY."""
    safe_query = urllib.parse.quote(query)
    url = f"https://pixabay.com/api/?key={PEXELS_API_KEY}&q={safe_query}&image_type=photo&orientation=vertical&per_page=3"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get('hits'):
            image_url = random.choice(data['hits'])['largeImageURL']
            img_data = requests.get(image_url).content
            with open(save_path, 'wb') as handler:
                handler.write(img_data)
            print(f"  ✓ Downloaded image for query: '{query}'")
        else:
            print(f"  ⚠ No image found for '{query}', falling back to default.")
            fallback_url = f"https://pixabay.com/api/?key={PEXELS_API_KEY}&q=nature+clouds&image_type=photo&orientation=vertical&per_page=3"
            fallback_data = requests.get(fallback_url).json()
            if fallback_data.get('hits'):
                img_data = requests.get(fallback_data['hits'][0]['largeImageURL']).content
                with open(save_path, 'wb') as handler:
                    handler.write(img_data)
                    
    except Exception as e:
        print(f"  ❌ Failed to fetch image for '{query}': {e}")

def generate_curriculum() -> Curriculum:
    """Generates a 20-lesson spiritual & numerology content plan."""
    print("Generating new spiritual curriculum via Gemini...")
    prompt = """
    You are an expert spiritual guide and viral YouTube strategist. 
    Generate a 20-video curriculum for a YouTube Shorts channel focused on daily prayers, 
    spiritual warfare, Psalms, morning affirmations, and numerology life hacks. 
    
    Use viral, urgent, and highly clickable titles similar to:
    - "Play This Psalm 91 Midnight Prayer"
    - "Listen Before 6AM For A Financial Miracle"
    - "Before Bed, Speak These 5 Words For An Overnight Miracle"
    - "The 3-Second Declaration That Strips Negativity From Your Home"
    
    Structure it logically into chapters and parts.
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Curriculum,
            temperature=0.7,
        ),
    )
    return Curriculum.model_validate_json(response.text)

def generate_lesson_script(lesson_title: str) -> VideoScript:
    """Generates the slides and narration for a specific spiritual lesson."""
    print(f"Generating script for: '{lesson_title}'...")
    prompt = f"""
    You are a viral YouTube Shorts scriptwriter in the spiritual and numerology niche.
    Write a highly engaging, fast-paced script for the video titled: "{lesson_title}".
    
    Requirements:
    1. Create exactly 7 slides.
    2. The narration should be urgent, comforting, and deeply spiritual. 
    3. CRITICAL: The narration text for the final slide MUST be exactly this: "To unlock your personalized path, click the link in the comments for your Daily Prayer and Numerology Guide."
    4. The image_search_query must be simple, 1-2 word keywords suitable for free stock footage APIs (e.g., "galaxy", "nature", "clouds", "sunset", "waterfall").
    5. Provide a highly optimized YouTube Title (under 60 characters).
    6. Provide a YouTube Description.
    7. Provide a comma-separated list of viral tags.
    """
    
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VideoScript,
            temperature=0.7,
        ),
    )
    
    return VideoScript.model_validate_json(response.text)

def generate_lesson_content(*args, **kwargs):
    """Main workflow manager."""
    if PLAN_FILE.exists():
        with open(PLAN_FILE, 'r') as f:
            plan = Curriculum.model_validate_json(f.read())
    else:
        plan = generate_curriculum()
        with open(PLAN_FILE, 'w') as f:
            f.
