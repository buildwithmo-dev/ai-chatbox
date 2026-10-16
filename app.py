
import streamlit as st
from groq import Groq, APIError

# -------------------------
# 1. Page configuration
# -------------------------
st.set_page_config(
    page_title="Groq AI Chatbot",
    page_icon="🤖",
    layout="centered",
)

st.title("🤖 Groq AI Chatbot")
st.caption("A conversational AI assistant powered by Groq")

# -------------------------
# 2. Configure the LLM
# -------------------------
try:
    client = Groq(
        api_key=st.secrets["GROQ_API_KEY"]
    )
except (KeyError, FileNotFoundError):
    st.error(
        "Groq API key is missing. "
        "Configure GROQ_API_KEY in your Streamlit secrets."
    )
    st.stop()

# Keep the model configurable without editing Python code.
MODEL = st.secrets.get(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

SYSTEM_PROMPT = """
You are a helpful AI assistant.
Answer clearly, accurately, and concisely.
If you are unsure about a fact, say so.
"""

# -------------------------
# 3. Initialize chat state
# -------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# -------------------------
# 4. Sidebar controls
# -------------------------
with st.sidebar:
    st.subheader("Chat settings")
    st.write(f"Model: `{MODEL}`")

    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()

    st.caption("Start a new conversation at any time.")

# -------------------------
# 5. Render chat history
# -------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# -------------------------
# 6. Handle user input
# -------------------------
if prompt := st.chat_input("Ask me anything..."):

    # Display and save the user's message
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Construct the context sent to the model
    api_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *st.session_state.messages,
    ]

    # Ask Groq for a response
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=api_messages,
                    temperature=0.7,
                    max_completion_tokens=1024,
                )

                answer = response.choices[0].message.content

                if not answer:
                    answer = "The model returned an empty response."

            st.markdown(answer)

            # Save only a successful assistant response
            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )

        except APIError as error:
            st.error(
                "The Groq API request failed. "
                "Check your model ID, API key, "
                "rate limits, and account access."
            )
            st.caption(f"API error: {error}")
