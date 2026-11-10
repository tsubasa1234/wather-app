# 天気予報Webアプリ

> 🌤️ **概要**
>
> OpenWeatherMap APIを使って、都市ごとの5日間の天気・気温・降水確率をグラフで表示するWebアプリです。

## 機能

- **都市の選択**: プルダウンのプリセット（東京・大阪・名古屋・札幌・福岡・那覇）と、都市名の自由入力に対応
- **5日間の予報**: 日ごとの最高・最低気温（折れ線）と降水確率（棒）を1つのグラフに重ねて表示
- **3時間ごとの予報**: 今日・明日の気温と降水確率を、3時間刻みのグラフで表示
- **エラー表示**: 存在しない都市、APIキーの未設定・無効、通信失敗をそれぞれ画面に表示

## 画面

![画面イメージ](docs/screenshot.png)

## 技術・実装

**使用技術：** Python / Django / OpenWeatherMap API / Chart.js / Render

**工夫した点：**

- 3時間ごとのデータを**日ごとに集計**（最高気温は日の最大、最低気温は最小、降水確率は最大）
- 日付の区切りを**都市の現地時間**で判定（APIの `timezone` を使い、UTCとのずれで日付がずれないようにした）
- 同じ都市の結果を**10分間キャッシュ**し、APIの呼び出し回数を節約
- ユーザー入力（都市名）は `json_script` とテンプレートのエスケープで安全に埋め込み
- `.env` を `.gitignore` に入れ、APIキーをリポジトリに含めない
- `ALLOWED_HOSTS` の空白を `.strip()` で除去し、環境変数の入力ミスに対応
- Renderの無料枠でのデプロイ・運用
- 集計処理と画面のテストを `unittest`（APIはモック）で作成

## ファイル構成

```
weather_app/
├── config/
│   ├── settings.py     # 環境変数読み込み、WhiteNoise設定
│   └── urls.py
├── weather/
│   ├── views.py        # API取得・日別集計・都市の切り替え・キャッシュ
│   ├── tests.py        # 集計処理と画面のテスト
│   └── urls.py
├── templates/weather/
│   └── index.html      # フォーム + 5日間グラフ + 3時間ごとグラフ + 表
├── requirements.txt
├── build.sh            # Renderビルドスクリプト
└── .env                # APIキー（Gitに含まない）
```

## 仕組み

> 💡 DjangoのビューでOpenWeatherMapの `/forecast` エンドポイントを叩き、5日分のデータ（3時間ごと40件）を取得します。
>
> そのデータを「日ごとの集計」と「3時間ごとの系列」の2通りに整形してテンプレートに渡し、Chart.jsで気温の折れ線と降水確率の棒グラフとして描画しています。

```python
# 日ごとにまとめる（現地時間で日付を判定）
by_date = defaultdict(list)
for item in items:
    by_date[to_local(item, tz_offset).date()].append(item)

for date, day_items in sorted(by_date.items()):
    daily.append({
        "date": date.strftime("%m-%d"),
        "temp_max": round(max(i["main"]["temp_max"] for i in day_items)),
        "temp_min": round(min(i["main"]["temp_min"] for i in day_items)),
        "pop": max(pop_percent(i) for i in day_items),
        ...
    })
```

### URLの使い方

| URL | 内容 |
| --- | --- |
| `/` | 東京の予報 |
| `/?city=大阪` | プリセット都市の予報 |
| `/?q=Kyoto` | 都市名を自由入力（プリセットより優先） |

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

## テスト

```bash
python manage.py test weather
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
| `ALLOWED_HOSTS` | `wather-app-1.onrender.com` |

## リンク

- URL: https://wather-app-1.onrender.com/ （Renderの無料枠のため、初回アクセスは表示まで30秒ほどかかります）
- ソースコード: https://github.com/tsubasa1234/wather-app
