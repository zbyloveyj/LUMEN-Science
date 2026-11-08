import csv
import json
import sqlite3
import sys
from pathlib import Path

script = Path(sys.argv[1])
root = Path.cwd()
output = root / "outputs" / ("sql-" + script.parent.name)
output.mkdir(parents=True, exist_ok=True)
database = root / ".lumen" / "analysis.sqlite3"
database.parent.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(database)
db.execute("PRAGMA busy_timeout=5000")
buffer = ""
index = 0
try:
    for character in script.read_text(encoding="utf-8-sig"):
        buffer += character
        if character == ";" and sqlite3.complete_statement(buffer):
            cursor = db.execute(buffer)
            if cursor.description:
                index += 1
                columns = [c[0] for c in cursor.description]
                values = cursor.fetchmany(100001)
                if len(values) > 100000:
                    raise ValueError("SQL 查询结果超过100,000行，请使用 LIMIT")
                with (output / ("query-" + str(index) + ".csv")).open("w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f); writer.writerow(columns); writer.writerows(values)
                print(json.dumps({"columns": columns, "rows": values[:60], "total": len(values)}, ensure_ascii=False))
            buffer = ""
    if buffer.strip() and not buffer.strip().startswith("--"):
        raise ValueError("SQL 语句需要以分号结束")
    db.commit()
    print("数据库：" + str(database))
finally:
    db.close()
