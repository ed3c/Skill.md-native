import hashlib
import json
import sys
from pathlib import Path


if "--version" in sys.argv:
    print("fixture-agent 1.0.0")
    raise SystemExit(0)


task = sys.stdin.read()
Path("target.txt").write_text("done\n", encoding="utf-8")
print(
    json.dumps(
        {
            "type": "task.completed",
            "status": "ok",
            "task_digest": hashlib.sha256(task.encode("utf-8")).hexdigest(),
        },
        sort_keys=True,
    )
)
