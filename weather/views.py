import requests
from django.shortcuts import render
from django.conf import settings


def index(request):
    api_key = settings.OPENWEATHER_API_KEY
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": "Tokyo", "appid": api_key, "units": "metric", "lang": "ja", "cnt": 40}

    res = requests.get(url, params=params)
    data = res.json()

    if "list" not in data:
        error = data.get("message", "APIキーを .env に設定してください")
        return render(request, "weather/index.html", {"error": error})

    # 1日1件（正午付近）に絞る
    forecast = []
    seen_dates = set()
    for item in data["list"]:
        date = item["dt_txt"].split(" ")[0]
        if date not in seen_dates:
            seen_dates.add(date)
            forecast.append({
                "date": date[5:],  # MM-DD
                "temp_max": round(item["main"]["temp_max"]),
                "temp_min": round(item["main"]["temp_min"]),
                "desc": item["weather"][0]["description"],
            })
        if len(forecast) == 7:
            break

    return render(request, "weather/index.html", {"forecast": forecast})
