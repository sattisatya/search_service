import os
import re
from openai import AzureOpenAI
from fastapi import HTTPException
from datetime import datetime, timezone

def get_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=os.getenv('AZURE_AI_API_KEY'),
        api_version="2024-10-21",
        azure_endpoint=os.getenv('AZURE_AI_ENDPOINT')
    )

def get_embedding(text: str, client: AzureOpenAI):
    try:
        resp = client.embeddings.create(model=os.getenv('TEXT_EMBEDDING_3_LARGE_DEPLOYMENT', 'text-embedding-ada-002'), input=text)
        return resp.data[0].embedding
    except Exception:
        raise HTTPException(status_code=500, detail="Embedding failed")

def chat_completion(client: AzureOpenAI, deployment: str, messages: list, temperature: float = 0.7, max_tokens: int = 500):
    return client.chat.completions.create(
        model=deployment,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )

def generate_chat_title(client: AzureOpenAI, question: str) -> str:
    prompt = f"""
Generate a short (max 7 words) clear, professional title summarizing this chat based ONLY on the first user question below.

Question: {question}

Return only the title, no quotes, no punctuation at end.
"""
    try:
        resp = client.chat.completions.create(
            model=os.getenv('GPT_4_1_MINI_DEPLOYMENT', 'gpt-4.1-mini'),
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