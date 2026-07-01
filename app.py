import os
import typing
import streamlit as st
import streamlit.components.v1 as components
from typing import List, TypedDict, Literal
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
import asyncio
import edge_tts
import tempfile
import base64
from supabase import create_client, Client
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- Constants & Config ---
MODEL_NAME = "llama-3.3-70b-versatile"

# --- State Management ---
class GameState(TypedDict):
    genre: str
    story_history: List[dict] # Changed to list of dicts: {"role": str, "content": str, "audio": bytes}
    current_scene: str
    secret_ending: str
    suggested_options: List[str]
    user_input: str
    is_game_over: bool
    narration_style: str
    audio_data: bytes
    narrator_voice: str

# --- Agent Nodes (Classes) ---

class NodeBase:
    def __init__(self, llm: ChatGroq):
        self.llm = llm

    @staticmethod
    def get_supabase_client():
        """Get Supabase client, resolving credentials from env or Streamlit secrets."""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        # Fallback to Streamlit secrets (for Streamlit Cloud deployment)
        if not url:
            try: url = st.secrets.get("SUPABASE_URL")
            except: pass
        if not key:
            try: key = st.secrets.get("SUPABASE_KEY")
            except: pass

        if not url or not key:
            return None

        return create_client(url, key)

    @staticmethod
    def create_story(session_id, secret_ending, genre, narration_style):
        """Insert a new story row. Returns the story UUID or None on failure."""
        try:
            client = NodeBase.get_supabase_client()
            if not client:
                print("Supabase credentials not found. Skipping save.")
                return None
            data = {
                "session_id": session_id,
                "secret_ending": secret_ending,
                "genre": genre,
                "narration_style": narration_style,
            }
            result = client.table("stories").insert(data).execute()
            story_id = result.data[0]["id"]
            print(f"Story created: {story_id}")
            return story_id
        except Exception as e:
            print(f"Failed to create story: {e}")
            return None

    @staticmethod
    def save_action(story_id, action_order, role, content):
        """Insert a single action into story_actions."""
        if not story_id:
            return
        try:
            client = NodeBase.get_supabase_client()
            if not client:
                return
            data = {
                "story_id": story_id,
                "action_order": action_order,
                "role": role,
                "content": content,
            }
            client.table("story_actions").insert(data).execute()
        except Exception as e:
            print(f"Failed to save action: {e}")

    @staticmethod
    def mark_game_over(story_id):
        """Set is_game_over = true on the story row."""
        if not story_id:
            return
        try:
            client = NodeBase.get_supabase_client()
            if not client:
                return
            client.table("stories").update({"is_game_over": True}).eq("id", story_id).execute()
            print(f"Story {story_id} marked as game over.")
        except Exception as e:
            print(f"Failed to mark game over: {e}")

    async def generate_audio(self, text: str, voice: str = "en-GB-SoniaNeural") -> bytes:
        try:
            communicate = edge_tts.Communicate(text, voice)
            mp3_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_bytes += chunk["data"]
            return mp3_bytes
        except Exception as e:
            print(f"Audio generation failed: {e}")
            return b""

class SetupNode(NodeBase):
    def __call__(self, state: GameState) -> GameState:
        genre = state.get("genre", "Fantasy")
        style = state.get("narration_style", "Standard")
        voice = state.get("narrator_voice", "en-GB-SoniaNeural")
        
        # Generate Secret Ending
        secret_prompt = (
            f"Generate a specific, obscure, and difficult-to-guess secret ending condition for a {genre} text adventure game. "
            "It must be a specific action or phrase the player must do/say. "
            "Examples: 'The player must find the silver spoon and melt it', 'The player must say the word 'banana' three times'. "
            "Output ONLY the condition string."
        )
        secret_response = self.llm.invoke([SystemMessage(content=secret_prompt)])
        secret_ending = secret_response.content.strip()

        # Generate Opening Scene
        opening_prompt = (
            f"You are a Dungeon Master. Start a new {genre} adventure. "
            f"Narration Style: {style}\n"
            "Describe the opening scene vividly. Keep it under 150 words. "
            "Do not ask the user what they want to do, just set the scene."
        )
        opening_response = self.llm.invoke([SystemMessage(content=opening_prompt)])
        opening_scene = opening_response.content.strip()

        # Generate Audio
        audio_bytes = asyncio.run(self.generate_audio(opening_scene, voice))

        # --- Persist to DB ---
        session_id = st.session_state.get("session_id", "unknown")
        story_id = self.create_story(session_id, secret_ending, genre, style)
        st.session_state.story_id = story_id
        st.session_state.action_order = 1
        self.save_action(story_id, 1, "dm", opening_scene)

        return {
            "secret_ending": secret_ending,
            "current_scene": opening_scene,
            "story_history": [{"role": "dm", "content": opening_scene, "audio": audio_bytes}],
            "is_game_over": False,
            "user_input": "",
            "audio_data": b""
        }

class StorytellerNode(NodeBase):
    def __call__(self, state: GameState) -> GameState:
        history = state.get("story_history", [])
        user_input = state.get("user_input", "")
        genre = state.get("genre", "Unknown")
        style = state.get("narration_style", "Standard")
        voice = state.get("narrator_voice", "en-GB-SoniaNeural")
        
        # Context window management: keep last few turns to avoid token limits if history gets huge
        # For this demo, we'll pass the last 5 entries + current input
        recent_history = history[-5:]
        context = "\n".join([f"{entry['role'].upper()}: {entry['content']}" for entry in recent_history])
        
        prompt = (
            f"You are the Dungeon Master for a {genre} game. "
            f"Narration Style: {style}\n"
            f"Current Story Context:\n{context}\n\n"
            f"Player Action: {user_input}\n\n"
            "Rules:\n"
            "1. Accept ANY user input, no matter how absurd. Adapt the story to it.\n"
            "2. The player CANNOT die. If they try to die, resurrect them or make them survive in a funny/weird way.\n"
            "3. Keep the narrative moving. Be creative. Keep response under 100 words.\n"
            "4. Do NOT give options at the end. Just the story."
        )
        
        response = self.llm.invoke([SystemMessage(content=prompt)])
        new_scene = response.content.strip()
        
        # Generate Audio
        audio_bytes = asyncio.run(self.generate_audio(new_scene, voice))

        # --- Persist to DB ---
        story_id = st.session_state.get("story_id")
        order = st.session_state.get("action_order", 1)
        order += 1
        self.save_action(story_id, order, "player", user_input)
        order += 1
        self.save_action(story_id, order, "dm", new_scene)
        st.session_state.action_order = order

        new_history = history + [
            {"role": "player", "content": user_input, "audio": None},
            {"role": "dm", "content": new_scene, "audio": audio_bytes}
        ]

        return {
            "current_scene": new_scene,
            "story_history": new_history,
            "audio_data": b""
        }

class JudgeNode(NodeBase):
    def __call__(self, state: GameState) -> GameState:
        user_input = state.get("user_input", "")
        current_scene = state.get("current_scene", "")
        secret_ending = state.get("secret_ending", "")
        
        prompt = (
            f"Secret Ending Condition: {secret_ending}\n"
            f"Player Action: {user_input}\n"
            f"Resulting Scene: {current_scene}\n\n"
            "Did the player trigger the secret ending? "
            "Reply strictly with 'YES' or 'NO'."
        )
        
        response = self.llm.invoke([SystemMessage(content=prompt)])
        is_game_over = "YES" in response.content.strip().upper()
        
        if is_game_over:
            story_id = st.session_state.get("story_id")
            self.mark_game_over(story_id)

        return {"is_game_over": is_game_over}

class GuideNode(NodeBase):
    def __call__(self, state: GameState) -> GameState:
        current_scene = state.get("current_scene", "")
        genre = state.get("genre", "")
        style = state.get("narration_style", "Standard")
        
        prompt = (
            f"Based on this scene in a {genre} game:\n'{current_scene}'\n\n"
            f"Generate 3 short, distinct, and relevant action options for the player. "
            f"The options should fit the {style} style. "
            "Format: Option 1 | Option 2 | Option 3"
        )
        
        response = self.llm.invoke([SystemMessage(content=prompt)])
        content = response.content.strip()
        
        # Basic parsing
        if "|" in content:
            options = [opt.strip() for opt in content.split("|")]
        else:
            # Fallback parsing if LLM doesn't follow format perfectly
            options = content.split("\n")[:3]
            
        # Ensure exactly 3 options
        while len(options) < 3:
            options.append("Do something else")
        options = options[:3]
        
        return {"suggested_options": options}

# --- Main App Logic ---


def build_graph(llm):
    workflow = StateGraph(GameState)
    
    workflow.add_node("setup", SetupNode(llm))
    workflow.add_node("storyteller", StorytellerNode(llm))
    workflow.add_node("judge", JudgeNode(llm))
    workflow.add_node("guide", GuideNode(llm))
    
    def route_start(state: GameState):
        if not state.get("current_scene"):
            return "setup"
        return "storyteller"

    workflow.set_conditional_entry_point(
        route_start,
        {
            "setup": "setup",
            "storyteller": "storyteller"
        }
    )
    
    workflow.add_edge("setup", "guide")
    workflow.add_edge("guide", END)
    
    workflow.add_edge("storyteller", "judge")
    workflow.add_edge("storyteller", "guide")
    workflow.add_edge("judge", END)
    
    return workflow.compile()

# Patching the main function to use build_graph
if __name__ == "__main__":
    # We need to move the build_graph logic inside main or accessible to it.
    # I will rewrite the main function in the file content to include this logic properly.
    pass

# Redefining main for the file content
def main():
    st.set_page_config(page_title="Infinite Adventure", layout="wide")
    
    st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e2e2e; color: white; }
    .stButton>button:hover { background-color: #4e4e4e; color: #00ff00; }
    .chat-container { background-color: #1e1e1e; padding: 20px; border-radius: 15px; margin-bottom: 20px; }
    .story-loader { display: flex; align-items: center; gap: 10px; font-size: 1rem; color: #d3d3d3; margin-bottom: 10px; }
    .story-loader .loader-dot { width: 10px; height: 10px; border-radius: 50%; background: #00ff00; animation: pulse 1s ease-in-out infinite; }
    .story-loader .loader-dot:nth-child(2) { animation-delay: 0.2s; }
    .story-loader .loader-dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 0.4; }
        50% { transform: scale(1.5); opacity: 1; }
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("♾️ Infinite Narrative Adventure")
    st.caption("Powered by LangGraph & Llama3-70b")

    with st.sidebar:
        st.header("Configuration")
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            try:
                api_key = st.secrets.get("GROQ_API_KEY")
            except FileNotFoundError:
                pass
        
        if not api_key:
            api_key = st.text_input("Enter Groq API Key", type="password")
        
        if not api_key:
            st.warning("Please enter a Groq API Key to start.")
            return

        st.header("Game Setup")
        genres = st.multiselect(
            "Select Genres (Max 2)",
            ["Fantasy", "Sci-Fi", "Horror", "Cyberpunk", "Comedy", "Mystery", "Western"],
            max_selections=2
        )
        
        narration_style = st.selectbox(
            "Narration Style",
            ["Standard", "Shakespearean", "Noir Detective", "Children's Book", "Rhyming Couplets", 
             "Cyberpunk Slang", "High Fantasy", "Pirate", "Scientific Report", "Gossip Columnist"]
        )
        
        voice_options = {
            "British Female": "en-GB-SoniaNeural",
            "British Male": "en-GB-RyanNeural",
            "US Female": "en-US-AriaNeural",
            "US Male": "en-US-ChristopherNeural",
            "Australian Female": "en-AU-NatashaNeural",
            "Australian Male": "en-AU-WilliamNeural",
            "Indian Female": "en-IN-NeerjaNeural",
            "Indian Male": "en-IN-PrabhatNeural",
            "Childlike Voice": "en-US-JennyNeural",
            "Comforting Voice": "en-US-AmberNeural",
            "Passionate Voice": "en-US-GuyNeural",
            "Funny Cartoon Voice": "en-US-JessaNeural"
        }
        selected_voice_name = st.selectbox("Narrator Voice", list(voice_options.keys()))
        narrator_voice = voice_options[selected_voice_name]
        
        st.markdown("---")
        custom_genre = st.text_input("Or type your own genre")
        custom_style = st.text_input("Or type your own narration style")
        
        mute_audio = st.checkbox("Mute Narrator", value=False)
        
        start_btn = st.button("Start New Game")

    if "graph" not in st.session_state:
        llm = ChatGroq(temperature=0.7, model_name=MODEL_NAME, groq_api_key=api_key)
        
        workflow = StateGraph(GameState)
        workflow.add_node("setup", SetupNode(llm))
        workflow.add_node("storyteller", StorytellerNode(llm))
        workflow.add_node("judge", JudgeNode(llm))
        workflow.add_node("guide", GuideNode(llm))
        
        def route_start(state: GameState):
            if not state.get("story_history"): # Use history as indicator of fresh game
                return "setup"
            return "storyteller"

        workflow.set_conditional_entry_point(
            route_start,
            {"setup": "setup", "storyteller": "storyteller"}
        )
        
        workflow.add_edge("setup", "guide")
        workflow.add_edge("guide", END)
        workflow.add_edge("storyteller", "judge")
        workflow.add_edge("storyteller", "guide")
        workflow.add_edge("judge", END)
        
        st.session_state.graph = workflow.compile()

    if "game_state" not in st.session_state:
        st.session_state.game_state = None
    if "session_id" not in st.session_state:
        import uuid
        st.session_state.session_id = str(uuid.uuid4())

    selected_genre = ", ".join(genres) if genres else ""
    if custom_genre:
        selected_genre = custom_genre.strip()

    selected_style = narration_style
    if custom_style:
        selected_style = custom_style.strip()

    if start_btn and selected_genre:
        initial_state = GameState(
            genre=selected_genre,
            story_history=[],
            current_scene="",
            secret_ending="",
            suggested_options=[],
            user_input="",
            is_game_over=False,
            narration_style=selected_style,
            audio_data=b"",
            narrator_voice=narrator_voice
        )
        st.markdown(
            "<div class='story-loader'>The storyteller pauses, ink poised and ready to reveal the first scene...<span class='loader-dot'></span><span class='loader-dot'></span><span class='loader-dot'></span></div>",
            unsafe_allow_html=True
        )
        # with st.spinner("The storyteller pauses, ink poised and ready to reveal the first scene..."):
        result = st.session_state.graph.invoke(initial_state)
        st.session_state.game_state = result
        st.rerun()

    if st.session_state.game_state:
        state = st.session_state.game_state
        
        st.markdown("### 📜 Story Log")
        with st.container():
            for i, entry in enumerate(state["story_history"]):
                role = entry["role"]
                content = entry["content"]
                audio = entry.get("audio")
                
                if role == "player":
                    st.info(f"**Player:** {content}")
                else:
                    # DM Content
                    with st.chat_message("assistant"):
                        st.write(content)
                        if audio and not mute_audio:
                            # Custom Audio Player using st.iframe and a data URI
                            b64_audio = base64.b64encode(audio).decode()
                            audio_html = """
                                <html>
                                <head>
                                    <meta charset=\"utf-8\" />
                                </head>
                                <body style=\"margin:0; padding:0;\">
                                    <audio id=\"audio_{i}\" src=\"data:audio/mp3;base64,{b64_audio}\"></audio>
                                    <button id=\"toggle_{i}\" type=\"button\" style=\"all:unset; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; width:40px; height:40px; border-radius:50%; background:#111; color:#ffffff; border:1px solid rgba(255,255,255,0.16); font-size:18px; transition:background 0.2s;\">&#9654;</button>
                                    <script>
                                        const audio = document.getElementById('audio_{i}');
                                        const button = document.getElementById('toggle_{i}');
                                        button.onclick = () => {{
                                            if (audio.paused) {{
                                                audio.play();
                                                button.textContent = '\u23F8';
                                            }} else {{
                                                audio.pause();
                                                button.textContent = '\u25B6';
                                            }}
                                        }};
                                        audio.onended = () => {{ button.textContent = '\u25B6'; }};
                                    </script>
                                </body>
                                </html>
                            """.format(b64_audio=b64_audio, i=i)
                            b64_html = base64.b64encode(audio_html.encode('utf-8')).decode()
                            st.iframe(f"data:text/html;charset=utf-8;base64,{b64_html}", height=75)

        if state["is_game_over"]:
            st.balloons()
            st.markdown(f"""
            # 🏆 VICTORY!
            You triggered the Secret Ending!
            **The Secret Condition was:** > *{state['secret_ending']}*
            """)
            if st.button("Play Again"):
                st.session_state.game_state = None
                st.rerun()
            return

        st.markdown("---")
        st.markdown("### 🎮 Your Action")
        
        col1, col2, col3 = st.columns(3)
        options = state.get("suggested_options", ["Wait...", "Look around", "Think"])
        
        action_taken = None
        if col1.button(options[0]): action_taken = options[0]
        if col2.button(options[1]): action_taken = options[1]
        if col3.button(options[2]): action_taken = options[2]
            
        custom_action = st.text_input("Or type your own action:", key="custom_input")
        if st.button("Submit Custom Action") and custom_action:
            action_taken = custom_action

        if action_taken:
            current_state = state.copy()
            current_state["user_input"] = action_taken
            # Update style and voice in case user changed it mid-game
            current_state["narration_style"] = narration_style
            current_state["narrator_voice"] = narrator_voice
            
            st.markdown(
                "<div class='story-loader'>The narrator leans in, considering the next twist...<span class='loader-dot'></span><span class='loader-dot'></span><span class='loader-dot'></span></div>",
                unsafe_allow_html=True
            )
            # with st.spinner("The narrator leans in, considering the next twist..."):
            result = st.session_state.graph.invoke(current_state)
            st.session_state.game_state = result
            st.rerun()

if __name__ == "__main__":
    main()
