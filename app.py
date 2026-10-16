
import logging
from datetime import datetime, timezone

import streamlit as st
from openai import OpenAI
from supabase import create_client

# --------------------------------------------------
# 1. APP CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="AI Chatbox",
    page_icon="💬",
    layout="wide",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a helpful AI assistant.
Provide accurate, clear, and practical answers.
If you are uncertain, say so rather than inventing facts.
Use Markdown when it improves readability.
"""

DEFAULT_MODEL = "openai/gpt-oss-120b"


# --------------------------------------------------
# 2. LOAD AND VALIDATE SECRETS
# --------------------------------------------------

def load_config():
    """Load required settings from Streamlit Secrets."""

    required = {
        "SUPABASE_URL": st.secrets.get("SUPABASE_URL", ""),
        "SUPABASE_KEY": st.secrets.get("SUPABASE_KEY", ""),
        "GROQ_API_KEY": st.secrets.get("GROQ_API_KEY", ""),
    }

    missing = [
        name
        for name, value in required.items()
        if not isinstance(value, str) or not value.strip()
    ]

    if missing:
        st.error(
            "Missing configuration in Streamlit Secrets: "
            + ", ".join(missing)
        )
        st.info(
            "Open your Streamlit app settings and check the Secrets section."
        )
        st.stop()

    model = str(
        st.secrets.get("GROQ_MODEL", DEFAULT_MODEL)
    ).strip() or DEFAULT_MODEL

    return {
        **required,
        "GROQ_MODEL": model,
    }

# st.write("Secrets diagnostic", {
#     "SUPABASE_URL exists": bool(
#         st.secrets.get("SUPABASE_URL", "")
#     ),
#     "SUPABASE_KEY exists": bool(
#         st.secrets.get("SUPABASE_KEY", "")
#     ),
#     "GROQ_API_KEY exists": bool(
#         st.secrets.get("GROQ_API_KEY", "")
#     ),
#     "GROQ_MODEL exists": bool(
#         st.secrets.get("GROQ_MODEL", "")
#     ),
# })

config = load_config()


# --------------------------------------------------
# 3. INITIALIZE CLIENTS
# --------------------------------------------------

@st.cache_resource
def get_groq_client(api_key):
    """Create a reusable Groq client using the OpenAI SDK."""

    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=60.0,
        max_retries=2,
    )


def get_supabase_client():
    """Create a Supabase client for the current Streamlit session."""

    client = create_client(
        config["SUPABASE_URL"],
        config["SUPABASE_KEY"],
    )

    # Restore the signed-in user's Supabase session after reruns.
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")

    if access_token and refresh_token:
        try:
            client.auth.set_session(
                access_token,
                refresh_token,
            )
        except Exception:
            logger.warning(
                "Could not restore Supabase session.",
                exc_info=True,
            )
            clear_auth_state()

    return client


groq = get_groq_client(config["GROQ_API_KEY"])


# --------------------------------------------------
# 4. SESSION STATE
# --------------------------------------------------

def initialize_state():
    defaults = {
        "access_token": None,
        "refresh_token": None,
        "user_id": None,
        "user_email": None,
        "conversation_id": None,
        "auth_mode": "Login",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_auth_state():
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.user_id = None
    st.session_state.user_email = None
    st.session_state.conversation_id = None


initialize_state()
supabase = get_supabase_client()


def remember_session(session):
    """Save Supabase authentication details in Streamlit session state."""

    st.session_state.access_token = session.access_token
    st.session_state.refresh_token = session.refresh_token
    st.session_state.user_id = session.user.id
    st.session_state.user_email = session.user.email


# --------------------------------------------------
# 5. AUTHENTICATION
# --------------------------------------------------

def render_authentication():
    st.title("💬 AI Chatbox")
    st.write("Sign in or create an account to start chatting.")

    login_tab, signup_tab = st.tabs(["Login", "Create account"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input(
                "Email address",
                key="login_email",
            )
            password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )

            submitted = st.form_submit_button(
                "Log in",
                use_container_width=True,
            )

        if submitted:
            if not email.strip() or not password:
                st.warning("Enter your email address and password.")
            else:
                try:
                    response = supabase.auth.sign_in_with_password(
                        {
                            "email": email.strip(),
                            "password": password,
                        }
                    )

                    if response.user and response.session:
                        remember_session(response.session)
                        st.success("Login successful.")
                        st.rerun()
                    else:
                        st.error("Login did not return a valid session.")

                except Exception as exc:
                    logger.exception("Supabase login failed")
                    st.error("Login failed. Check your credentials.")
                    st.caption(
                        f"Error type: {type(exc).__name__}"
                    )

    with signup_tab:
        with st.form("signup_form"):
            name = st.text_input(
                "Full name",
                key="signup_name",
            )
            email = st.text_input(
                "Email address",
                key="signup_email",
            )
            password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="signup_confirm_password",
            )

            submitted = st.form_submit_button(
                "Create account",
                use_container_width=True,
            )

        if submitted:
            if not name.strip() or not email.strip() or not password:
                st.warning("Complete all required fields.")
            elif password != confirm_password:
                st.warning("Your passwords do not match.")
            elif len(password) < 8:
                st.warning("Use a password with at least 8 characters.")
            else:
                try:
                    response = supabase.auth.sign_up(
                        {
                            "email": email.strip(),
                            "password": password,
                            "options": {
                                "data": {
                                    "full_name": name.strip(),
                                }
                            },
                        }
                    )

                    if response.session and response.user:
                        remember_session(response.session)
                        st.success("Your account has been created.")
                        st.rerun()
                    else:
                        st.success(
                            "Signup submitted. Check your email for "
                            "a confirmation link, then log in here."
                        )

                except Exception as exc:
                    logger.exception("Supabase signup failed")
                    st.error("Signup failed.")
                    st.caption(
                        f"Error type: {type(exc).__name__}"
                    )


# --------------------------------------------------
# 6. DATABASE OPERATIONS
# --------------------------------------------------

def get_conversations():
    """Fetch the signed-in user's conversations."""

    result = (
        supabase.table("conversations")
        .select("*")
        .eq("user_id", st.session_state.user_id)
        .order("created_at", desc=True)
        .execute()
    )

    return result.data or []


def create_conversation(first_message):
    """Create a conversation and return its ID."""

    title = " ".join(first_message.split())[:60]
    if len(first_message) > 60:
        title += "..."

    result = (
        supabase.table("conversations")
        .insert(
            {
                "user_id": st.session_state.user_id,
                "title": title or "New conversation",
            }
        )
        .execute()
    )

    if not result.data:
        raise RuntimeError("The conversation could not be created.")

    return result.data[0]["id"]


def get_messages(conversation_id):
    """Fetch messages belonging to a conversation."""

    result = (
        supabase.table("messages")
        .select("*")
        .eq("user_id", st.session_state.user_id)
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )

    return result.data or []


def save_message(conversation_id, role, content):
    """Save a user or assistant message."""

    supabase.table("messages").insert(
        {
            "user_id": st.session_state.user_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
        }
    ).execute()


def delete_conversation(conversation_id):
    """Delete a conversation owned by the current user."""

    # Delete child messages first if your schema does not use
    # an ON DELETE CASCADE foreign key.
    (
        supabase.table("messages")
        .delete()
        .eq("user_id", st.session_state.user_id)
        .eq("conversation_id", conversation_id)
        .execute()
    )

    (
        supabase.table("conversations")
        .delete()
        .eq("user_id", st.session_state.user_id)
        .eq("id", conversation_id)
        .execute()
    )


# --------------------------------------------------
# 7. GROQ CHAT COMPLETION
# --------------------------------------------------


def generate_ai_response(messages):
    """Generate an answer using Groq, with built-in web search enabled."""

    api_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + """

Web search instructions:
- For questions about current events, today's date or time,
  recent developments, current prices, and other changing facts,
  use the browser search tool when appropriate.
- For questions that require no current information, answer
  directly without unnecessary searching.
- Never claim to have searched the web if you did not.
- When search results provide sources, include relevant source
  links or citations in your answer.
- Distinguish verified information from uncertainty.
""",
        }
    ]

    for message in messages:
        role = message.get("role")
        content = message.get("content")

        if role in ("user", "assistant") and isinstance(content, str):
            api_messages.append({
                "role": role,
                "content": content,
            })

    response = groq.chat.completions.create(
        model=config["GROQ_MODEL"],
        messages=api_messages,
        tools=[
            {"type": "browser_search"}
        ],
        max_tokens=2048,
        temperature=0.7,
    )

    answer = response.choices[0].message.content

    if not answer:
        raise RuntimeError("The AI returned an empty response.")

    return answer


# --------------------------------------------------
# 8. CHAT INTERFACE
# --------------------------------------------------

def render_chat():
    st.title("💬 AI Chatbox")

    with st.sidebar:
        st.write("### Account")
        st.write(st.session_state.user_email or "Signed in")

        if st.button("Log out", use_container_width=True):
            try:
                supabase.auth.sign_out()
            except Exception:
                logger.warning(
                    "Supabase sign-out request failed.",
                    exc_info=True,
                )
            finally:
                clear_auth_state()
            st.rerun()

        st.divider()
        st.write("### Conversations")

        if st.button("＋ New chat", use_container_width=True):
            st.session_state.conversation_id = None
            st.rerun()

        try:
            conversations = get_conversations()
        except Exception as exc:
            logger.exception("Could not load conversations")
            st.error("Could not load conversation history.")
            st.caption(f"Error type: {type(exc).__name__}")
            conversations = []

        for conversation in conversations:
            conversation_id = conversation["id"]
            title = conversation.get("title") or "Untitled conversation"

            is_current = (
                st.session_state.conversation_id == conversation_id
            )

            if st.button(
                ("● " if is_current else "") + title,
                key=f"conversation_{conversation_id}",
                use_container_width=True,
            ):
                st.session_state.conversation_id = conversation_id
                st.rerun()

        st.divider()
        st.caption(f"Model: {config['GROQ_MODEL']}")

    conversation_id = st.session_state.conversation_id

    # Verify the selected conversation belongs to the signed-in user.
    if conversation_id:
        owned_conversation = any(
            item["id"] == conversation_id
            for item in conversations
        )

        if not owned_conversation:
            st.session_state.conversation_id = None
            conversation_id = None

    if conversation_id:
        try:
            history = get_messages(conversation_id)
        except Exception as exc:
            logger.exception("Could not load messages")
            st.error("Could not load this conversation.")
            st.caption(f"Error type: {type(exc).__name__}")
            history = []
    else:
        history = []

    if not history:
        st.markdown("### What would you like help with?")
        st.write(
            "Ask a question, explore an idea, write code, "
            "or work through a problem."
        )

    for message in history:
        role = message.get("role", "assistant")

        if role not in ("user", "assistant"):
            continue

        with st.chat_message(role):
            st.markdown(message.get("content", ""))

    prompt = st.chat_input("Message AI Chatbox...")

    if prompt and prompt.strip():
        prompt = prompt.strip()

        try:
            if not conversation_id:
                conversation_id = create_conversation(prompt)
                st.session_state.conversation_id = conversation_id

            save_message(
                conversation_id,
                "user",
                prompt,
            )

            history.append(
                {
                    "role": "user",
                    "content": prompt,
                }
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    answer = generate_ai_response(history)
                st.markdown(answer)

            save_message(
                conversation_id,
                "assistant",
                answer,
            )

            st.rerun()

        except Exception as exc:
            logger.exception("Chat request failed")
            st.error(
                "The message could not be processed or saved. "
                "Check your database configuration and try again."
            )
            st.caption(f"Error type: {type(exc).__name__}")


# --------------------------------------------------
# 9. MAIN ENTRY POINT
# --------------------------------------------------

def main():
    if not st.session_state.user_id:
        render_authentication()
    else:
        render_chat()


if __name__ == "__main__":
    main()
