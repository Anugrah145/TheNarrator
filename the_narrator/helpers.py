def is_valid_protagonist_description(description: str) -> bool:
    if not description:
        return True
    blocklist = [
        "weather", "forecast", "code", "python", "javascript", "script", "run", "execute", "api",
        "how to", "tell me", "what is", "who is", "when is", "where is", "http", "www.", "openai"
    ]
    text = description.lower()
    return not any(term in text for term in blocklist)
