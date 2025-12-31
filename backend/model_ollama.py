import datetime
from ollama import chat, ChatResponse
from typing import Dict

OLLAMA_MODEL = "gemma3:12b"


class LLM_Helper:
    """
    A wrapper for ollama llm model, mainly used for creating chat session, saving conversation history

    """

    def __init__(self):
        current_time = datetime.datetime.now().strftime("%A, %B %d, %Y %H:%M")
        self.init_prompt = f"""
            Role: Google Calendar Booking Assistant.
            Current Context: Today is {current_time}.

            Objectives:
            1. Extract meeting details (name, location, description, start/end date, start/end time).
            2. Validate: Dates must be future/today. Times must be 1-12am/pm. 
            3. Logic:
            - Missing/Invalid Info: Ask a follow-up question if start/end date and start/end time is unclear. Other information are not required.
            - Info Gathered: State "The meeting will be scheduled on [Full Month Date], from [time] to [time]. Please confirm." Do not output the JSON before the user has approved it.
            - User Confirms: Output raw JSON ONLY. No markdown, backticks, or preamble.
            - Conflict Bypass: If the user insists on a time despite a system conflict, output: bypass restriction {{JSON}}

            Data Formatting:
            - JSON Dates: dd/mm/yyyy | JSON Times: HH:MMam/pm (no spaces).
            - Conversation: Use full month names (e.g., December).
            - Missing values: ""

            Strict JSON Structure:
            {{"meeting_name": "", "location": "", "description": "", "start_date": "", "end_date": "", "start_time": "", "end_time": ""}}
        """
        self.restart_chat_session()

    def restart_chat_session(self) -> None:
        self.chat_history = [
            {
                "role": "system",
                "content": self.init_prompt,
            },
        ]

    def ask_a_question(self, prompt: str) -> str:
        self.chat_history += [{"role": "user", "content": prompt}]

        response: ChatResponse = chat(model=OLLAMA_MODEL, messages=self.chat_history)

        self.chat_history += [
            {"role": "Assistant", "content": response.message.content}
        ]

        return response.message.content

    def append_chat_history(self, chat_obj: Dict[str, str]) -> None:
        self.chat_history += [chat_obj]
