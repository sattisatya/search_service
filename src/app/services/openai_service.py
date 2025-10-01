import os
import re
from openai import OpenAI
from fastapi import HTTPException
from datetime import datetime, timezone

def get_client() -> OpenAI:
    return OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_embedding(text: str, client: OpenAI):
    try:
        resp = client.embeddings.create(model="text-embedding-ada-002", input=text)
        return resp.data[0].embedding
    except Exception:
        raise HTTPException(status_code=500, detail="Embedding failed")

def chat_completion(client: OpenAI, model: str, messages: list, temperature: float = 0.7, max_tokens: int = 500):
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

def generate_chat_title(client: OpenAI, question: str) -> str:
    prompt = f"""
Generate a short (max 7 words) clear, professional title summarizing this chat based ONLY on the first user question below.

Question: {question}

Return only the title, no quotes, no punctuation at end.
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role":"system","content":"You create concise, descriptive chat titles."},
                {"role":"user","content": prompt.strip()}
            ],
            temperature=0.4,
            max_tokens=30
        )
        title = resp.choices[0].message.content.strip()
        title = title.strip('"').strip("'")
        title = re.sub(r"\s+", " ", title)
        if len(title) > 60:
            title = title[:57].rstrip() + "..."
        return title
    except Exception:
        return "Conversation"