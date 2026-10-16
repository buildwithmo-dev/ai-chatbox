
import streamlit as st
from openai import OpenAI, APIError

# -------------------------
# 1. Page configuration
# -------------------------
st.set_page_config(
    page_title="Groq AI Chatbot",
    page_icon="🤖",
    layout="centered",
)

st.title("🤖 Groq AI Chatbot")
st.caption("Groq Responses API · Conversation history · Web search")

# -------------------------
# 2. Configure the client
# -------------------------
try:
    api_key = st.secrets["GROQ_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("GROQ_API_KEY is missing from Streamlit secrets.")
    st.stop()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
)

MODEL = st.secrets.get(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

SYSTEM_PROMPT = """
You are a helpful AI assistant.

Answer clearly and accurately.
Use browser search when current information is needed.
When using web search, identify relevant sources and provide links
when available.
If you are uncertain, say so.
"""

# -------------------------
# 3. Initialize session state
# -------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_response_id" not in st.session_state:
    st.session_state.last_response_id = None

# -------------------------
# 4. Sidebar
# -------------------------
with st.sidebar:
    st.subheader("Chat settings")
    st.caption(f"Model: {MODEL}")

    st.divider()
    st.subheader("Latest response ID")

    response_id = st.session_state.last_response_id

    if response_id:
        st.code(response_id, language=None)
        st.caption(
            "Identifier for the latest successful API response."
        )
    else:
        st.caption("No response has been generated yet.")

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_response_id = None
        st.rerun()

# -------------------------
# 5. Render conversation history
# -------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# -------------------------
# 6. Handle new messages
# -------------------------
if prompt := st.chat_input("Ask me anything..."):

    # Save and display the user's message.
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Groq currently requires us to send the conversation
    # history ourselves; previous_response_id is unsupported.
    api_input = [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in st.session_state.messages
    ]

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                response = client.responses.create(
                    model=MODEL,
                    instructions=SYSTEM_PROMPT,
                    input=api_input,
                    tools=[
                        {"type": "browser_search"}
                    ],
                    max_output_tokens=1024,
                )

                answer = response.output_text

                if not answer:
                    answer = "The model returned no text response."

            st.markdown(answer)

            # Store the assistant's answer in local session history.
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

            # Record the ID returned by the Responses API.
            st.session_state.last_response_id = response.id

        except APIError as error:
            # Remove the failed user turn so it can be retried.
            if (
                st.session_state.messages
                and st.session_state.messages[-1]["role"] == "user"
                and st.session_state.messages[-1]["content"] == prompt
            ):
                st.session_state.messages.pop()

            st.error(
                "The Groq Responses API request failed. "
                "Check your API key, model access, "
                "browser-search support, and rate limits."
            )
            st.caption(str(error))
