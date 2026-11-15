/**
 * Bhakti — Google Sheets live sync.
 *
 * Setup:
 *   1. Create a Google Sheet.
 *   2. Extensions -> Apps Script.
 *   3. Replace the code with this file.
 *   4. Run refreshCalls once and allow access.
 *   5. Triggers (clock icon) -> Add Trigger:
 *        function: refreshCalls
 *        event source: Time-driven
 *        type: Minutes timer
 *        interval: Every minute
 *
 * The "Calls" sheet is rewritten on every run, so new calls appear within a
 * minute. Keep the ngrok tunnel and the server running, or the fetch fails and
 * the sheet keeps its last good copy.
 */

const CSV_URL =
  "https://either-craftwork-hedging.ngrok-free.dev/api/v1/export/calls.csv";

function refreshCalls() {
  const response = UrlFetchApp.fetch(CSV_URL, {
    // ngrok shows a browser warning page without this header.
    headers: { "ngrok-skip-browser-warning": "true" },
    muteHttpExceptions: true,
  });

  if (response.getResponseCode() !== 200) {
    console.log("Fetch failed: " + response.getResponseCode());
    return;
  }

  const rows = Utilities.parseCsv(response.getContentText());
  if (!rows.length) return;

  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName("Calls") || spreadsheet.insertSheet("Calls");

  sheet.clearContents();
  sheet.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
  sheet.setFrozenRows(1);
}
