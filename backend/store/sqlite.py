"""Persistencia en SQLite: investigaciones, eventos, propuestas y métricas.

Usamos el módulo `sqlite3` de la librería estándar, sin ORM: son cuatro tablas
y consultas sencillas. Las operaciones tardan microsegundos, así que se llaman
directamente desde el código asíncrono sin pasar por un hilo aparte.

Guardar los eventos permite reproducir una investigación ya terminada (por
ejemplo, si el navegador se conecta tarde o recarga la página).
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.contracts import MetricsTotals, Proposal, TaskMetric
from router import summarize

RunStatus = Literal["running", "finished", "error"]
RunMode = Literal["real", "demo"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    topic       TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    seq     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  TEXT NOT NULL REFERENCES runs(id),
    data    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_by_run ON events(run_id, seq);
CREATE TABLE IF NOT EXISTS proposals (
    id         TEXT PRIMARY KEY,
    run_id     TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data       TEXT NOT NULL,
    file_path  TEXT
);
CREATE TABLE IF NOT EXISTS task_metrics (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL,
    data              TEXT NOT NULL,
    baseline_cost_usd REAL NOT NULL
);
"""


@dataclass(frozen=True)
class RunRecord:
    id: str
    topic: str
    status: RunStatus
    created_at: str
    finished_at: str | None
    client_ip: str | None = None
    mode: RunMode = "real"


class Store:
    def __init__(self, path: Path | str = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI puede ejecutar código de arranque en otro hilo.
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Añade columnas nuevas a bases de datos creadas con una versión anterior.

        CREATE TABLE IF NOT EXISTS no modifica tablas que ya existen, así que las
        columnas añadidas después se crean aquí si faltan.
        """
        columns = {row["name"] for row in self._db.execute("PRAGMA table_info(runs)")}
        with self._db:
            if "client_ip" not in columns:
                self._db.execute("ALTER TABLE runs ADD COLUMN client_ip TEXT")
            if "mode" not in columns:
                self._db.execute("ALTER TABLE runs ADD COLUMN mode TEXT NOT NULL DEFAULT 'real'")

    def close(self) -> None:
        self._db.close()

    # --- Investigaciones -------------------------------------------------------

    def create_run(
        self, run_id: str, topic: str, client_ip: str | None = None, mode: RunMode = "real"
    ) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO runs (id, topic, status, created_at, client_ip, mode) "
                "VALUES (?, ?, 'running', ?, ?, ?)",
                (run_id, topic, now(), client_ip, mode),
            )

    def count_runs_today(self, mode: RunMode = "real", client_ip: str | None = None) -> int:
        """Investigaciones de hoy (día UTC), en total o de una IP. Para el cupo diario."""
        today = datetime.now(UTC).date().isoformat()
        query = "SELECT COUNT(*) FROM runs WHERE mode = ? AND substr(created_at, 1, 10) = ?"
        params: tuple = (mode, today)
        if client_ip is not None:
            query += " AND client_ip = ?"
            params += (client_ip,)
        return self._db.execute(query, params).fetchone()[0]

    def finish_run(self, run_id: str, status: RunStatus) -> None:
        with self._db:
            self._db.execute(
                "UPDATE runs SET status = ?, finished_at = ? WHERE id = ?",
                (status, now(), run_id),
            )

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return RunRecord(**dict(row)) if row else None

    # --- Eventos ---------------------------------------------------------------

    def add_event(self, run_id: str, event_json: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO events (run_id, data) VALUES (?, ?)", (run_id, event_json)
            )

    def list_events(self, run_id: str) -> list[dict]:
        rows = self._db.execute(
            "SELECT data FROM events WHERE run_id = ? ORDER BY seq", (run_id,)
        ).fetchall()
        return [json.loads(row["data"]) for row in rows]

    # --- Propuestas ------------------------------------------------------------

    def save_proposal(self, proposal: Proposal) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO proposals (id, run_id, status, created_at, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    proposal.id,
                    proposal.run_id,
                    proposal.status,
                    proposal.created_at.isoformat(),
                    proposal.model_dump_json(),
                ),
            )

    def delete_pending_demo_proposals(self) -> int:
        """Borra las propuestas pendientes de investigaciones de demo.

        Cada demo propone las mismas 3 notas: sin esto se acumularían duplicadas en
        la lista de revisión. Las aprobadas o rechazadas no se tocan.
        """
        with self._db:
            cursor = self._db.execute(
                "DELETE FROM proposals WHERE status = 'pending' AND run_id IN "
                "(SELECT id FROM runs WHERE mode = 'demo')"
            )
        return cursor.rowcount

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        row = self._db.execute(
            "SELECT data, status FROM proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        return self._to_proposal(row) if row else None

    def list_proposals(self, status: str | None = None) -> list[Proposal]:
        query = "SELECT data, status FROM proposals"
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        rows = self._db.execute(query + " ORDER BY created_at DESC, id", params).fetchall()
        return [self._to_proposal(row) for row in rows]

    def set_proposal_status(
        self, proposal_id: str, status: str, file_path: str | None = None
    ) -> Proposal | None:
        with self._db:
            self._db.execute(
                "UPDATE proposals SET status = ?, file_path = COALESCE(?, file_path) WHERE id = ?",
                (status, file_path, proposal_id),
            )
        return self.get_proposal(proposal_id)

    @staticmethod
    def _to_proposal(row: sqlite3.Row) -> Proposal:
        # El estado vive en su propia columna (se actualiza sin reescribir el JSON).
        return Proposal.model_validate_json(row["data"]).model_copy(
            update={"status": row["status"]}
        )

    # --- Métricas --------------------------------------------------------------

    def add_metric(self, metric: TaskMetric, baseline_cost_usd: float) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO task_metrics (run_id, data, baseline_cost_usd) VALUES (?, ?, ?)",
                (metric.run_id, metric.model_dump_json(), baseline_cost_usd),
            )

    def metrics(self, run_id: str | None = None) -> tuple[list[TaskMetric], MetricsTotals]:
        query = "SELECT data, baseline_cost_usd FROM task_metrics"
        params: tuple = ()
        if run_id is not None:
            query += " WHERE run_id = ?"
            params = (run_id,)
        rows = self._db.execute(query + " ORDER BY id", params).fetchall()
        records = [TaskMetric.model_validate_json(row["data"]) for row in rows]
        return records, summarize(records, [row["baseline_cost_usd"] for row in rows])


def now() -> str:
    return datetime.now(UTC).isoformat()
