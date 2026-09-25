"""Fluxo semanal: gravação no Drive -> aula no módulo "Lives Semanais" da Hotmart."""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import drive
import hotmart

STATE_FILE = "processed.json"
TZ = ZoneInfo("America/Sao_Paulo")


def main():
    folder_id = os.environ["DRIVE_FOLDER_ID"]
    name_filter = os.environ.get("MEET_NAME_FILTER", "")
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    with open(STATE_FILE) as f:
        state = json.load(f)
    done = set(state["processed"])

    pending = [r for r in drive.find_recordings(folder_id, name_filter) if r["id"] not in done]
    if not pending:
        print("Nenhuma gravação nova. Nada a fazer.")
        return

    os.makedirs("downloads", exist_ok=True)
    for rec in pending:
        live_date = datetime.fromisoformat(rec["createdTime"].replace("Z", "+00:00")).astimezone(TZ)
        title = f"Live {live_date:%d/%m/%Y}"
        print(f"Gravação: {rec['name']} -> aula '{title}'")

        path = drive.download(rec["id"], os.path.join("downloads", "live.mp4"))
        hotmart.publish_lesson(path, title, dry_run=dry_run)
        os.remove(path)

        if not dry_run:
            state["processed"].append(rec["id"])
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        print(f"OK: {title}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRO: {e}", file=sys.stderr)
        raise
