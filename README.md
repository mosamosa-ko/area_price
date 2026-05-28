# area_price

住所または緯度経度から周辺の地価情報を確認する FastAPI アプリケーションです。国土交通省の不動産情報ライブラリを利用し、周辺価格の一覧、平均価格、最寄り地点、簡易な価格推移を表示します。

## Features

- 住所検索
- 緯度経度での直接検索
- 周辺地価の一覧表示
- 最寄り地点と平均価格の表示
- 年別の簡易価格推移
- APIキー未設定時のデモモード

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`:

```env
MLIT_API_KEY=your_api_key
NOMINATIM_USER_AGENT=area-price-mvp/1.0 (contact: your-email@example.com)
DEMO_MODE=true
```

## Local Development

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Deploy

This project is prepared for Vercel deployment.

- Entry point: `index.py`
- Static assets: `public/static/`
- Config: `vercel.json`

For production, set these environment variables in Vercel:

- `MLIT_API_KEY`
- `NOMINATIM_USER_AGENT`
- `DEMO_MODE`
