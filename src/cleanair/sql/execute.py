"""Execute validated SQL safely (SPEC §8.1 step 4) -- layer 2 of SQL safety, independent of the validator.

- read-only connection: writes fail inside DuckDB
- enable_external_access = false: read_csv('file'), httpfs, ATTACH of other files are refused by the engine
- timeout: a watchdog thread calls connection.interrupt()
- row cap: fetch at most max_rows + 1 and report truncation
"""

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import duckdb


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    seconds: float
    meta: dict = field(default_factory=dict)

    def to_markdown(self, max_rows: int = 50) -> str:
        if not self.columns:
            return "(no columns)"
        out = ["| " + " | ".join(self.columns) + " |", "|" + "---|" * len(self.columns)]
        for r in self.rows[:max_rows]:
            out.append("| " + " | ".join("NULL" if v is None else str(v) for v in r) + " |")
        if len(self.rows) > max_rows or self.truncated:
            out.append(f"... ({len(self.rows)}{'+' if self.truncated else ''} rows total)")
        return "\n".join(out)


def connect_readonly(db_path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=True, config={"enable_external_access": False})


def execute(sql: str, db_path: Path, timeout_s: float = 5.0, max_rows: int = 1000) -> QueryResult:
    con = connect_readonly(db_path)
    timer = threading.Timer(timeout_s, con.interrupt)
    t0 = time.time()
    try:
        timer.start()
        cur = con.execute(sql)
        rows = cur.fetchmany(max_rows + 1)
        columns = [d[0] for d in cur.description] if cur.description else []
    except duckdb.InterruptException as e:
        raise TimeoutError(f"query exceeded {timeout_s}s") from e
    finally:
        timer.cancel()
        con.close()
    return QueryResult(columns, rows[:max_rows], len(rows) > max_rows, round(time.time() - t0, 3))
