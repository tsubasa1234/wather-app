from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render

API_URL = "https://api.openweathermap.org/data/2.5/forecast"
CACHE_SECONDS = 60 * 10  # 同じ都市は10分間キャッシュ（APIの呼び出し回数を節約）
HOURLY_COUNT = 16  # 3時間 × 16件 = 48時間（今日・明日）

# プリセット都市: 表示名 -> OpenWeatherMapに渡すクエリ
CITIES = {
    "東京": "Tokyo,JP",
    "大阪": "Osaka,JP",
    "名古屋": "Nagoya,JP",
    "札幌": "Sapporo,JP",
    "福岡": "Fukuoka,JP",
    "那覇": "Naha,JP",
}
DEFAULT_CITY = "東京"


class WeatherError(Exception):
    """画面にそのまま表示できるエラーメッセージを持つ例外。"""


def fetch_forecast(query):
    """OpenWeatherMapの/forecastを取得する。同じ都市は一定時間キャッシュする。"""
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        raise WeatherError("APIキーが設定されていません。.env に OPENWEATHER_API_KEY を設定してください")

    cache_key = f"forecast:{query.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {"q": query, "appid": api_key, "units": "metric", "lang": "ja"}
    try:
        res = requests.get(API_URL, params=params, timeout=10)
        data = res.json()
    except (requests.RequestException, ValueError):
        raise WeatherError("天気データを取得できませんでした。時間をおいて再度お試しください")

    if "list" not in data:
        if str(data.get("cod")) == "404":
            raise WeatherError(f"都市「{query}」が見つかりませんでした。ローマ字などで入力してみてください")
        raise WeatherError(data.get("message", "APIキーが無効です。設定を確認してください"))

    cache.set(cache_key, data, CACHE_SECONDS)
    return data


def to_local(item, tz_offset):
    """APIのUNIX時刻を、その都市の現地時間に変換する。"""
    utc = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
    return utc + timedelta(seconds=tz_offset)


def pop_percent(item):
    """降水確率(0〜1)を%に変換する。"""
    return round(item.get("pop", 0) * 100)


def aggregate_daily(items, tz_offset):
    """3時間ごとのデータを日ごとにまとめる。

    最高気温はその日の最大、最低気温はその日の最小、降水確率はその日の最大。
    天気の説明は現地の正午に最も近い時間帯のものを使う。
    """
    by_date = defaultdict(list)
    for item in items:
        by_date[to_local(item, tz_offset).date()].append(item)

    daily = []
    for date, day_items in sorted(by_date.items()):
        noon_item = min(day_items, key=lambda i: abs(to_local(i, tz_offset).hour - 12))
        daily.append({
            "date": date.strftime("%m-%d"),
            "temp_max": round(max(i["main"]["temp_max"] for i in day_items)),
            "temp_min": round(min(i["main"]["temp_min"] for i in day_items)),
            "pop": max(pop_percent(i) for i in day_items),
            "desc": noon_item["weather"][0]["description"],
        })
    return daily


def build_hourly(items, tz_offset, count=HOURLY_COUNT):
    """直近の3時間ごとデータ（気温・降水確率）を作る。"""
    hourly = []
    for item in items[:count]:
        local = to_local(item, tz_offset)
        hourly.append({
            "label": local.strftime("%m/%d %H:00"),
            "temp": round(item["main"]["temp"], 1),
            "pop": pop_percent(item),
            "desc": item["weather"][0]["description"],
        })
    return hourly


def resolve_city(request):
    """リクエストから (表示名, APIクエリ, プリセット選択値) を決める。

    ?q=Kyoto のような自由入力が優先。なければ ?city=大阪 のプリセット。
    """
    free_text = request.GET.get("q", "").strip()
    if free_text:
        return free_text, free_text, ""

    preset = request.GET.get("city", DEFAULT_CITY)
    if preset not in CITIES:
        preset = DEFAULT_CITY
    return preset, CITIES[preset], preset


def index(request):
    label, query, selected = resolve_city(request)
    context = {
        "cities": list(CITIES),
        "selected": selected,
        "q": request.GET.get("q", "").strip(),
        "city_label": label,
    }

    try:
        data = fetch_forecast(query)
    except WeatherError as e:
        context["error"] = str(e)
        return render(request, "weather/index.html", context)

    tz_offset = data.get("city", {}).get("timezone", 0)
    items = data["list"]
    context["forecast"] = aggregate_daily(items, tz_offset)
    context["hourly"] = build_hourly(items, tz_offset)
    # 自由入力のときは、APIが返した正式な都市名を表示する
    if not selected:
        context["city_label"] = data.get("city", {}).get("name") or label
    return render(request, "weather/index.html", context)
