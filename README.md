# 天気予報Webアプリ

>  **概要**
>
> OpenWeatherMap APIを使って、東京の5日間の天気と気温をグラフで表示するWebアプリです。


## 技術・実装

**使用技術：** Python / Django / OpenWeatherMap API / Chart.js / Render

**工夫した点：**

- Renderの無料枠でのデプロイ・運用
- `.env` を `.gitignore` に入れ、APIキーをリポジトリに含めない
- APIキーが未設定・無効のときはエラーメッセージを表示するようにした
- `ALLOWED_HOSTS` の空白を `.strip()` で除去し、環境変数の入力ミスに対応できるようにした

## ファイル構成

```
weather_app/
├── config/
│   ├── settings.py     # 環境変数読み込み、WhiteNoise設定
│   └── urls.py
├── weather/
│   ├── views.py        # API取得・データ整形
│   └── urls.py
├── templates/weather/
│   └── index.html      # グラフ + 表
├── requirements.txt
├── build.sh            # Renderビルドスクリプト
└── .env                # APIキー（Gitに含まない）
```

## 仕組み

>  DjangoのビューでOpenWeatherMapの `/forecast` エンドポイントを叩き、5日分のデータ（3時間ごと40件）から1日1件に絞り込みます。
>
> 最高・最低気温と天気説明をテンプレートに渡し、Chart.jsでラインチャートとして描画しています。

```python
res = requests.get(url, params={"q": "tokyo", "appid": api_key, "units": "metric"})
data = res.json()

# 1日1件に絞る
seen_dates = set()
for item in data["list"]:
    date = item["dt_txt"].split(" ")[0]
    if date not in seen_dates:
        seen_dates.add(date)
        forecast.append(
            {
                "date": date[5:],
                "temp_max": round(item["main"]["temp_max"]),
                "temp_min": round(item["main"]["temp_min"]),
                "desc": item["weather"][0]["description"],
            }
        )
```

## ローカルでの実行

```bash
pip install -r requirements.txt
```

プロジェクト直下に `.env` を作成します。

```
SECRET_KEY=your-secret-key
OPENWEATHER_API_KEY=your-api-key
DEBUG=True
```

```bash
python manage.py runserver
```

## Renderデプロイ設定

| 項目 | 値 |
| --- | --- |
| Build Command | `./build.sh` |
| Start Command | `gunicorn config.wsgi:application` |

## 環境変数

| Key | 内容 |
| --- | --- |
| `SECRET_KEY` | Djangoのシークレットキー |
| `OPENWEATHER_API_KEY` | OpenWeatherMapのAPIキー |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `weather-app-1.onrender.com` |

## リンク

- URL: https://weather-app-1.onrender.com/
- ソースコード: https://github.com/tsubasa1234/weather-app
