import requests
from datetime import datetime
import pytz
import os

def get_crypto_news():
    url = "https://api.coingecko.com/api/v3/status_updates"
    resp = requests.get(url)
    print(f"Status Code: {resp.status_code}")
    print(f"Response Snippet: {resp.text[:200]}")

    data = resp.json()
    updates = data.get("status_updates", [])[:5]

    if not updates:
        return "No recent crypto news found."

    headlines = []
    for update in updates:
        project = update.get("project", {}).get("name", "Unknown Project")
        title = update.get("title", "").strip()
        description = update.get("description", "").strip()
        headlines.append(f"🔹 *{project}* – {title}\n{description}")

    return "\n\n".join(headlines)

def send_telegram_message(message):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

def main():
    tz = pytz.timezone("Europe/Zurich")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    news = get_crypto_news()
    message = f"📰 *Daily Crypto News* – {now}\n\n{news}"
    send_telegram_message(message)

if __name__ == "__main__":
    main()
