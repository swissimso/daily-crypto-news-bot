"""Unit tests for crypto_news_bot.py — all external calls are mocked."""
import os
import unittest
from unittest.mock import MagicMock, patch

import requests

import crypto_news_bot as bot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _env_without(*names):
    """Return os.environ minus the specified variable names."""
    return {k: v for k, v in os.environ.items() if k not in names}


# ---------------------------------------------------------------------------
# _get_env
# ---------------------------------------------------------------------------
class TestGetEnv(unittest.TestCase):
    def test_returns_value_when_set(self):
        with patch.dict(os.environ, {"MY_VAR": "hello"}):
            self.assertEqual(bot._get_env("MY_VAR"), "hello")

    def test_raises_when_missing(self):
        with patch.dict(os.environ, _env_without("MISSING_VAR"), clear=True):
            with self.assertRaises(EnvironmentError):
                bot._get_env("MISSING_VAR")

    def test_raises_when_empty_string(self):
        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            with self.assertRaises(EnvironmentError):
                bot._get_env("EMPTY_VAR")


# ---------------------------------------------------------------------------
# _get_with_retry
# ---------------------------------------------------------------------------
class TestGetWithRetry(unittest.TestCase):
    def _ok_response(self, json_data):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 200
        resp.json.return_value = json_data
        resp.raise_for_status.return_value = None
        return resp

    @patch("crypto_news_bot.requests.get")
    def test_returns_on_first_success(self, mock_get):
        mock_get.return_value = self._ok_response({"ok": True})
        resp = bot._get_with_retry("https://example.com")
        mock_get.assert_called_once()
        self.assertEqual(resp.json(), {"ok": True})

    @patch("crypto_news_bot.time.sleep")
    @patch("crypto_news_bot.requests.get")
    def test_retries_on_failure_then_succeeds(self, mock_get, mock_sleep):
        fail = MagicMock(spec=requests.Response)
        fail.raise_for_status.side_effect = requests.HTTPError("500")
        ok = self._ok_response({"coins": []})
        mock_get.side_effect = [fail, ok]
        resp = bot._get_with_retry("https://example.com")
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(resp.json(), {"coins": []})

    @patch("crypto_news_bot.time.sleep")
    @patch("crypto_news_bot.requests.get")
    def test_raises_after_max_retries(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.ConnectionError("down")
        with self.assertRaises(requests.ConnectionError):
            bot._get_with_retry("https://example.com")
        self.assertEqual(mock_get.call_count, bot.MAX_RETRIES)


# ---------------------------------------------------------------------------
# fetch_trending_coins
# ---------------------------------------------------------------------------
class TestFetchTrendingCoins(unittest.TestCase):
    @patch("crypto_news_bot._get_with_retry")
    def test_returns_coin_names(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "coins": [
                {"item": {"name": "Bitcoin"}},
                {"item": {"name": "Ethereum"}},
            ]
        }
        mock_get.return_value = mock_resp
        result = bot.fetch_trending_coins()
        self.assertEqual(result, ["Bitcoin", "Ethereum"])

    @patch("crypto_news_bot._get_with_retry")
    def test_returns_empty_list_when_no_coins(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"coins": []}
        mock_get.return_value = mock_resp
        self.assertEqual(bot.fetch_trending_coins(), [])

    @patch("crypto_news_bot._get_with_retry")
    def test_raises_on_api_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("down")
        with self.assertRaises(requests.ConnectionError):
            bot.fetch_trending_coins()


# ---------------------------------------------------------------------------
# fetch_fear_and_greed
# ---------------------------------------------------------------------------
class TestFetchFearAndGreed(unittest.TestCase):
    @patch("crypto_news_bot._get_with_retry")
    def test_formats_correctly(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"value": "72", "value_classification": "Greed"}]
        }
        mock_get.return_value = mock_resp
        self.assertEqual(bot.fetch_fear_and_greed(), "Greed (72)")

    @patch("crypto_news_bot._get_with_retry")
    def test_handles_missing_data_gracefully(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{}]}
        mock_get.return_value = mock_resp
        result = bot.fetch_fear_and_greed()
        self.assertIn("Unknown", result)
        self.assertIn("N/A", result)

    @patch("crypto_news_bot._get_with_retry")
    def test_raises_on_api_error(self, mock_get):
        mock_get.side_effect = requests.Timeout("timeout")
        with self.assertRaises(requests.Timeout):
            bot.fetch_fear_and_greed()


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------
class TestGenerateSummary(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("crypto_news_bot.OpenAI")
    def test_returns_stripped_summary(self, mock_openai_cls):
        choice = MagicMock()
        choice.message.content = "  Market looks bullish.  "
        mock_openai_cls.return_value.chat.completions.create.return_value.choices = [choice]
        result = bot.generate_summary(["Bitcoin", "Ethereum"], "Greed (72)")
        self.assertEqual(result, "Market looks bullish.")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("crypto_news_bot.OpenAI")
    def test_raises_on_openai_error(self, mock_openai_cls):
        mock_openai_cls.return_value.chat.completions.create.side_effect = Exception("API down")
        with self.assertRaises(Exception):
            bot.generate_summary(["Bitcoin"], "Fear (20)")


# ---------------------------------------------------------------------------
# send_telegram_message
# ---------------------------------------------------------------------------
class TestSendTelegramMessage(unittest.TestCase):
    @patch.dict(os.environ, {"TELEGRAM_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"})
    @patch("crypto_news_bot.requests.post")
    def test_sends_and_validates_ok_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 42}}
        mock_post.return_value = mock_resp
        bot.send_telegram_message("Hello!")  # should not raise

    @patch.dict(os.environ, {"TELEGRAM_TOKEN": "tok", "TELEGRAM_CHAT_ID": "123"})
    @patch("crypto_news_bot.requests.post")
    def test_raises_when_telegram_returns_ok_false(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": False, "description": "Unauthorized"}
        mock_post.return_value = mock_resp
        with self.assertRaises(RuntimeError):
            bot.send_telegram_message("Hello!")

    def test_raises_when_token_missing(self):
        with patch.dict(os.environ, _env_without("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"), clear=True):
            with self.assertRaises(EnvironmentError):
                bot.send_telegram_message("Hello!")


if __name__ == "__main__":
    unittest.main()
