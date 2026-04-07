import logging
import os
import time
from datetime import datetime

import pytz
import requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 10          # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = 2             # seconds between retries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_env(name: str) -> str:
    """Return the value of a required environment variable or raise clearly."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set.")
    return value


def _get_with_retry(url: str, **kwargs) -> requests.Response:
    """GET *url* with timeout and simple exponential back-off on failure."""
    if MAX_RETRIES < 1:
        raise ValueError(f"MAX_RETRIES must be >= 1, got {MAX_RETRIES}")
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("GET %s failed (attempt %d/%d): %s", url, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
    raise last_exc  # type: ignore[misc]  # last_exc is always set (MAX_RETRIES >= 1)


# ---------------------------------------------------------------------------
# Data-fetching functions
# ---------------------------------------------------------------------------
def fetch_trending_coins() -> list[str]:
    """Return names of trending coins from CoinGecko."""
    url = "https://api.coingecko.com/api/v3/search/trending"
    try:
        resp = _get_with_retry(url)
        coins = resp.json().get("coins", [])
        names = [coin["item"]["name"] for coin in coins if "item" in coin]
        logger.info("Fetched %d trending coins.", len(names))
        return names
    except Exception as exc:
        logger.error("Could not fetch trending coins: %s", exc)
        raise


def fetch_fear_and_greed() -> str:
    """Return a human-readable Fear & Greed string, e.g. 'Greed (72)'."""
    url = "https://api.alternative.me/fng/?limit=1&format=json"
    try:
        resp = _get_with_retry(url)
        index = resp.json().get("data", [{}])[0]
        classification = index.get("value_classification", "Unknown")
        value = index.get("value", "N/A")
        result = f"{classification} ({value})"
        logger.info("Fear & Greed index: %s", result)
        return result
    except Exception as exc:
        logger.error("Could not fetch Fear & Greed index: %s", exc)
        raise


# ---------------------------------------------------------------------------
# OpenAI summary
# ---------------------------------------------------------------------------
def generate_summary(trending: list[str], fear_greed: str) -> str:
    """Ask OpenAI to produce a short daily crypto summary."""
    client = OpenAI(api_key=_get_env("OPENAI_API_KEY"))

    prompt = (
        "Summarize the current crypto market in a brief daily update. "
        f"The Fear and Greed index is {fear_greed}. "
        f"Trending coins are: {', '.join(trending)}. "
        "Respond in an informative, professional tone."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        summary = response.choices[0].message.content.strip()
        logger.info("OpenAI summary generated successfully.")
        return summary
    except Exception as exc:
        logger.error("OpenAI API error: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Telegram delivery
# ---------------------------------------------------------------------------
def send_telegram_message(message: str) -> None:
    """Send *message* to the configured Telegram chat and verify delivery."""
    token = _get_env("TELEGRAM_TOKEN")
    chat_id = _get_env("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API returned ok=false: {result}")
        logger.info("Telegram message sent (message_id=%s).", result["result"]["message_id"])
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    tz = pytz.timezone("Europe/Zurich")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    trending = fetch_trending_coins()
    fear_greed = fetch_fear_and_greed()
    summary = generate_summary(trending, fear_greed)

    message = f"📰 *Daily Crypto Summary* – {now}\n\n{summary}"
    send_telegram_message(message)
    logger.info("Daily crypto summary dispatched successfully.")


if __name__ == "__main__":
    main()
