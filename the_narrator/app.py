import os
import uuid
import streamlit as st
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from .types import GameState
from .agents import SetupNode, StorytellerNode, JudgeNode, ProtagonistNode, GuideNode
from .ui import render_styles, render_header, render_configuration, render_story_log, render_action_panel

MODEL_NAME = "llama-3.3-70b-versatile"


def build_graph(llm):
    workflow = StateGraph(GameState)
    workflow.add_node("setup", SetupNode(llm))
    workflow.add_node("storyteller", StorytellerNode(llm))
    workflow.add_node("protagonist", ProtagonistNode(llm))
    workflow.add_node("judge", JudgeNode(llm))
    workflow.add_node("guide", GuideNode(llm))

    def route_start(state: GameState):
        if not state.get("current_scene"):
            return "setup"
        return "storyteller"

    workflow.set_conditional_entry_point(
        route_start,
        {"setup": "setup", "storyteller": "storyteller"}
    )

    workflow.add_edge("setup", "guide")
    workflow.add_edge("guide", END)
    workflow.add_edge("storyteller", "protagonist")
    workflow.add_edge("protagonist", "judge")
    workflow.add_edge("protagonist", "guide")
    workflow.add_edge("judge", END)

    return workflow.compile()


def main():
    st.set_page_config(page_title="Infinite Adventure", layout="wide")
    if "config_expanded" not in st.session_state:
        st.session_state.config_expanded = True

    render_styles()
    render_header()

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("GROQ_API_KEY")
        except FileNotFoundError:
            pass

    if not api_key:
        api_key = st.text_input("Enter Groq API Key", type="password", key="groq_api_key")

    if not api_key:
        st.warning("Please enter a Groq API Key to start.")
        return

    config = render_configuration()
    storyteller_name = config["storyteller_name"]
    protagonist_name = config["protagonist_name"]
    protagonist_description = config["protagonist_description"]
    genres = config["genres"]
    custom_genre = config["custom_genre"]
    narration_style = config["narration_style"]
    custom_style = config["custom_style"]
    narrator_voice = config["narrator_voice"]
    mute_audio = config["mute_audio"]
    start_btn = config["start_btn"]

    if "graph" not in st.session_state:
        llm = ChatGroq(temperature=0.7, model_name=MODEL_NAME, groq_api_key=api_key)
        llm.storage = None
        workflow = build_graph(llm)
        st.session_state.graph = workflow

    if "game_state" not in st.session_state:
        st.session_state.game_state = None
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    selected_genre = ", ".join(genres) if genres else ""
    if custom_genre:
        selected_genre = custom_genre.strip()

    selected_style = narration_style
    if custom_style:
        selected_style = custom_style.strip()

    if start_btn and selected_genre and storyteller_name:
        initial_state = GameState(
            genre=selected_genre,
            storyteller_name=storyteller_name,
            protagonist_name=protagonist_name,
            protagonist_description=protagonist_description,
            protagonist_status={"health":100, "mood":"neutral", "notes":""},
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
        result = st.session_state.graph.invoke(initial_state)
        st.session_state.game_state = result
        st.rerun()

    if st.session_state.game_state:
        state = st.session_state.game_state
        render_story_log(state, mute_audio)

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

        action_taken = render_action_panel(state)
        if action_taken:
            current_state = state.copy()
            current_state["user_input"] = action_taken
            current_state["narration_style"] = narration_style
            current_state["narrator_voice"] = narrator_voice
            st.markdown(
                "<div class='story-loader'>The narrator leans in, considering the next twist...<span class='loader-dot'></span><span class='loader-dot'></span><span class='loader-dot'></span></div>",
                unsafe_allow_html=True
            )
            result = st.session_state.graph.invoke(current_state)
            st.session_state.game_state = result
            st.rerun()


if __name__ == "__main__":
    main()
