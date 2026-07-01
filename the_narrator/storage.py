import os
import json
import streamlit as st
from supabase import create_client


def get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url:
        try:
            url = st.secrets.get("SUPABASE_URL")
        except Exception:
            pass
    if not key:
        try:
            key = st.secrets.get("SUPABASE_KEY")
        except Exception:
            pass
    if not url or not key:
        return None
    return create_client(url, key)


def create_story(session_id, secret_ending, genre, narration_style, storyteller_name=None):
    client = get_supabase_client()
    if not client:
        print("Supabase credentials not found. Skipping save.")
        return None
    try:
        data = {
            "session_id": session_id,
            "secret_ending": secret_ending,
            "genre": genre,
            "narration_style": narration_style,
            "storyteller_name": storyteller_name,
        }
        result = client.table("stories").insert(data).execute()
        return result.data[0]["id"]
    except Exception as e:
        print(f"Failed to create story: {e}")
        return None


def save_action(story_id, action_order, role, content):
    if not story_id:
        return
    client = get_supabase_client()
    if not client:
        return
    try:
        data = {
            "story_id": story_id,
            "action_order": action_order,
            "role": role,
            "content": content,
        }
        client.table("story_actions").insert(data).execute()
    except Exception as e:
        print(f"Failed to save action: {e}")


def mark_game_over(story_id):
    if not story_id:
        return
    client = get_supabase_client()
    if not client:
        return
    try:
        client.table("stories").update({"is_game_over": True}).eq("id", story_id).execute()
    except Exception as e:
        print(f"Failed to mark game over: {e}")


def create_protagonist(story_id, name, description):
    if not name:
        return None
    client = get_supabase_client()
    if not client:
        print("Supabase client not available; skipping protagonist save.")
        return None
    try:
        data = {
            "story_id": story_id,
            "name": name,
            "description": description,
            "status": json.dumps({"health":100, "mood":"neutral", "notes":""}),
        }
        result = client.table("protagonists").insert(data).execute()
        return result.data[0]["id"]
    except Exception as e:
        print(f"Failed to create protagonist: {e}")
        return None


def update_protagonist_status(protagonist_id, status):
    if not protagonist_id:
        return
    client = get_supabase_client()
    if not client:
        return
    try:
        client.table("protagonists").update({"status": json.dumps(status)}).eq("id", protagonist_id).execute()
    except Exception as e:
        print(f"Failed to update protagonist status: {e}")
