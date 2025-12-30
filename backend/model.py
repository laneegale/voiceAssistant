import json
from ollama import chat, ChatResponse
import datetime

OLLAMA_MODEL = "gemma3:12b"

class LLM_Helper:
    def __init__(self):
        current_time = datetime.datetime.now()
        self.init_prompt = f'You are an assistant to help users to create a google calendar booking. The voice recording will be provided to you. Extract and infer meeting details from audio using the current date {current_time}. You must collect the date amd start/end time of the meeting. If you cant infer these information or the date/time are invalid (e.g. the date specified by the user is before current date, time should be in 1-12am or 1-12pm, anything exceeding the range is invalid), you should only reply with a follow-up question, until you have gathered all required information. Once you have all information you ask for confirmation (the confirmation message should looks like this and dont include your step to infer the information - The meeting will be scheduled on [date], from [time] to [time] - Please confirm); If the user confirm/approve/said yes to you, DO NOT ask for confirmation again. Just output ONLY the collected inofmration as a raw JSON without markdown wrappers, backticks, or preamble. Use dd/mm/yyyy for dates and HH:MMam/pm (no spaces) for times in the Json. But when you are replying to the user or confirming use the full month name (e.g. Decemeber) instead of number. Values should be empty strings if missing. The JSON must strictly follow this structure: {{"meeting_name": "", "location": "", "description": "", "start_date": "", "end_date": "", "start_time": "", "end_time": ""}}.'
        self.restart_chat_session()

    def restart_chat_session(self):
        self.chat_history = [
            {
                "role": "system",
                "content": self.init_prompt,
            },
        ]

    def ask_a_question(self, prompt, time_conflict_message=None):
        self.chat_history += [{
            'role': "user",
            'content': prompt
        }]
        response: ChatResponse = chat(model=OLLAMA_MODEL, messages=self.chat_history)
        self.chat_history += [{
            'role': "Assistant",
            'content': response.message.content
        }]

        # try:
        #     return json.loads(response.message.content)
        # except (ValueError, TypeError, json.JSONDecodeError):
        return response.message.content
