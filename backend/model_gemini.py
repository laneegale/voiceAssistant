import json
import datetime
from pathlib import Path
from google import genai
from google.genai.types import Part, UserContent

GEMINI_MODEL = "gemini-2.0-flash"
MP3_PATH = Path.joinpath(Path(__file__).parent, "recordings/talking.mp3")

class Gemini:
    def __init__(self):
        self.client = genai.Client()
        current_time = datetime.datetime.now()
        self.init_prompt = f'You are an assistant to help users to create a google calendar booking. The voice recording will be provided to you. Extract meeting details from audio using the current date {current_time}. The user must clearly specify the date amd start/end time of the meeting, and the purpose (e.g. meeting with whom). If these information are missing, output ONLY a follow-up question, until you have gathered all required information; otherwise, output ONLY the raw JSON without markdown wrappers, backticks, or preamble. Use dd/mm/yyyy for dates and HH:MMam/pm (no spaces) for times. Values should be empty strings if missing. The JSON must strictly follow this structure: {{"meeting_name": "", "location": "", "description": "", "start_date": "", "end_date": "", "start_time": "", "end_time": ""}}.'
        self.restart_chat_session()

    def restart_chat_session(self):
        self.chat_session = self.client.chats.create(
            model=GEMINI_MODEL,
            history=[
                UserContent(parts=[Part(text=self.init_prompt)]),
            ],
        )

    def ask_a_question(self, prompt):
        response = self.chat_session.send_message(prompt)

        return response.text

    def ask_a_question_with_mp3(self):
        # user_instruction = self.client.files.upload(file=MP3_PATH)
        with open(MP3_PATH, "rb") as fp:
            audio_content = fp.read()
        audio_part = Part.from_bytes(data=audio_content, mime_type="audio/mp3")

        response = self.chat_session.send_message(audio_part)

        try:
            return json.loads(response.text)
        except (ValueError, TypeError, json.JSONDecodeError):
            return response.text

    def transcript(self):
        user_instruction_audio = self.client.files.upload(file=MP3_PATH)
        response = self.client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                "Please generate the transcript of the attached audio, return plain text, single paragraph of only the transcript",
                user_instruction_audio,
            ],
        )

        return response.text

if __name__ == "__main__":
    # Testing scripts

    current_time = datetime.datetime.now()
    client = genai.Client()

    test1 = "Yo, can you help me to book a meeting with Team tomorrow? Uh, that should last three hours"
    test2 = "Yo, can you help me to book a meeting with Team tomorrow, uh, from 12 PM to 3 PM? Um, it'll be an online meeting."

    prompt = f'You are an assistant to help users to create a google calendar booking. The voice recording will be provided to you. Extract meeting details from audio using the current date {current_time}. The user must clearly specify the date amd start/end time of the meeting, and the purpose (e.g. meeting with whom). If these information are missing, output ONLY a follow-up question, until you have gathered all required information; otherwise, output ONLY the raw JSON without markdown wrappers, backticks, or preamble. Use dd/mm/yyyy for dates and HH:MMam/pm (no spaces) for times. Values should be empty strings if missing. The JSON must strictly follow this structure: {{"meeting_name": "", "location": "", "description": "", "start_date": "", "end_date": "", "start_time": "", "end_time": ""}}.'

    client = genai.Client()
    myfile = client.files.upload(file="test1.mp3")

    response = client.models.generate_content(
        model="gemini-3-flash-preview", contents=[prompt, myfile]
    )

    print(response.text)
