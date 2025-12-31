import os
import re
import json
import whisper
import shutil
import base64
from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment
from fastapi import FastAPI, File, UploadFile

from scheduling import *
from model_ollama import LLM_Helper

# Init 
app = FastAPI()
assistant = LLM_Helper()
whisper_model = whisper.load_model("base")

UPLOAD_DIR = "recordings"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
MP3_PATH = os.path.join(UPLOAD_DIR, "talking.mp3") # This is the default path for saving user instruction

# Helper functions
def extract_json_or_text(input_string):
    json_match = re.search(r"(\{.*\})", input_string, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return input_string

    return input_string

def generate_audio_base64(text):
    tts = gTTS(text=text, lang="en", slow=False)
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    audio_base64 = base64.b64encode(mp3_fp.read()).decode("utf-8")

    return audio_base64

"""
    API starts here
"""

@app.get("/")
async def root():
    return {"message": "Hello World! Here is the API server for the AI voice assistant!"}

@app.get("/api/login")
def login():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            "session",  # Save cache
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.new_page()
        page.goto("https://calendar.google.com")
        try:
            page.wait_for_selector('[aria-label="Switch to Tasks"]', timeout=0)
            page.wait_for_load_state("networkidle")
        except Exception as _:
            assistant_response = "It seems like there are some issues when you are trying to sign in. Please refresh the webpage and try again."

            return {
                "reply": assistant_response,
                "audio": generate_audio_base64(assistant_response),
            }

        context.close()

    if check_if_google_calendar_login():
        assistant_response = (
            "You are all set! Start scheduling by clicking the Talk button!"
        )
    else:
        assistant_response = "It seems like there are some issues when you are trying to sign in. Please refresh the webpage and try again."

    return {
        "reply": assistant_response,
        "audio": generate_audio_base64(assistant_response),
    }

@app.post("/api/save-audio")
async def save_audio(audio: UploadFile = File(...)):

    temp_webm_path = os.path.join(UPLOAD_DIR, "temp_recording.webm")

    with open(temp_webm_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
        buffer.flush()

    try:
        audio_data = AudioSegment.from_file(temp_webm_path)
        audio_data.export(MP3_PATH, format="mp3")
        os.remove(temp_webm_path)

        print(f"Successfully converted to: {MP3_PATH}")
        return {"message": "Saved as MP3", "path": MP3_PATH}

    except Exception as e:
        print("bad", str(e))
        return {"message": "Conversion failed", "error": str(e)}

@app.post("/api/get-audio")
async def get_audio(text):
    audio_data = generate_audio_base64(text)
    return {"audio": audio_data}

@app.post("/api/reset")
async def reset():
    assistant.restart_chat_session()

@app.post("/api/process")
async def process(audio: UploadFile = File(...)):
    """ Processing the voice data given from the frontend
    
    """

    temp_webm_path = os.path.join(UPLOAD_DIR, "temp_recording.webm")

    with open(temp_webm_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
        buffer.flush()

    try:
        audio_data = AudioSegment.from_file(temp_webm_path)
        audio_data.export(MP3_PATH, format="mp3")
        os.remove(temp_webm_path)

        print(f"Successfully converted to: {MP3_PATH}")
    except Exception as e:
        print("bad", str(e))
        return {"message": "Conversion failed", "error": str(e)}

    result = whisper_model.transcribe(MP3_PATH)
    message = result["text"]
    raw_response = assistant.ask_a_question(message)
    response = extract_json_or_text(raw_response)

    assistant_response = ""

    if isinstance(response, dict):
        print(response)
        assistant_response = "Alright, let me schedule right now!"

        is_valid, validate_msg = validate_meeting_time(response)
        if is_valid:
            all_conflicted_events = {}
            if "bypass restriction" not in raw_response.lower():
                periods = split_time_period(response)

                for period in periods:
                    date, _ = period.split(",")
                    existing_events = await get_event_from_date(date)
                    preprocess_event = lambda e: (
                        parse_google_timestr_to_24h_range(e[0]),
                        e[1],
                    )
                    format_date = lambda d: datetime.strptime(d, "%d%m%Y").strftime(
                        "%B %d, %Y"
                    )

                    temp = find_conflicting_events(
                        period, [preprocess_event(i) for i in existing_events]
                    )
                    if len(temp) > 0:
                        all_conflicted_events[format_date(date)] = temp

            if all_conflicted_events:
                msg = generate_conflict_message(all_conflicted_events)
                print(all_conflicted_events)
                assistant_response = "It seems like there is a time conflict with the events shown here, Would you like to schedule for another time?"

                assistant.chat_history += [
                    {
                        "role": "system",
                        "content": assistant_response,
                    }
                ]
                audio_data = generate_audio_base64(assistant_response)

                return {
                    "message": message,
                    "reply": assistant_response + msg,
                    "audio": audio_data,
                }
            else:
                await add_calendar_event(response)
                assistant_response = (
                    "Alright, the schedule has been successfully added to the calendar!"
                )

                assistant.chat_history += [
                    {
                        "role": "system",
                        "content": assistant_response,
                    }
                ]
        else:
            assistant_response = "Please select another time. " + validate_msg

            assistant.chat_history += [
                {
                    "role": "system",
                    "content": assistant_response,
                }
            ]

    else:
        print(response)
        assistant_response = response
    audio_data = generate_audio_base64(assistant_response)

    return {"message": message, "reply": assistant_response, "audio": audio_data}
