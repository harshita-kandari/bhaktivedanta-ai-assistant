from fastapi import APIRouter
from fastapi.responses import Response

from app.services import export

router = APIRouter(prefix="/export", tags=["export"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/calls.xlsx")
def export_calls() -> Response:
    """Download calls, appointments, doctors and patients as one workbook."""
    return Response(
        content=export.workbook_bytes(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="hospital_call_data.xlsx"'},
    )


@router.get("/calls.csv")
def export_calls_csv() -> Response:
    """Public CSV for Google Sheets: =IMPORTDATA("<this url>")."""
    return Response(
        content=export.calls_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'inline; filename="hospital_calls.csv"'},
    )
