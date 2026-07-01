import streamlit as st
import base64
from .types import GameState
from .helpers import is_valid_protagonist_description


def render_styles():
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
    .hero-card { background: #111; padding: 20px; border-radius: 18px; margin-bottom: 20px; color: #f2f2f2; }
    .hero-card h2 { margin: 0 0 10px; font-size: 1.6rem; }
    .hero-card p { margin: 0; line-height: 1.5; color: #bfbfbf; }
    .mobile-setup > div { margin-bottom: 16px; }
    .mobile-setup label { font-weight: 600; margin-bottom: 6px; display: block; }
    .mobile-setup .stTextInput>div>div>input,
    .mobile-setup .stSelectbox>div>div>div>div>div>div { width: 100% !important; }
    @media (max-width: 768px) {
        .css-1d391kg { padding: 16px; }
    }
    </style>
    """, unsafe_allow_html=True)


def render_header():
    st.title("♾️ Infinite Narrative Adventure")
    st.caption("Powered by LangGraph & Llama3-70b")
    st.markdown(
        """
        <div class='hero-card'>
            <h2>Start your next adventure</h2>
            <p>Become the storyteller, choose a mood, and let the narrative unfold.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_configuration():
    with st.expander("Configuration", expanded=st.session_state.config_expanded):
        storyteller_name = st.text_input(
            "Your storyteller name",
            key="storyteller_name",
            placeholder="e.g. Aria the Bard"
        )
        st.markdown("**Main character profile (optional)**")
        protagonist_name = st.text_input("Protagonist name (optional)", key="protagonist_name", placeholder="e.g. Rowan")
        protagonist_description = st.text_area(
            "Protagonist description (optional)",
            key="protagonist_description",
            placeholder="Describe the protagonist in a few sentences. Include personality, role, or how they feel.",
            help="Write only a character description. Do not ask questions, request weather updates, or enter code."
        )
        if protagonist_name:
            summary = protagonist_description.strip() or "No description provided"
            st.markdown(
                f"<div class='hero-card'><strong>{protagonist_name}</strong><br/><small>{summary}</small></div>",
                unsafe_allow_html=True
            )
        if protagonist_description and not is_valid_protagonist_description(protagonist_description):
            st.error("Invalid description. Please enter only a character description without asking questions or requesting code/weather information.")
            protagonist_description = ""
        st.session_state.protagonist_description = protagonist_description
        if not storyteller_name:
            st.warning("A storyteller name is required to begin.")

        st.markdown("### Adventure setup")
        genres = st.multiselect(
            "Select Genres (Max 2)",
            ["Fantasy", "Sci-Fi", "Horror", "Cyberpunk", "Comedy", "Mystery", "Western"],
            max_selections=2,
            key="genres"
        )

        custom_genre = st.text_input("Or type your own genre", key="custom_genre")

        narration_style = st.selectbox(
            "Narration Style",
            ["Standard", "Shakespearean", "Noir Detective", "Children's Book", "Rhyming Couplets", 
             "Cyberpunk Slang", "High Fantasy", "Pirate", "Scientific Report", "Gossip Columnist"],
            key="narration_style"
        )
        custom_style = st.text_input("Or type your own narration style", key="custom_style")

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
        selected_voice_name = st.selectbox("Narrator Voice", list(voice_options.keys()), key="selected_voice_name")
        narrator_voice = voice_options[selected_voice_name]

        mute_audio = st.checkbox("Mute Narrator", value=False, key="mute_audio")

        st.markdown("---")
        st.markdown(
            "**How to begin:** 1) Enter your storyteller name, 2) choose a genre and style, 3) tap Create My Story."
        )

        start_btn = st.button("Create My Story")
        if start_btn:
            st.session_state.config_expanded = False

    return {
        "storyteller_name": storyteller_name,
        "protagonist_name": protagonist_name,
        "protagonist_description": protagonist_description,
        "genres": genres,
        "custom_genre": custom_genre,
        "narration_style": st.session_state.get("narration_style"),
        "custom_style": custom_style,
        "narrator_voice": narrator_voice,
        "mute_audio": mute_audio,
        "start_btn": start_btn,
    }


def render_story_log(state: GameState, mute_audio: bool):
    st.markdown("### 📜 Story Log")
    with st.container():
        for i, entry in enumerate(state["story_history"]):
            role = entry["role"]
            content = entry["content"]
            audio = entry.get("audio")

            if role == "player":
                st.info(f"**Player:** {content}")
            else:
                with st.chat_message("assistant"):
                    st.write(content)
                    if audio and not mute_audio:
                        b64_audio = base64.b64encode(audio).decode()
                        audio_html = f"""
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
                        """
                        b64_html = base64.b64encode(audio_html.encode('utf-8')).decode()
                        st.iframe(f"data:text/html;charset=utf-8;base64,{b64_html}", height=75)


def render_action_panel(state: GameState):
    st.markdown("---")
    st.markdown("### 🎮 Your Action")

    col1, col2, col3 = st.columns(3)
    options = state.get("suggested_options", ["Wait...", "Look around", "Think"])

    action_taken = None
    if col1.button(options[0]):
        action_taken = options[0]
    if col2.button(options[1]):
        action_taken = options[1]
    if col3.button(options[2]):
        action_taken = options[2]

    custom_action = st.text_input("Or type your own action:", key="custom_input")
    if st.button("Submit Custom Action") and custom_action:
        action_taken = custom_action

    return action_taken
