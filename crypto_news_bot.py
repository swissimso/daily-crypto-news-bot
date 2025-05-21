import requests
from datetime import datetime
import pytz
import os

def get_crypto_news():
    url = "https://cryptopanic.com/api/v1/posts/?auth_token=" + os.environ["CRYPTOPANIC_TOKEN"] + "&public=true"
    resp = requests.get(url)
    data = resp.json()
    headlines = [f"- {post['title']}" for post in data.get("results", [])[:5]]
    return "\n".join(headlines)

def send_telegram_message(message):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

def main():
    tz = pytz.timezone("Europe/Zurich")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    news = get_crypto_news()
    message = f"📰 *Daily Crypto News* – {now}\n\n{news}"
    send_telegram_message(message)

if __name__ == "__main__":
    main()
