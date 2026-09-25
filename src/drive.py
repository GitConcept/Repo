"""Busca e baixa a gravação da live no Google Drive (via conta de serviço)."""
import io
import json
import os
from datetime import datetime, timedelta, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _service():
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def find_recordings(folder_id: str, name_filter: str, days_back: int = 7):
    """Lista vídeos da pasta criados nos últimos `days_back` dias, do mais antigo ao mais novo."""
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
    q = [
        f"'{folder_id}' in parents",
        "(mimeType contains 'video/' or mimeType = 'application/vnd.google-apps.shortcut')",
        "trashed = false",
        f"createdTime > '{since}'",
    ]
    if name_filter:
        safe = name_filter.replace("\\", "\\\\").replace("'", "\\'")
        q.append(f"name contains '{safe}'")
    resp = _service().files().list(
        q=" and ".join(q),
        fields="files(id, name, createdTime, size, mimeType, shortcutDetails)",
        orderBy="createdTime",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = []
    for f in resp.get("files", []):
        if f["mimeType"] == "application/vnd.google-apps.shortcut":
            # Atalho: usa o vídeo original (o robô precisa ter acesso a ele também).
            target = f.get("shortcutDetails", {})
            if not target.get("targetMimeType", "").startswith("video/"):
                continue
            f["id"] = target["targetId"]
        files.append(f)
    return files


def download(file_id: str, dest_path: str):
    request = _service().files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.FileIO(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=64 * 1024 * 1024)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  download {int(status.progress() * 100)}%")
    return dest_path
