from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from . import views

JST = 9 * 3600


def make_item(dt, temp, temp_min, temp_max, pop, desc="晴天"):
    return {
        "dt": dt,
        "main": {"temp": temp, "temp_min": temp_min, "temp_max": temp_max},
        "pop": pop,
        "weather": [{"description": desc}],
    }


# 基準時刻: 2026-11-10 00:00 JST (= 2026-11-09 15:00 UTC)。ここから3時間刻みのダミーデータを作る
BASE = int(datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc).timestamp())


def sample_items():
    items = []
    temps = [8, 7, 9, 12, 14, 13, 10, 9, 8, 7, 9, 13, 15, 14, 11, 10]
    for i, t in enumerate(temps):
        items.append(make_item(BASE + i * 3 * 3600, t, t - 1, t + 1, 0.1 * (i % 5)))
    return items


class AggregateDailyTests(SimpleTestCase):
    def test_max_min_are_taken_across_the_whole_day(self):
        daily = views.aggregate_daily(sample_items(), JST)
        first = daily[0]
        # 1日目(00:00〜21:00 JST)の気温は 8,7,9,12,14,13,10,9
        self.assertEqual(first["date"], "11-10")
        self.assertEqual(first["temp_max"], 15)  # 最大は 14+1
        self.assertEqual(first["temp_min"], 6)  # 最小は 7-1
        self.assertGreater(first["temp_max"], first["temp_min"])

    def test_pop_is_daily_maximum_in_percent(self):
        daily = views.aggregate_daily(sample_items(), JST)
        self.assertEqual(daily[0]["pop"], 40)

    def test_dates_use_the_city_timezone_not_utc(self):
        # UTC基準だと 11-09 の15:00 だが、JSTでは 11-10 の 00:00
        daily = views.aggregate_daily([make_item(BASE, 8, 7, 9, 0)], JST)
        self.assertEqual(daily[0]["date"], "11-10")
        daily_utc = views.aggregate_daily([make_item(BASE, 8, 7, 9, 0)], 0)
        self.assertEqual(daily_utc[0]["date"], "11-09")

    def test_description_comes_from_the_item_closest_to_noon(self):
        items = [
            make_item(BASE + 0 * 3 * 3600, 8, 7, 9, 0, desc="夜の雲"),  # 00:00
            make_item(BASE + 4 * 3 * 3600, 14, 13, 15, 0, desc="昼の晴れ"),  # 12:00
        ]
        self.assertEqual(views.aggregate_daily(items, JST)[0]["desc"], "昼の晴れ")


class BuildHourlyTests(SimpleTestCase):
    def test_limits_the_number_of_points_and_formats_labels(self):
        hourly = views.build_hourly(sample_items(), JST, count=4)
        self.assertEqual(len(hourly), 4)
        self.assertEqual(hourly[0]["label"], "11/10 00:00")
        self.assertEqual(hourly[1]["label"], "11/10 03:00")


@override_settings(OPENWEATHER_API_KEY="test-key")
class IndexViewTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def api_response(self, payload):
        res = MagicMock()
        res.json.return_value = payload
        return res

    def ok_payload(self, name="Tokyo"):
        return {"cod": "200", "list": sample_items(), "city": {"name": name, "timezone": JST}}

    @patch("weather.views.requests.get")
    def test_default_city_is_tokyo(self, mock_get):
        mock_get.return_value = self.api_response(self.ok_payload())
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(mock_get.call_args.kwargs["params"]["q"], "Tokyo,JP")
        self.assertContains(res, "東京の天気予報")
        self.assertContains(res, "降水確率")

    @patch("weather.views.requests.get")
    def test_preset_city_is_passed_to_the_api(self, mock_get):
        mock_get.return_value = self.api_response(self.ok_payload("Osaka"))
        self.client.get("/", {"city": "大阪"})
        self.assertEqual(mock_get.call_args.kwargs["params"]["q"], "Osaka,JP")

    @patch("weather.views.requests.get")
    def test_free_text_takes_priority_over_preset(self, mock_get):
        mock_get.return_value = self.api_response(self.ok_payload("Kyoto"))
        res = self.client.get("/", {"city": "大阪", "q": "Kyoto"})
        self.assertEqual(mock_get.call_args.kwargs["params"]["q"], "Kyoto")
        self.assertContains(res, "Kyotoの天気予報")

    @patch("weather.views.requests.get")
    def test_unknown_preset_falls_back_to_default(self, mock_get):
        mock_get.return_value = self.api_response(self.ok_payload())
        self.client.get("/", {"city": "存在しない"})
        self.assertEqual(mock_get.call_args.kwargs["params"]["q"], "Tokyo,JP")

    @patch("weather.views.requests.get")
    def test_unknown_city_shows_error(self, mock_get):
        mock_get.return_value = self.api_response({"cod": "404", "message": "city not found"})
        res = self.client.get("/", {"q": "zzzzzz"})
        self.assertContains(res, "見つかりませんでした")
        self.assertNotContains(res, "hourlyChart")

    @patch("weather.views.requests.get")
    def test_invalid_api_key_shows_error(self, mock_get):
        mock_get.return_value = self.api_response({"cod": 401, "message": "Invalid API key"})
        res = self.client.get("/")
        self.assertContains(res, "Invalid API key")

    @patch("weather.views.requests.get", side_effect=requests.ConnectionError)
    def test_network_failure_shows_error(self, _mock_get):
        res = self.client.get("/")
        self.assertContains(res, "取得できませんでした")

    @override_settings(OPENWEATHER_API_KEY="")
    def test_missing_api_key_shows_error(self):
        res = self.client.get("/")
        self.assertContains(res, "APIキーが設定されていません")

    @patch("weather.views.requests.get")
    def test_same_city_is_cached(self, mock_get):
        mock_get.return_value = self.api_response(self.ok_payload())
        self.client.get("/")
        self.client.get("/")
        self.assertEqual(mock_get.call_count, 1)

    @patch("weather.views.requests.get")
    def test_user_input_is_escaped_in_the_page(self, mock_get):
        mock_get.return_value = self.api_response({"cod": "404", "message": "city not found"})
        res = self.client.get("/", {"q": "<script>alert(1)</script>"})
        self.assertNotContains(res, "<script>alert(1)</script>")
