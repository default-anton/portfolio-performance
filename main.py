import locale
from datetime import date

from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import jinja_filters
from activity_report import ActivityReport, load_activity_report
from bank_of_canada import get_cadx_rate
from middlewares.csrf_middleware import CSRFMiddleware

locale.setlocale(locale.LC_ALL, "en_CA.UTF-8")

app = FastAPI()
app.add_middleware(CSRFMiddleware)
app.add_middleware(GZipMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")
templates.env.filters["currency"] = jinja_filters.currency


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request},
    )


@app.post("/report", response_class=HTMLResponse)
def create_report(request: Request, file: UploadFile | None = None):
    activity_report: ActivityReport | None = None

    if file is None:
        return HTMLResponse(
            content="No file was uploaded.",
            headers={"HX-Retarget": "#form .error", "HX-Reswap": "innerHTML"},
        )

    accepted_file_types = (
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if file.content_type not in accepted_file_types:
        return HTMLResponse(
            content=f"File type {file.content_type} is not supported.",
            headers={"HX-Retarget": "#form .error", "HX-Reswap": "innerHTML"},
        )

    try:
        activity_report = load_activity_report(file.file.read())
    except Exception as e:
        return HTMLResponse(
            content=f"Error loading activity report: {e}",
            headers={"HX-Retarget": "#form .error", "HX-Reswap": "innerHTML"},
        )

    activity_report.save()

    boc_usdcad = get_cadx_rate(date.today())

    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "activity_report": activity_report,
            "boc_usdcad": boc_usdcad,
        },
        headers={"HX-Push-URL": f"/report/{activity_report.id}"},
    )


@app.get("/report/{id}", response_class=HTMLResponse)
def get_report(request: Request, id: str):
    try:
        activity_report = ActivityReport.load(id)
    except (OSError, ValueError):
        return HTMLResponse(
            content="Report not found.",
            status_code=404,
        )

    boc_usdcad = get_cadx_rate(date.today())

    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "activity_report": activity_report,
            "boc_usdcad": boc_usdcad,
        },
    )
