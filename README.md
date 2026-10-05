# AI Learning Assistant

A beginner-friendly AI chatbot built with Python, Flask, HTML, CSS and JavaScript.
It uses the Groq API (free tier, no credit card).

## Get a free API key
1. Go to https://console.groq.com and sign up.
2. Open https://console.groq.com/keys and click "Create API Key".
3. Copy the key (starts with gsk_). It is shown only once.

## Run it (Windows PowerShell)
```powershell
cd ai-chatbot
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env        # replace YOUR_API_KEY_HERE with your real key, save
python app.py
```
Open http://127.0.0.1:5000 in your browser. Press Ctrl+C in the terminal to stop.

If activation is blocked by PowerShell:
- `Set-ExecutionPolicy -Scope Process Bypass` (temporary, this window only), then activate again, or
- `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or
- use `venv\Scripts\activate.bat` in Command Prompt.

## Change AI provider later
Edit API_KEY, API_URL and MODEL_NAME in `.env`. Any OpenAI-style /chat/completions API works.

## Troubleshooting
Read the messages in the terminal where `python app.py` is running. They show the real reason
(401 = bad key, 404/400 = wrong model or URL, 429 = rate limit) without printing your key.
