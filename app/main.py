from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models.schemas import SearchRequest, SearchResponse
from app.services.land_price import LandPriceService


BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="Area Price Finder",
    description="住所または緯度経度から周辺の地価情報を取得するMVP",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "public" / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/search", response_model=SearchResponse)
async def search_prices(payload: SearchRequest) -> SearchResponse:
    service = LandPriceService()
    try:
        return await service.search(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
