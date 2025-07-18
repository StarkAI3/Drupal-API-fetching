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

with st.form(key='chat_form'):
    user_query = st.text_area("Your question:", height=80)
    submit = st.form_submit_button("Ask")

if submit and user_query.strip():
    with st.spinner("Thinking..."):
        try:
            response = requests.post(API_URL, json={"query": user_query.strip()})
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                lang = data.get('language', 'en')
                direct_circular = data.get('direct_circular', None)
                st.session_state['history'].append((user_query, answer, lang, direct_circular))
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"Failed to connect to backend: {e}")

st.markdown("---")
st.subheader("Conversation History")
for i, (q, a, lang, direct_circular) in enumerate(reversed(st.session_state['history'])):
    st.markdown(f"**You ({'Marathi' if lang == 'mr' else 'English'}):** {q}")
    if direct_circular:
        st.markdown(f"**Direct Circular Match:**\n{direct_circular}")
    st.markdown(f"**Bot:** {a}")
    st.markdown("---") 