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

    urls = hotmart.module_urls()

    def key(rec_id, url):
        # Uma entrada por gravação + módulo: se um curso falhar, o outro não é repetido.
        return f"{rec_id}|{url}"

    pending = [
        r for r in drive.find_recordings(folder_id, name_filter, days_back=14)
        if any(key(r["id"], u) not in done for u in urls)
    ]
    if not pending:
        print("Nenhuma gravação nova. Nada a fazer.")
        # Diagnóstico: o que o robô enxerga na pasta, sem o filtro de nome.
        visiveis = drive.find_recordings(folder_id, "", days_back=30)
        print(f"Vídeos dos últimos 30 dias visíveis na pasta: {len(visiveis)}")
        for r in visiveis[-10:]:
            print(f"  - {r['name']} ({r['createdTime']})")
        return

    os.makedirs("downloads", exist_ok=True)
    for rec in pending:
        live_date = datetime.fromisoformat(rec["createdTime"].replace("Z", "+00:00")).astimezone(TZ)
        title = f"LIVE | DIA {live_date:%d/%m/%Y}"
        print(f"Gravação: {rec['name']} -> aula '{title}'")

        targets = [(key(rec["id"], u), u) for u in urls if key(rec["id"], u) not in done]

        def mark_done(k):
            state["processed"].append(k)
            done.add(k)
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)

        path = drive.download(rec["id"], os.path.join("downloads", "live.mp4"))
        hotmart.publish_lesson(path, title, targets, dry_run=dry_run, on_done=mark_done)
        os.remove(path)
        print(f"OK: {title} ({len(targets)} curso(s))")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRO: {e}", file=sys.stderr)
        raise
