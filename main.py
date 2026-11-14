import os
import re
import sys
import json
import datetime
import time
import traceback
from pathlib import Path
from src.generator import (
    generate_curriculum,
    generate_lesson_content,
    generate_visuals,
    create_video
)
from src.uploader import upload_to_youtube

CONTENT_PLAN_FILE = Path("content_plan.json")
OUTPUT_DIR = Path("output")
LESSONS_PER_RUN = 1

def get_content_plan():
    if not CONTENT_PLAN_FILE.exists():
        print("📄 content_plan.json not found. Generating new plan...")
        new_plan = generate_curriculum()
        with open(CONTENT_PLAN_FILE, 'w') as f:
            json.dump(new_plan, f, indent=2)
        print(f"✅ New curriculum saved to {CONTENT_PLAN_FILE}")
        return new_plan
    else:
        try:
            with open(CONTENT_PLAN_FILE, 'r') as f:
                plan = json.load(f)
            if not plan.get("lessons") or not isinstance(plan["lessons"], list):
                raise ValueError("⚠️ Invalid or empty lesson plan detected.")
            return plan
        except Exception as e:
            print(f"❌ ERROR loading existing plan: {e}. Regenerating...")
            new_plan = generate_curriculum()
            with open(CONTENT_PLAN_FILE, 'w') as f:
                json.dump(new_plan, f, indent=2)
            return new_plan


def update_content_plan(plan):
    with open(CONTENT_PLAN_FILE, 'w') as f:
        json.dump(plan, f, indent=2)


def text_to_speech_kokoro(text, output_path):
    """Uses Kokoro ONNX for ultra-realistic Michael voice."""
    print("🎤 Converting script to Kokoro Michael voice...")
    from kokoro_onnx import Kokoro
    import soundfile as sf
    
    # Load the model downloaded by the GitHub Action
    kokoro = Kokoro("kokoro-v0_19.onnx", "voices.json")
    wav_path = str(output_path.with_suffix('.wav'))
    
    try:
        # am_michael is the highly realistic American male voice
        samples, sample_rate = kokoro.create(text, voice="am_michael", speed=1.0, lang="en-us")
        sf.write(wav_path, samples, sample_rate)
        
        print("✅ Speech generated successfully!")
        return Path(wav_path)
    except Exception as e:
        print(f"❌ Failed to generate Kokoro TTS: {e}")
        raise


def produce_lesson_videos(lesson):
    print(f"\n▶️ Starting production for Lesson: '{lesson['title']}'")
    chapter_safe = re.sub(r'[^\w]', '_', str(lesson['chapter'])).strip('_')
    part_safe = re.sub(r'[^\w]', '_', str(lesson['part'])).strip('_')
    unique_id = f"{datetime.datetime.now().strftime('%Y%m%d')}_{chapter_safe}_{part_safe}"

    lesson_content = generate_lesson_content(lesson['title'])

    print("\n--- Producing Long-Form Video ---")

    intro_slide = {"title": lesson['title'], "content": "Welcome to your daily spiritual guidance."}
    outro_slide = {"title": "Amen.", "content": "Click the link in the comments for your Daily Prayer Guide.\n#Spirituality #DailyPrayer"}
    all_slides = [intro_slide] + lesson_content['long_form_slides'] + [outro_slide]

    slide_scripts = [
        f"Welcome. Today’s spiritual message is titled: {lesson['title']}.",
        *[s['content'] for s in lesson_content['long_form_slides']],
        "Thank you for joining us in prayer today. To unlock your personalized path, click the link in the comments for your daily prayer guide. May you be blessed."
    ]

    slide_audio_paths = []
    for i, script in enumerate(slide_scripts):
        audio_path = OUTPUT_DIR / f"audio_slide_{i+1}_{unique_id}.wav"
        wav_path = text_to_speech_kokoro(script, audio_path)
        slide_audio_paths.append(wav_path)
    print(f"🎧 Total slide audios: {len(slide_audio_paths)}")

    slide_dir = OUTPUT_DIR / f"slides_long_{unique_id}"
    slide_paths = []
    for i, slide in enumerate(all_slides):
        path = generate_visuals(
            output_dir=slide_dir,
            video_type='long',
            slide_content=slide,
            slide_number=i + 1,
            total_slides=len(all_slides)
        )
        slide_paths.append(path)

    long_video_path = OUTPUT_DIR / f"long_video_{unique_id}.mp4"
    print(f"🎥 Creating long-form video at: {long_video_path}")
    create_video(slide_paths, slide_audio_paths, long_video_path, 'long')

    long_thumb_path = generate_visuals(
        output_dir=OUTPUT_DIR,
        video_type='long',
        thumbnail_title=lesson['title']
    )

    print("\n--- Producing Short Video ---")
    short_script = (f"{lesson_content['short_form_highlight']}\n\n"
    f"Link to the full prayer is in the description below.")
    short_audio_wav_path = OUTPUT_DIR / f"short_audio_{unique_id}.wav"
    short_audio_path = text_to_speech_kokoro(short_script, short_audio_wav_path)

    short_slide_dir = OUTPUT_DIR / f"slides_short_{unique_id}"
    short_slide_content = {
        "title": "Daily Prayer",
        "content": f"{lesson_content['short_form_highlight']}\n\n#DailyPrayer #Faith"
    }
    short_slide_path = generate_visuals(
        output_dir=short_slide_dir,
        video_type='short',
        slide_content=short_slide_content,
        slide_number=1,
        total_slides=1
    )

    short_video_path = OUTPUT_DIR / f"short_video_{unique_id}.mp4"
    print(f"🎥 Creating short video at: {short_video_path}")
    create_video([short_slide_path], [short_audio_path], short_video_path, 'short')

    short_thumb_path = generate_visuals(
        output_dir=OUTPUT_DIR,
        video_type='short',
        thumbnail_title=f"Quick Prayer: {lesson['title']}"
    )

    print("\n📤 Uploading to YouTube...")
    hashtags = lesson_content.get("hashtags", "#Prayer #Spirituality #Faith #Psalm91")
    long_desc = f"Today's Message: {lesson['title']}\n\n{hashtags}\n\nMay this prayer bring peace and protection into your life."
    long_tags = "Prayer, Spirituality, Psalm 91, Midnight Prayer, Faith, Blessing, Christian, " + lesson['title'].replace(" ", ", ")

    long_video_id = upload_to_youtube(
        long_video_path,
        lesson['title'],
        long_desc,
        long_tags,
        long_thumb_path
    )

    if long_video_id:
        print("⏳ Waiting 30 seconds before uploading the short...")
        time.sleep(30)
        highlight = (lesson_content.get('short_form_highlight') or '').strip()
        if not highlight:
            highlight = f"Daily Prayer: {lesson['title']}"
        short_title = f"{highlight[:90].rstrip()} #Shorts"
        short_desc = (f"{lesson_content['short_form_highlight']}\n\n"
                      f"Watch the full prayer here: https://www.youtube.com/watch?v={long_video_id}\n\n"
                      f"{hashtags}")
        upload_to_youtube(
            short_video_path,
            short_title.strip(),
            short_desc,
            "Prayer,Shorts,Spirituality,Faith",
            short_thumb_path
        )
        return long_video_id
    return None


def main():
    print("🚀 Starting Autonomous Channel Generator")
    print(f"📁 Current working dir: {os.getcwd()}")
    print(f"📁 OUTPUT_DIR: {OUTPUT_DIR.resolve()}")

    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        print(f"📁 Created output folder: {OUTPUT_DIR.exists()}")
        plan = get_content_plan()
        pending = [(i, lesson) for i, lesson in enumerate(plan['lessons']) if lesson['status'] == 'pending']

        if not pending:
            print("🎉 All lessons produced! Generating new content plan to restart from scratch...")

            previous_titles = [lesson['title'] for lesson in plan['lessons']]
            new_plan = generate_curriculum(previous_titles=previous_titles)
            update_content_plan(new_plan)
            plan = new_plan
            pending = [(i, lesson) for i, lesson in enumerate(new_plan['lessons']) if lesson['status'] == 'pending']
            if not pending:
                print("⚠️ Curriculum generated but no valid lessons found.")
                return

        failed_lessons = []
        for lesson_index, lesson in pending[:LESSONS_PER_RUN]:
            try:
                video_id = produce_lesson_videos(lesson)
                if video_id:
                    for original_lesson in plan['lessons']:
                        if original_lesson['title'].strip().lower() == lesson['title'].strip().lower():
                            original_lesson['status'] = 'complete'
                            original_lesson['youtube_id'] = video_id
                            print(f"✅ Completed lesson: {lesson['title']}")
                            break
                    else:
                        print(f"⚠️ Could not find lesson in plan to mark as complete: {lesson['title']}")
                else:
                    print(f"❌ Upload failed (no video ID returned): {lesson['title']}")
                    failed_lessons.append(lesson['title'])
            except Exception as e:
                print(f"❌ Failed producing lesson: {lesson['title']}")
                traceback.print_exc()
                failed_lessons.append(lesson['title'])
            finally:
                update_content_plan(plan)
                print("📦 Content plan saved.")

        if failed_lessons:
            print(f"\n❌ PIPELINE FAILED — {len(failed_lessons)} lesson(s) did not complete:")
            for title in failed_lessons:
                print(f"   - {title}")
                sys.exit(1)

    except Exception as e:
        print("❌ Critical error in main()")
        traceback.print_exc()
        sys.exit(1)

    try:
        for file in OUTPUT_DIR.glob("*.wav"):
            file.unlink()
            print(f"🧹 Deleted: {file}")
    except Exception as e:
        print(f"⚠️ Could not clean up .wav files: {e}")

if __name__ == "__main__":
    main()
