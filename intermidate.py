import streamlit as st
import requests
import json
import time
import os
import uuid
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base

# Configurations
DATABASE_URL = "postgresql://postgres:PAvEcizawOGNeYDbwLSWBzFtWKRSAiSq@postgres.railway.internal:5432/railway"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama.railway.internal:11434")
MODEL_NAME = "llama3"

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True)
    role = Column(String, index=True)
    content = Column(Text)
    timestamp = Column(DateTime, default=func.now())

Base.metadata.create_all(bind=engine)

def save_message(session_id, role, content):
    db = SessionLocal()
    db.add(ChatMessage(session_id=session_id, role=role, content=content))
    db.commit()
    db.close()

def load_saved_chats():
    db = SessionLocal()
    sessions = db.query(ChatMessage.session_id).distinct().all()
    db.close()
    for session in sessions:
        session_id = session[0]
        if st.sidebar.button(f"Session: {session_id[:8]}..."):
            load_chat_from_db(session_id)

def load_chat_from_db(session_id):
    st.session_state["messages"] = []
    db = SessionLocal()
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp).all()
    db.close()
    for message in messages:
        st.session_state.messages.append({"role": message.role, "content": message.content})

def preload_model():
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL_NAME, "prompt": "Hello"},
            timeout=10
        )
        r.raise_for_status()
    except Exception as e:
        st.sidebar.error(f"Model load failed: {e}")

def generate_response(messages):
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": MODEL_NAME, "messages": messages, "stream": True},
            stream=True
        )
        output = ""
        for line in response.iter_lines():
            if line:
                body = json.loads(line)
                if "error" in body:
                    raise Exception(body["error"])
                delta = body.get("message", {}).get("content", "")
                output += delta
                yield delta
    except Exception as e:
        yield str(e)

def format_chatlog(chatlog):
    return "\n".join(f"{msg['role']}: {msg['content']}" for msg in chatlog)

def show_msgs():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

def main():
    st.set_page_config(page_title="LLaMA 3 Chat (Railway)", page_icon="🦙")
    st.title("🦙 LLaMA 3 Chat with DB (Railway)")

    preload_model()

    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = str(uuid.uuid4())
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []

    show_msgs()

    user_input = st.chat_input("Type your message:")
    if user_input:
        session_id = st.session_state["session_id"]
        st.session_state.messages.append({"role": "user", "content": user_input})
        save_message(session_id, "user", user_input)
        
        with st.chat_message("user"):
            st.write(user_input)
        
        with st.chat_message("assistant"):
            full_response = ""
            response_placeholder = st.empty()
            for chunk in generate_response(st.session_state.messages):
                full_response += chunk
                response_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            save_message(session_id, "assistant", full_response)

    chatlog = format_chatlog(st.session_state['messages'])
    st.sidebar.download_button("📥 Download Chat Log", chatlog, "chat_log.txt", "text/plain")

    if st.sidebar.checkbox("🕓 Show chat history"):
        st.sidebar.title("Past Sessions")
        load_saved_chats()

if __name__ == "__main__":
    main()
