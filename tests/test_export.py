from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook


def test_export_returns_workbook(client: TestClient) -> None:
    response = client.get("/api/v1/export/calls.xlsx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml"
    )

    workbook = load_workbook(BytesIO(response.content))
    assert {"Summary", "Calls", "Appointments", "Doctors", "Patients"} <= set(
        workbook.sheetnames
    )
    assert workbook["Doctors"].max_row >= 2
