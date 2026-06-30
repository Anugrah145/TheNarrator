# Deployment Guide

This guide explains how to deploy **The Narrator** to Streamlit Community Cloud and set up the database.

## 1. Database Setup (Supabase)

We use **Supabase** (Free Tier) to store completed stories.

1.  Go to [Supabase](https://supabase.com/) and create a free account.
2.  Create a new Project.
3.  Go to the **SQL Editor** in the left sidebar.
4.  Run the following SQL query to create the `stories` table:

```sql
create table stories (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  genre text,
  narration_style text,
  secret_ending text,
  history jsonb,
  triggered_ending boolean
);
```

5.  Go to **Project Settings** -> **API**.
6.  Copy the `Project URL` and `anon` / `public` Key. You will need these for deployment.

## 2. Deployment (Streamlit Community Cloud)

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

## 3. CI/CD Pipeline

A GitHub Action has been set up in `.github/workflows/ci.yml`.
- It runs automatically on every push to `main` or Pull Request.
- It installs dependencies and checks for syntax errors.
- You can view the status in the **Actions** tab of your GitHub repository.
