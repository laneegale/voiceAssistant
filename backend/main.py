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
MP3_PATH = os.path.join(
    UPLOAD_DIR, "talking.mp3"
)  # This is the default path for saving user instruction


# Helper functions
def extract_json_or_text(input_string: str) -> str:
    """Extract the json contained in input_string. If there is no json in the string, return input_string unmodified.

    Args:
        input_string: some string
        e.g. 'bypass restriction {"key1": "v1", "key2": "v2}'

    Returns:
        Either the json inside the string, or return the unmodified input string
        e.g. '{"key1": "v1", "key2": "v2}'

    """
    json_match = re.search(r"(\{.*\})", input_string, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return input_string

    return input_string


def generate_audio_base64(text: str) -> str:
    """Converts text to speech and encodes the resulting audio as a base64 string. This is useful for sending audio data directly to a frontend.

    Args:
        text: The string content to be converted into speech.

    Returns:
        A base64-encoded UTF-8 string representing the MP3 audio data.

    """
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
    """Hello World"""

    return {
        "message": "Hello World! Here is the API server for the AI voice assistant!"
    }


@app.post("/api/reset")
async def reset():
    assistant.restart_chat_session()


@app.post("/api/get-audio")
async def get_audio(text):
    audio_data = generate_audio_base64(text)
    return {"audio": audio_data}


@app.get("/api/login")
def login() -> dict[str, str]:
    """
        Initializes a persistent browser session for Google Calendar authentication.

        This endpoint uses Playwright to launch a Chromium instance. If the user is 
        not logged in, it allows for manual interaction. If a session already 
        exists, it verifies the 'Switch to Tasks' element to confirm access.

        Returns:
            dict: A JSON response containing:
                - reply (str): Status message for the user.
                - audio (str): Base64 encoded voice response of the status.
        
        Note:
            Uses a persistent context stored in the 'session' directory to maintain 
            login cookies across restarts.
    """

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


@app.post("/api/process")
async def process(audio: UploadFile = File(...)) -> dict[str, str]:
    """
        Processes voice-based scheduling requests and manages Google Calendar integration.

        The workflow follows these steps:
        1. Audio Conversion: Converts incoming WebM audio to MP3.
        2. Transcription: Uses OpenAI Whisper to convert speech to text.
        3. Intent Extraction: Uses an LLM to parse meeting details (date/time) from the transcript.
        4. Conflict Validation: Checks Google Calendar for overlapping events.
        5. Execution: Adds the event to the calendar or returns a conflict warning.

        Args:
            audio (UploadFile): A multipart form-data file containing the user's voice recording.

        Returns:
            dict: A JSON response containing:
                - message (str): The recognized transcript from the user.
                - reply (str): The text-based response from the assistant.
                - audio (str): A base64 encoded string of the assistant's voice reply.
    """

    # 1. Fetch the input audio file and save as mp3 locally
    temp_webm_path = os.path.join(UPLOAD_DIR, "temp_recording.webm")
    with open(temp_webm_path, "wb") as buffer:
        shutil.copyfileobj(audio.file, buffer)
        buffer.flush()
    try:
        audio_data = AudioSegment.from_file(temp_webm_path)
        audio_data.export(MP3_PATH, format="mp3")
        os.remove(temp_webm_path)
    except Exception as e:
        return {"message": "Conversion failed", "error": str(e)}

    # 2. Get the transcript of the input audio using Openai whisper model
    transcript_payload = whisper_model.transcribe(MP3_PATH)
    transcript = transcript_payload["text"]

    # 3. Feed the transcript to the LLM model to get an reply
    raw_model_response = assistant.ask_a_question(transcript)
    parsed_model_response = extract_json_or_text(raw_model_response)

    # The model didnt return a json, which means the LLM need more information from user
    if not isinstance(parsed_model_response, dict):
        final_model_response = parsed_model_response
        audio_data = generate_audio_base64(final_model_response)
        return {"message": transcript, "reply": final_model_response, "audio": audio_data}

    # 4. Perform a time conflict check to determine the final LLM reply, perform the scheduling on Google Calendar if no conflict found
    is_time_valid, validate_msg = validate_meeting_time(parsed_model_response)

    if not is_time_valid:
        return await finalize_assistant_response(
            transcript, f"Please select another time. {validate_msg}"
        )
    
    # Check for time conflict
    if not "bypass restriction" in raw_model_response.lower():
        all_conflicted_events = await get_all_conflict_event(parsed_model_response)
        if all_conflicted_events:
            final_model_response = "It seems like there is a time conflict with the events shown below, Would you like to schedule for another time."
            return await finalize_assistant_response(
                transcript,
                f"{final_model_response} {generate_conflict_message(all_conflicted_events)}",
                final_model_response
            )
        
    # 5. All good, add the event to Google Calendar now
    await add_calendar_event(parsed_model_response)

    return await finalize_assistant_response(
        transcript,
        "Alright, the schedule has been successfully added to the calendar!",
    )

async def get_all_conflict_event(parsed_model_response: AppointmentData):
    all_conflicted_events = {}

    periods = split_time_period(parsed_model_response)
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
        curren_conflicting_event = find_conflicting_events(
            period, [preprocess_event(i) for i in existing_events]
        )
        if len(curren_conflicting_event) > 0:
            all_conflicted_events[format_date(date)] = curren_conflicting_event
    
    return all_conflicted_events

async def finalize_assistant_response(transcript: str, reply_text: str, reply_text_for_audio: str=None) -> dict:
    """Centralized helper to update history, generate audio, and format API return."""
    assistant.append_chat_history({"role": "system", "content": reply_text})
    if reply_text_for_audio:
        audio_data = generate_audio_base64(reply_text_for_audio)
    else:
        audio_data = generate_audio_base64(reply_text)
    
    return {
        "message": transcript,
        "reply": reply_text,
        "audio": audio_data
    }