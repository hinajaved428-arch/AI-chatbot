import logging
import os
import uuid

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

from config import SYSTEM_PROMPT

# Read the settings from the .env file
load_dotenv()

API_KEY = os.getenv("API_KEY", "").strip()
API_URL = os.getenv(
    "API_URL", "https://api.groq.com/openai/v1/chat/completions"
).strip()
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-120b").strip()

MAX_MESSAGE_LENGTH = 2000      # longest message the user may send
MAX_HISTORY_MESSAGES = 12      # how many past messages we send to the AI (6 pairs)
REQUEST_TIMEOUT = 45           # seconds to wait for the AI

# Show helpful messages in the terminal (the API key is never printed)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("chatbot")

app = Flask(__name__)
# Used to sign the browser cookie. A random value is fine for local use.
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)

# Conversation history lives here, on the server, one list per browser session.
# Note: it is cleared when you stop the server.
conversations = {}


class AIServiceError(Exception):
    """An error with a friendly message that is safe to show the user."""

    def __init__(self, user_message, http_status=502):
        super().__init__(user_message)
        self.user_message = user_message
        self.http_status = http_status


def get_session_id():
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def call_ai(messages):
    """Send the messages to the AI API and return the reply text."""
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        logger.error("API_KEY is missing. Add it to the .env file and restart.")
        raise AIServiceError(
            "The API key is missing. Please add it to the .env file and restart the server.",
            500,
        )

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7,
        "max_completion_tokens": 2048,
    }

    try:
        response = requests.post(
            API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.Timeout:
        logger.error("The AI service timed out after %s seconds.", REQUEST_TIMEOUT)
        raise AIServiceError(
            "The AI service took too long to respond. Please try again.", 504
        )
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to %s (check your internet).", API_URL)
        raise AIServiceError(
            "Sorry, I couldn't connect to the AI service. Please check your internet connection and API configuration, then try again.",
            502,
        )
    except requests.exceptions.RequestException as error:
        logger.error("Request failed: %s", type(error).__name__)
        raise AIServiceError(
            "Sorry, something went wrong while contacting the AI service.", 502
        )

    status = response.status_code
    if status != 200:
        # Log the provider's explanation so you can debug (it never contains your key)
        logger.error("AI API returned status %s: %s", status, response.text[:500])
        if status in (401, 403):
            raise AIServiceError(
                "The API key looks invalid or not allowed. Please check the key in your .env file.",
                502,
            )
        if status == 429:
            raise AIServiceError(
                "Too many requests right now (free-tier limit). Please wait a minute and try again.",
                429,
            )
        if status in (400, 404):
            raise AIServiceError(
                "The AI service rejected the request. The model name or API URL in .env may be wrong or outdated.",
                502,
            )
        raise AIServiceError(
            "The AI service had a problem. Please try again in a moment.", 502
        )

    try:
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        logger.error("Unexpected response format: %s", response.text[:500])
        raise AIServiceError(
            "The AI service sent an unexpected response. Please try again.", 502
        )

    if not reply or not reply.strip():
        logger.error("The AI returned an empty reply.")
        raise AIServiceError(
            "The AI returned an empty answer. Please try asking again.", 502
        )

    return reply.strip()


@app.route("/")
def index():
    return render_template("index.html", max_length=MAX_MESSAGE_LENGTH)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid request."), 400

    message = data.get("message")
    if not isinstance(message, str):
        return jsonify(error="Invalid request."), 400

    message = message.strip()
    if not message:
        return jsonify(error="Please enter a message."), 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return (
            jsonify(
                error=f"Your message is too long. Please keep it under {MAX_MESSAGE_LENGTH} characters."
            ),
            400,
        )

    sid = get_session_id()
    history = conversations.get(sid, [])

    # System prompt first, then recent history, then the new question
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + history[-MAX_HISTORY_MESSAGES:]
        + [{"role": "user", "content": message}]
    )

    try:
        reply = call_ai(messages)
    except AIServiceError as error:
        return jsonify(error=error.user_message), error.http_status
    except Exception:
        logger.exception("Unexpected server error")
        return jsonify(error="Something went wrong on the server."), 500

    # Save to history only after a successful answer
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    conversations[sid] = history[-MAX_HISTORY_MESSAGES:]

    return jsonify(reply=reply)


@app.route("/api/history", methods=["GET"])
def get_history():
    sid = get_session_id()
    return jsonify(messages=conversations.get(sid, []))


@app.route("/api/clear", methods=["POST"])
def clear():
    conversations.pop(get_session_id(), None)
    return jsonify(ok=True)


if __name__ == "__main__":
    logger.info("Using model: %s", MODEL_NAME)
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        logger.warning("API_KEY is not set. Chat will not work until you add it to .env")
    app.run(debug=True)
