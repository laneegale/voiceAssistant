
import os
import shutil
from fastapi import FastAPI, File, UploadFile
from pydub import AudioSegment
import base64
from io import BytesIO
from gtts import gTTS

from scheduling import *

from model import LLM_Helper
from google import genai
import json
import re
import whisper
whisper_model = whisper.load_model("base")

app = FastAPI()
# assistant = Gemini()
assistant = LLM_Helper()

UPLOAD_DIR = "recordings"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
mp3_path = os.path.join(UPLOAD_DIR, "talking.mp3")

def extract_json_or_text(input_string):
    json_match = re.search(r'(\{.*\})', input_string, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return input_string
            
    return input_string

def generate_audio_base64(text):
    tts = gTTS(text=text, lang='en', slow=False)
    mp3_fp = BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    audio_base64 = base64.b64encode(mp3_fp.read()).decode('utf-8')
    
    return audio_base64

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/api/save-audio")
async def save_audio(audio: UploadFile = File(...)):

    temp_webm_path = os.path.join(UPLOAD_DIR, "temp_recording.webm")

    with open(temp_webm_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
        buffer.flush()

    try:
        audio_data = AudioSegment.from_file(temp_webm_path)
        audio_data.export(mp3_path, format="mp3")
        os.remove(temp_webm_path)
        
        print(f"Successfully converted to: {mp3_path}")
        return {"message": "Saved as MP3", "path": mp3_path}
        
    except Exception as e:
        print("bad", str(e))
        return {"message": "Conversion failed", "error": str(e)}

@app.post("/api/process")
async def process(audio: UploadFile = File(...)):

    temp_webm_path = os.path.join(UPLOAD_DIR, "temp_recording.webm")

    with open(temp_webm_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
        buffer.flush()

    try:
        audio_data = AudioSegment.from_file(temp_webm_path)
        audio_data.export(mp3_path, format="mp3")
        os.remove(temp_webm_path)
        
        print(f"Successfully converted to: {mp3_path}")        
    except Exception as e:
        print("bad", str(e))
        return {"message": "Conversion failed", "error": str(e)}

    result = whisper_model.transcribe(mp3_path)
    message = result["text"]
    response = assistant.ask_a_question(message)
    response = extract_json_or_text(response)

    assistant_response = ""

    if isinstance(response, dict):
        print(response)
        assistant_response = "Alright, let me schedule right now!"

        time_conflict = False
        is_valid, validate_msg = validate_meeting_time(response)
        if is_valid:

            periods = split_time_period(response)
            # print(periods)
            all_conflicted_events = {}

            c = 0
            for period in periods:
                date, time = period.split(',')
                existing_events = get_event_from_date(date)
                # existing_events = all_events[c]
                # print(existing_events)
                # all_conflicted_events[date] = find_conflicting_events(period, existing_events)
                preprocess_event = lambda e: (parse_google_timestr_to_24h_range(e[0]), e[1])
                format_date = lambda d: datetime.strptime(d, "%d%m%Y").strftime("%B %d, %Y")

                all_conflicted_events[format_date(date)] = find_conflicting_events(period, [preprocess_event(i) for i in existing_events])
                c += 1

            if all_conflicted_events: 
                # time_conflict = True
                msg = generate_conflict_message(all_conflicted_events)
                assistant_response = "It seems like there is a time conflict with the events shown here, please select another time."
                audio_data = generate_audio_base64(assistant_response)
                return {"message": message, "reply": assistant_response + msg, "audio": audio_data}
            else:
                assistant_response = "Good time"
                # do the scheduling here
                # to - do
        else:
            # time_conflict = True
            assistant_response = "Please select another time. " + validate_msg

    else:
        print(response)
        assistant_response = response
    audio_data = generate_audio_base64(assistant_response)

    return {"message": message, "reply": assistant_response, "audio": audio_data}

@app.post("/api/get-audio")
async def get_audio(text):
    audio_data = generate_audio_base64(text)
    return {"audio": audio_data}


@app.post("/api/reset")
async def reset():
    assistant.restart_chat_session()
