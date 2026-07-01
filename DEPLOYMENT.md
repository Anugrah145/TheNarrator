# Deployment Guide

This guide explains how to deploy **The Narrator** to Streamlit Community Cloud and set up the database.

## 1. Database Setup (Supabase)

We use **Supabase** (Free Tier) to persist every game action — including incomplete stories.

1.  Go to [Supabase](https://supabase.com/) and create a free account.
2.  Create a new Project.
3.  Go to the **SQL Editor** in the left sidebar.
4.  Run the following SQL to create the tables:

```sql
-- Master table: one row per game session
CREATE TABLE stories (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id text NOT NULL,
  secret_ending text,
  storyteller_name text,
  genre text,
  narration_style text,
  is_game_over boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

-- Action log: every player action and DM response
CREATE TABLE story_actions (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  story_id uuid REFERENCES stories(id) ON DELETE CASCADE,
  action_order integer NOT NULL,
  role text NOT NULL,
  content text NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Index for fast lookups by story
CREATE INDEX idx_story_actions_story_id ON story_actions(story_id);

-- Protagonist table: optional main character profile per story
CREATE TABLE protagonists (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  story_id uuid REFERENCES stories(id) ON DELETE CASCADE,
  name text,
  description text,
  status jsonb,
  created_at timestamptz DEFAULT now()
);
```

5.  Go to **Project Settings** -> **API**.
6.  Copy the `Project URL` and `anon` / `public` Key. You will need these for deployment.

## 2. Local Development

1.  Copy `.env` and fill in your credentials:

```
SUPABASE_URL=your_supabase_project_url_here
SUPABASE_KEY=your_supabase_anon_key_here
GROQ_API_KEY=your_groq_api_key_here
```

2.  The app loads `.env` automatically via `python-dotenv`.
3.  `.env` is in `.gitignore` — never commit it.

## 3. Deployment (Streamlit Community Cloud)

1.  Push your code to a GitHub repository.
2.  Go to [Streamlit Community Cloud](https://streamlit.io/cloud) and sign in.
3.  Click **New app**.
4.  Select your repository, branch (`main`), and main file path (`app.py`).
5.  Click **Advanced Settings** -> **Secrets**.
6.  Add your secrets in the following format:

```toml
GROQ_API_KEY = "your_groq_api_key_here"
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_KEY = "your_supabase_anon_key"
```

7.  Click **Save** and then **Deploy**.

## 4. CI/CD Pipeline

A GitHub Action has been set up in `.github/workflows/ci.yml`.
- It runs automatically on every push to `main` or Pull Request.
- It installs dependencies and checks for syntax errors.
- You can view the status in the **Actions** tab of your GitHub repository.
