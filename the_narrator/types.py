from typing import List, TypedDict, Optional

class GameState(TypedDict):
    genre: str
    storyteller_name: str
    protagonist_name: Optional[str]
    protagonist_description: Optional[str]
    protagonist_status: dict
    story_history: List[dict]
    current_scene: str
    secret_ending: str
    suggested_options: List[str]
    user_input: str
    is_game_over: bool
    narration_style: str
    audio_data: bytes
    narrator_voice: str
