from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from activity_report import ActivityReport, load_activity_report

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "title": "Home"}
    )


@app.get("/report", response_class=HTMLResponse)
async def report(request: Request, file: UploadFile | None = None):
    activity_report: ActivityReport | None = None

    if file and file.filename is not None:
        activity_report = load_activity_report(file.filename)

    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "title": "Portfolio Performance",
            "activity_report": activity_report,
        },
    )
