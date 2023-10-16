from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from middlewares.csrf_middleware import CSRFMiddleware
from activity_report import ActivityReport, load_activity_report

app = FastAPI()
app.add_middleware(CSRFMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")


templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Upload Your Questrade Activity Report"},
    )


@app.post("/report", response_class=HTMLResponse)
def report(request: Request, file: UploadFile | None = None):
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

    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "title": "Portfolio Performance",
            "activity_report": activity_report,
        },
        headers={"HX-Push-URL": "/report"},
    )
