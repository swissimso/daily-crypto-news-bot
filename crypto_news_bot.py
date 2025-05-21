import requests
from datetime import datetime
import pytz
import os
import openai

def fetch_trending_coins():
    url = "https://api.coingecko.com/api/v3/search/trending"
    resp = requests.get(url)
    coins = resp.json().get("coins", [])
    return [coin["item"]["name"] for coin in coins]

def fetch_fear_and_greed():
    url = "https://api.alternative.me/fng/?limit=1&format=json"
    resp = requests.get(url)
    data = resp.json()
    index = data.get("data", [{}])[0]
    return f"{index.get('value_classification')} ({index.get('value')})"

def summon_openai_summary(trending, fear_greed):
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = (
        f"Summarize the current crypto market in a brief daily update. "
        f"The Fear and Greed index is {fear_greed}. "
        f"Trending coins are: {', '.join(trending)}. "
        f"Respond in an informative, professional tone."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )

    return response.choices[0].message.content.strip()


def send_telegram_message(message):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def main():
    tz = pytz.timezone("Europe/Zurich")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    trending = fetch_trending_coins()
    fear_greed = fetch_fear_and_greed()
    summary = summon_openai_summary(trending, fear_greed)
    message = f"📰 *Daily Crypto Summary* – {now}\n\n{summary}"
    send_telegram_message(message)

if __name__ == "__main__":
    main()
