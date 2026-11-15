/**
 * Bhakti — Google Sheets sync for all datasets.
 *
 * Writes four tabs in one run: Calls, Appointments, Doctors, Patients.
 *
 * Setup:
 *   1. Create a Google Sheet.
 *   2. Extensions -> Apps Script, replace the code with this file.
 *   3. Run refreshAll once, allow access.
 *   4. Triggers (clock icon) -> Add Trigger:
 *        refreshAll / Time-driven / Minutes timer / Every minute
 *
 * Optional instant push (seconds instead of a minute):
 *   5. Deploy -> New deployment -> Web app
 *        Execute as: Me
 *        Who has access: Anyone
 *      Copy the web app URL and set it on the server:
 *        SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
 *      The server calls it after every call webhook; doPost runs refreshAll.
 */

const DATA_URL =
  "https://either-craftwork-hedging.ngrok-free.dev/api/v1/export/sheets.json";

function writeTab(spreadsheet, name, table) {
  const sheet = spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
  const values = [table.headers].concat(table.rows);
  sheet.clearContents();
  sheet.getRange(1, 1, values.length, table.headers.length).setValues(values);
  sheet.setFrozenRows(1);
}

function refreshAll() {
  const response = UrlFetchApp.fetch(DATA_URL, {
    // ngrok shows a browser warning page without this header.
    headers: { "ngrok-skip-browser-warning": "true" },
    muteHttpExceptions: true,
  });

  if (response.getResponseCode() !== 200) {
    console.log("Fetch failed: " + response.getResponseCode());
    return;
  }

  const data = JSON.parse(response.getContentText());
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  writeTab(spreadsheet, "Calls", data.calls);
  writeTab(spreadsheet, "Appointments", data.appointments);
  writeTab(spreadsheet, "Doctors", data.doctors);
  writeTab(spreadsheet, "Patients", data.patients);
}

function doPost() {
  refreshAll();
  return ContentService.createTextOutput(JSON.stringify({ ok: true })).setMimeType(
    ContentService.MimeType.JSON
  );
}
