
import streamlit as st
import requests
import json
import time
import os
import uuid
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base

# Database Configuration
DATABASE_URL = "postgresql://postgres:PAvEcizawOGNeYDbwLSWBzFtWKRSAiSq@postgres.railway.internal:5432/railway"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Model
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True)
    role = Column(String, index=True)
    content = Column(Text)
    timestamp = Column(DateTime, default=func.now())

Base.metadata.create_all(bind=engine)

# Model name
model = "llama3"

# Response generator (mimics streaming)
def response_generator(msg_content):
    lines = msg_content.split('\n')
    for line in lines:
        words = line.split()
        for word in words:
            yield word + " "
            time.sleep(0.1)
        yield "\n"

# Show chat messages
def show_msgs():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# Chat function with LLaMA3
def chat(messages):
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        )
        response.raise_for_status()
        output = ""
        for line in response.iter_lines():
            body = json.loads(line)
            if "error" in body:
                raise Exception(body["error"])
            if body.get("done", False):
                return {"role": "assistant", "content": output}
            output += body.get("message", {}).get("content", "")
    except Exception as e:
        return {"role": "assistant", "content": str(e)}

# Save message to DB
def save_message(session_id, role, content):
    db = SessionLocal()
    new_message = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(new_message)
    db.commit()
    db.close()

# Load previous chat sessions
def load_saved_chats():
    db = SessionLocal()
    sessions = db.query(ChatMessage.session_id).distinct().all()
    db.close()
    
    for session in sessions:
        session_id = session[0]
        if st.sidebar.button(f"Session: {session_id[:8]}..."):
            load_chat_from_db(session_id)

# Load chat messages from DB
def load_chat_from_db(session_id):
    st.session_state["messages"] = []
    db = SessionLocal()
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp).all()
    db.close()

    for message in messages:
        st.session_state.messages.append({"role": message.role, "content": message.content})

# Format chat log for download
def format_chatlog(chatlog):
    return "\n".join(f"{msg['role']}: {msg['content']}" for msg in chatlog)

# Streamlit UI
def main():
    st.title("LLaMA Chat with Database")
    
    # Initialize session state variables
    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = str(uuid.uuid4())
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []
    
    # Show messages
    show_msgs()

    # User input
    user_input = st.chat_input("Enter your prompt:")
    if user_input:
        session_id = st.session_state["session_id"]
        
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        save_message(session_id, "user", user_input)
        
        response = chat([{"role": "user", "content": user_input}])
        st.session_state.messages.append(response)
        save_message(session_id, "assistant", response["content"])
        
        with st.chat_message("assistant"):
            st.write_stream(response_generator(response["content"]))    

    # Chat log download
    chatlog = format_chatlog(st.session_state['messages'])
    st.sidebar.download_button(
        label="Download Chat Log",
        data=chatlog,
        file_name="chat_log.txt",
        mime="text/plain"
    )

    # Load previous chats
    if st.sidebar.checkbox("Show/hide chat history"):
        st.sidebar.title("Previous Chats")
        load_saved_chats()

if __name__ == "__main__":
    main()
