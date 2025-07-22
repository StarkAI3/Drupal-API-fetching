import os
from dotenv import load_dotenv
load_dotenv()
import re
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fetch_and_store import get_embedding, search_vectors  # Updated import
from gemini_utils import generate_gemini_response
from language_utils import detect_language
import multiprocessing
from multiprocessing.pool import ApplyResult
from typing import Optional
import json
from datetime import datetime

DATA_DIR = 'data'

# Add a function to normalize user queries
import re as _re

def normalize_query(query):
    # Remove generic phrases and punctuation
    query = query.lower()
    query = _re.sub(r"is there any|recent|circular|please|give me|provide|can you|find|show|tell me|about|the|a|an", "", query)
    query = _re.sub(r"[^\w\s]", "", query)  # Remove punctuation
    query = _re.sub(r"\s+", " ", query).strip()
    return query

app = FastAPI()

class ChatRequest(BaseModel):
    query: str
    last_circular_id: Optional[str] = None  # For session context
    history: Optional[list] = None  # Add conversation history

# Add a helper to convert relative links to full URLs
BASE_URL = "https://pmc.gov.in"  # Change to your actual base URL if different

def make_full_url(link):
    if not link:
        return None
    if link.startswith("http://") or link.startswith("https://"):
        return link
    if link.startswith("/"):
        return BASE_URL + link
    return link

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
        # Always prefer the 'file' field for PDF links
        file_link = meta.get('file')
        # Fallbacks if 'file' is not present
        if not file_link:
            file_link = meta.get('link') or meta.get('external_link') or meta.get('url')
        file_link = make_full_url(file_link)
        results.append({
            'id': match['id'],
            'score': match['score'],
            'text': text,
            'content_type': meta.get('content_type', ''),
            'link': file_link,  # This will now always be the PDF if available
            'title': meta.get('title', ''),
            'display_date': meta.get('display_date', ''),
            'nid': meta.get('nid', ''),
            'raw_metadata': meta
        })
    return results

# Helper to find circular by nid in context results

def find_circular_by_id(context_results, nid):
    for ctx in context_results:
        if str(ctx.get('nid')) == str(nid) or ctx.get('id', '').endswith(str(nid)):
            return ctx
    return None

# Removed: load_circular_by_nid and all references to it

def compose_prompt(user_query, context_results, lang, history=None):
    # Compose conversation history for Gemini prompt
    history_str = ''
    if history:
        for turn in history[-6:]:  # Use last 3 exchanges (user+bot)
            role = turn.get('role', 'user')
            content = turn.get('content', '')
            if role == 'user':
                history_str += f"User: {content}\n"
            else:
                history_str += f"Bot: {content}\n"
    context_str = ''
    for i, ctx in enumerate(context_results):
        context_str += f"[{i+1}] Title: {ctx.get('title', '')}\n"
        context_str += f"Text: {ctx['text']}\n"
        if ctx.get('display_date'):
            context_str += f"Date: {ctx['display_date']}\n"
        if ctx.get('link'):
            context_str += f"PDF: {ctx['link']}\n"
        context_str += '\n'
    if lang == 'mr':
        prompt = (
            f"\u0924\u0941\u092e\u094d\u0939\u0940 PMC \u0935\u0947\u092c\u0938\u093e\u0907\u091f\u0938\u093e\u0920\u0940 \u092e\u093e\u0939\u093f\u0924\u0940\u092a\u0942\u0930\u094d\u0923 \u0938\u0939\u093e\u092f\u094d\u092f\u0915 \u0906\u0939\u093e\u0924. \u0935\u093e\u092a\u0930\u0915\u0930\u094d\u0924\u094d\u092f\u093e\u091a\u093e \u092a\u094d\u0930\u0936\u094d\u0928: '{user_query}'\n\n"
            f"\u0938\u0902\u0926\u0930\u094d\u092d:\n{context_str}\n"
            f"\u0935\u0930\u0940\u0932 \u0938\u0902\u0926\u0930\u094d\u092d\u093e\u0924\u0940\u0932 \u092e\u093e\u0939\u093f\u0924\u0940\u091a\u093e \u0935\u093e\u092a\u0930 \u0915\u0930\u0942\u0928 \u0935\u093e\u092a\u0930\u0915\u0930\u094d\u0924\u094d\u092f\u093e\u091a\u094d\u092f\u093e \u092a\u094d\u0930\u0936\u094d\u0928\u093e\u091a\u0947 \u0909\u0924\u094d\u0924\u0930 \u0926\u094d\u092f\u093e. \u091c\u0930 \u0935\u093e\u092a\u0930\u0915\u0930\u094d\u0924\u094d\u092f\u093e\u0928\u0947 \u0935\u093f\u0936\u093f\u0937\u094d\u091f \u0938\u0930\u094d\u0915\u094d\u092f\u0941\u0932\u0930, \u0924\u093e\u0930\u0940\u0916 \u0915\u093f\u0902\u0935\u093e PDF \u0932\u093f\u0902\u0915 \u0935\u093f\u091a\u093e\u0930\u0932\u0940 \u0905\u0938\u0947\u0932, \u0924\u0930 \u0924\u0940 \u092e\u093e\u0939\u093f\u0924\u0940 \u0938\u094d\u092a\u0937\u094d\u091f\u092a\u0923\u0947 \u0909\u0924\u094d\u0924\u0930\u093e\u0924 \u0926\u094d\u092f\u093e. \u0936\u0915\u094d\u092f \u0905\u0938\u0932\u094d\u092f\u093e\u0938 PDF \u0932\u093f\u0902\u0915 \u0909\u0924\u094d\u0924\u0930\u093e\u0924 \u0938\u092e\u093e\u0935\u093f\u0937\u094d\u091f \u0915\u0930\u093e."
        )
    else:
        prompt = (
            f"You are an informative assistant for the PMC website.\n"
            f"Conversation history (for context):\n{history_str}\n"
            f"User's question: '{user_query}'\n\n"
            f"Context:\n{context_str}\n"
            f"Using the above context, answer the user's question in English. If the user asks for a specific circular, date, or PDF link, provide that information explicitly. Always include the PDF link in your answer if available."
        )
    print("\nDEBUG: Prompt sent to Gemini:\n", prompt)
    return prompt

@app.post('/chat')
async def chat(request: ChatRequest):
    user_query = request.query.strip()
    lang = detect_language(user_query)
    history = request.history or []
    normalized_query = normalize_query(user_query)
    print(f"[DEBUG] Original query: {user_query}")
    print(f"[DEBUG] Normalized query: {normalized_query}")

    # Detect if the query is for the latest/most recent circular
    is_latest_query = bool(re.search(r'(latest|most recent|newest|recently published|सर्वात अलीकडील|नवीन|नुकतेच प्रकाशित|नवीनतम|अलीकडेच)', user_query, re.I))
    # Detect if the query is a follow-up (date, summary, details, explain, about, etc. in English and Marathi)
    is_followup = bool(re.search(r'(date|release|issued|when|day|month|year|summarize|summary|details|explain|about|what is it|tell me more|show more|describe|give details|सारांश|माहिती|स्पष्टीकरण|काय आहे|अधिक सांगा)', user_query, re.I))
    top_circular = None
    context_results = []
    last_circular = None
    if request.last_circular_id:
        last_circular = request.last_circular_id
    elif history:
        for turn in reversed(history):
            if isinstance(turn, dict) and turn.get('role') == 'assistant' and turn.get('circular_metadata'):
                last_circular = turn['circular_metadata'].get('nid')
                break

    if is_latest_query:
        try:
            with open(os.path.join(DATA_DIR, 'circular.json'), 'r', encoding='utf-8') as f:
                all_circulars = json.load(f)
            def parse_date(item):
                date_str = item.get('display_date')
                try:
                    return datetime.strptime(date_str, '%d %B %Y') if date_str else datetime.min
                except Exception:
                    return datetime.min
            all_circulars = sorted(all_circulars, key=parse_date, reverse=True)
            for circ in all_circulars:
                if circ.get('file') or circ.get('url') or circ.get('link'):
                    top_circular = {
                        'nid': circ.get('nid'),
                        'title': circ.get('title'),
                        'text': circ.get('body', ''),
                        'link': circ.get('file') or circ.get('url') or circ.get('link'),
                        'display_date': circ.get('display_date'),
                        'content_type': 'circular',
                        'raw_metadata': circ
                    }
                    break
        except Exception as e:
            print(f"[DEBUG] Latest circular search failed: {e}")
    elif is_followup and last_circular:
        try:
            with open(os.path.join(DATA_DIR, 'circular.json'), 'r', encoding='utf-8') as f:
                all_circulars = json.load(f)
            for circ in all_circulars:
                if str(circ.get('nid')) == str(last_circular):
                    print(f"[DEBUG] Context-following: using last_circular nid={circ.get('nid')}, title={circ.get('title')}")
                    top_circular = {
                        'nid': circ.get('nid'),
                        'title': circ.get('title'),
                        'text': circ.get('body', ''),
                        'link': circ.get('file') or circ.get('url') or circ.get('link'),
                        'display_date': circ.get('display_date'),
                        'content_type': 'circular',
                        'raw_metadata': circ
                    }
                    break
        except Exception as e:
            print(f"[DEBUG] Context-following JSON search failed: {e}")
    else:
        context_results = search_context(normalized_query, top_k=10)
        print(f"\n[DEBUG] Query: {normalized_query}")
        for i, ctx in enumerate(context_results):
            print(f"[DEBUG] Result {i+1}: nid={ctx.get('nid')}, title={ctx.get('title')}, link={ctx.get('link')}")
        def find_best_match(context_results, user_query):
            user_query_lower = user_query.lower()
            for ctx in context_results:
                title = ctx.get('title', '').lower()
                text = ctx.get('text', '').lower()
                if user_query_lower in title or user_query_lower in text:
                    return ctx
            return None
        best_match = find_best_match(context_results, normalized_query)
        if best_match:
            top_circular = best_match
        elif context_results:
            top_circular = context_results[0]
        if (not top_circular or not (normalized_query in (top_circular.get('title', '').lower() + ' ' + top_circular.get('text', '').lower()))):
            try:
                with open(os.path.join(DATA_DIR, 'circular.json'), 'r', encoding='utf-8') as f:
                    all_circulars = json.load(f)
                for circ in all_circulars:
                    title = circ.get('title', '').lower()
                    text = circ.get('body', '').lower() if circ.get('body') else ''
                    if normalized_query in title or normalized_query in text:
                        print(f"[DEBUG] Fallback JSON match: nid={circ.get('nid')}, title={circ.get('title')}, file={circ.get('file')}")
                        top_circular = {
                            'nid': circ.get('nid'),
                            'title': circ.get('title'),
                            'text': circ.get('body', ''),
                            'link': circ.get('file') or circ.get('url') or circ.get('link'),
                            'display_date': circ.get('display_date'),
                            'content_type': 'circular',
                            'raw_metadata': circ
                        }
                        break
            except Exception as e:
                print(f"[DEBUG] Fallback JSON search failed: {e}")

    # Use Gemini for dynamic, context-aware answer if a circular is found
    if top_circular and top_circular.get('link'):
        # Compose a prompt for Gemini
        prompt = f"User question: {user_query}\n\n"
        prompt += f"Relevant circular:\nTitle: {top_circular.get('title', '')}\n"
        if top_circular.get('display_date'):
            prompt += f"Date: {top_circular.get('display_date')}\n"
        prompt += f"PDF Link: {top_circular['link']}\n"
        if top_circular.get('text'):
            prompt += f"Text: {top_circular.get('text', '')[:500]}\n"
        if history:
            prompt += "\nConversation history (for context):\n"
            for turn in history[-6:]:
                role = turn.get('role', 'user')
                content = turn.get('content', '')
                prompt += f"{role.capitalize()}: {content}\n"
        prompt += "\nPlease answer the user's question in a natural, helpful, and concise way, using the circular information above. If the user asks for a link, provide it as [PDF](link)."
        try:
            answer = generate_gemini_response(prompt)
            # Post-process: replace raw link with [PDF](link) if present
            pdf_link = top_circular['link']
            if pdf_link:
                # Remove any malformed or double-encoded links
                import re as _re
                # Replace any [PDF](...) or (https...) or raw links with correct Markdown
                answer = _re.sub(r"\[PDF\]\([^)]*\)", "", answer)  # Remove any existing [PDF](...)
                answer = _re.sub(r"https?://\S+", "[PDF](%s)" % pdf_link, answer)
                # Ensure only one [PDF](...) in the answer
                if f"[PDF]({pdf_link})" not in answer:
                    answer = answer.strip() + f" [PDF]({pdf_link})"
            direct_answer = answer.strip()
        except Exception as e:
            print(f"[DEBUG] Gemini failed: {e}")
            answer = f"Yes, there is a recent circular titled '{top_circular.get('title', 'the requested circular')}'. Here is the link: [PDF]({top_circular['link']})"
            if is_latest_query and top_circular.get('display_date'):
                answer += f" It was published on {top_circular.get('display_date')}."
            direct_answer = answer
    else:
        direct_answer = "Sorry, a PDF link for the relevant circular is not available."
        answer = direct_answer

    return {
        "answer": answer,
        "language": lang,
        "direct_answer": direct_answer,
        "circular_metadata": top_circular,
        "context_results": context_results[:3] if context_results else []
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chatbot_server:app", host="0.0.0.0", port=8000, reload=True) 