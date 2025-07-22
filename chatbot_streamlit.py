import streamlit as st
import requests

st.set_page_config(page_title="PMC Chatbot", page_icon="🤖")
st.title("PMC AI-Powered Chatbot")
st.markdown("""
Ask your questions about the PMC website in English or Marathi. The bot will answer in the same language and provide links if available.
""")

API_URL = "http://localhost:8000/chat"

if 'history' not in st.session_state:
    st.session_state['history'] = []
if 'last_circular_id' not in st.session_state:
    st.session_state['last_circular_id'] = None
if 'last_circular_metadata' not in st.session_state:
    st.session_state['last_circular_metadata'] = None

with st.form(key='chat_form'):
    user_query = st.text_area("Your question:", height=80)
    submit = st.form_submit_button("Ask")

if submit and user_query.strip():
    with st.spinner("Thinking..."):
        try:
            # Prepare conversation history for backend (user/bot turns)
            history_payload = []
            for q, a, lang, direct_answer, circular_metadata in st.session_state['history']:
                history_payload.append({"role": "user", "content": q})
                history_payload.append({"role": "assistant", "content": a})
            payload = {"query": user_query.strip(), "history": history_payload}
            if st.session_state['last_circular_id']:
                payload["last_circular_id"] = st.session_state['last_circular_id']
            response = requests.post(API_URL, json=payload)
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                lang = data.get('language', 'en')
                direct_answer = data.get('direct_answer', None)
                circular_metadata = data.get('circular_metadata', None)
                # Store last matched circular for follow-up context
                if circular_metadata and circular_metadata.get('nid'):
                    st.session_state['last_circular_id'] = circular_metadata['nid']
                    st.session_state['last_circular_metadata'] = circular_metadata
                st.session_state['history'].append((user_query, answer, lang, direct_answer, circular_metadata))
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"Failed to connect to backend: {e}")

# Remove 'You', 'Direct Answer', and 'PDF' from conversation history, only show 'Bot' answer
st.markdown("---")
st.subheader("Conversation History")
for i, (q, a, lang, direct_answer, circular_metadata) in enumerate(reversed(st.session_state['history'])):
    st.markdown(f"**Bot:** {a}")
    st.markdown("---") 