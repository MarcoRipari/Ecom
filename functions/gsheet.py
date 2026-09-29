import streamlit as st
import os
from google.oauth2 import service_account
import gspread
from gspread_formatting import CellFormat, NumberFormat, format_cell_ranges
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.http import MediaInMemoryUpload
from gspread.utils import rowcol_to_a1
from gspread_formatting import CellFormat, NumberFormat, format_cell_ranges
import gspread.utils
from googleapiclient.discovery import build
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# ---------------------------
# 📊 Google Sheets Client Helper
# ---------------------------
_credentials = None
gsheet_client = None
drive_service = None

def get_gsheet_client():
    global _credentials, gsheet_client, drive_service
    if gsheet_client is not None:
        return gsheet_client, drive_service

    gcp_sa = None
    try:
        gcp_sa = st.secrets.get("GCP_SERVICE_ACCOUNT")
    except Exception:
        pass

    if gcp_sa:
        try:
            _credentials = service_account.Credentials.from_service_account_info(
                gcp_sa,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
            )
            gsheet_client = gspread.authorize(_credentials)
            drive_service = build('drive', 'v3', credentials=_credentials)
        except Exception:
            gsheet_client = None
            drive_service = None

    return gsheet_client, drive_service

def get_sheet(sheet_id, tab):
    client, _ = get_gsheet_client()
    if not client:
        raise ValueError("Google Sheets credentials non configurate nei secrets.")
    spreadsheet = client.open_by_key(sheet_id)
    worksheets = spreadsheet.worksheets()

    for ws in worksheets:
        if ws.title.strip().lower() == tab.strip().lower():
            return ws

    return spreadsheet.add_worksheet(title=tab, rows="10000", cols="50")

def append_to_sheet(sheet_id, tab, df):
    sheet = get_sheet(sheet_id, tab)
    df = df.fillna("").astype(str)
    values = df.values.tolist()

    existing_rows = len(sheet.get_all_values())
    start_row = existing_rows + 1 if existing_rows > 0 else 1
    target_cell = f"A{start_row}"
    sheet.update(target_cell, values, value_input_option="RAW")

def append_log(sheet_id, logs):
    sheet = get_sheet(sheet_id, "logs")
    rows_to_append = []
    for log in logs:
        rows_to_append.append([
            log.get("sku", ""),
            log.get("status", ""),
            log.get("prompt", ""),
            log.get("output", ""),
            log.get("timestamp", ""),
            log.get("prompt_tokens", 0),
            log.get("completion_tokens", 0),
            log.get("total_tokens", 0),
            log.get("estimated_cost_usd", 0)
        ])

    sheet.append_rows(rows_to_append)
