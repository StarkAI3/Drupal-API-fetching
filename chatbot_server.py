import os
from dotenv import load_dotenv
load_dotenv()
import re
from fastapi import FastAPI
from pydantic import BaseModel
from fetch_and_store import get_embedding, search_vectors  # Updated import
from gemini_utils import generate_gemini_response
from language_utils import detect_language
import multiprocessing
from multiprocessing.pool import ApplyResult

app = FastAPI()

class ChatRequest(BaseModel):
    query: str

def extract_link(text):
    urls = re.findall(r'https?://\S+', text)
    return urls[0] if urls else None

def search_context(query, top_k=5):
    embedding = get_embedding(query)
    res = search_vectors(embedding, top_k=top_k)
    if isinstance(res, ApplyResult):
        res = res.get()
    results = []
    print("\nDEBUG: Top matches for query:", query)
    for match in res['matches']:
        meta = match['metadata']
        text = meta.get('text', '')
        print("  -", text[:120].replace('\n', ' '))
        link = extract_link(text)
        results.append({
            'id': match['id'],
            'score': match['score'],
            'text': text,
            'content_type': meta.get('content_type', ''),
            'link': link
        })
    return results

def compose_prompt(user_query, context_results, lang):
    context_str = ''
    for i, ctx in enumerate(context_results):
        context_str += f"[{i+1}] {ctx['text']}\n"
        if ctx['link']:
            context_str += f"Link: {ctx['link']}\n"
    if lang == 'mr':
        prompt = (
            f"तुम्ही PMC वेबसाइटसाठी एक माहितीपूर्ण सहाय्यक आहात. वापरकर्त्याचा प्रश्न: '{user_query}'\n\n"
            f"संदर्भ:\n{context_str}\n"
            f"वरील संदर्भात जर 'SAP Sasa-40 Training Workshop' किंवा तत्सम शब्द असलेला परिपत्रक असेल, तर त्याची माहिती आणि लिंक उत्तरात द्या.\n"
            f"वरील संदर्भ वापरून, वापरकर्त्याच्या प्रश्नाचे उत्तर मराठीत द्या. शक्य असल्यास, संबंधित लिंक उत्तरात समाविष्ट करा."
        )
    else:
        prompt = (
            f"You are an informative assistant for the PMC website. User's question: '{user_query}'\n\n"
            f"Context:\n{context_str}\n"
            f"If any context contains the phrase 'SAP Sasa-40 Training Workshop' or similar, answer with its details and link.\n"
            f"Using the above context, answer the user's question in English. If possible, include the relevant link in your answer."
        )
    print("\nDEBUG: Prompt sent to Gemini:\n", prompt)
    return prompt

@app.post('/chat')
async def chat(request: ChatRequest):
    user_query = request.query.strip()
    lang = detect_language(user_query)
    context_results = search_context(user_query, top_k=5)
    prompt = compose_prompt(user_query, context_results, lang)
    answer = generate_gemini_response(prompt)
    print("\nDEBUG: Gemini raw answer:\n", answer)

    # Check for direct match in context
    keyword = "SAP Sasa-40 Training Workshop"
    direct_circular = None
    for ctx in context_results:
        if keyword.lower() in ctx['text'].lower():
            direct_circular = ctx
            break

    # Build direct answer if found
    direct_answer = None
    if direct_circular:
        direct_answer = f"Subject: {keyword}\nDetails: {direct_circular['text']}"
        if direct_circular['link']:
            direct_answer += f"\nLink: {direct_circular['link']}"

    # Always append the top context's link if not present in the answer
    for ctx in context_results:
        if ctx['link'] and ctx['link'] not in answer:
            if lang == 'mr':
                answer += f"\n\nलिंक: {ctx['link']}"
            else:
                answer += f"\n\nLink: {ctx['link']}"
            break

    # Return both Gemini's answer and direct circular details if found
    return {
        "answer": answer,
        "language": lang,
        "direct_circular": direct_answer if direct_answer else None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chatbot_server:app", host="0.0.0.0", port=8000, reload=True) 