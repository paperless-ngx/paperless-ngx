"""Lightweight detection to decide if we should boot migration mode."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

_DOC_EXISTS_QUERY = "SELECT 1 FROM documents_document LIMIT 1;"


def _get_db_config() -> dict[str, Any]:
    data_dir = Path(os.getenv("PAPERLESS_DATA_DIR", BASE_DIR.parent / "data")).resolve()
    if not os.getenv("PAPERLESS_DBHOST"):
        return {
            "ENGINE": "sqlite",
            "NAME": data_dir / "db.sqlite3",
        }

    engine = "mariadb" if os.getenv("PAPERLESS_DBENGINE") == "mariadb" else "postgres"
    cfg = {
        "ENGINE": engine,
        "HOST": os.getenv("PAPERLESS_DBHOST"),
        "PORT": os.getenv("PAPERLESS_DBPORT"),
        "NAME": os.getenv("PAPERLESS_DBNAME", "paperless"),
        "USER": os.getenv("PAPERLESS_DBUSER", "paperless"),
        "PASSWORD": os.getenv("PAPERLESS_DBPASS", "paperless"),
    }
    return cfg


def _probe_sqlite(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        conn = sqlite3.connect(path, timeout=1)
        cur = conn.cursor()
        cur.execute(_DOC_EXISTS_QUERY)
        cur.fetchone()
        return True
    except sqlite3.Error:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _probe_postgres(cfg: dict[str, Any]) -> bool:
    try:
        import psycopg
    except ImportError:  # pragma: no cover
        logger.debug("psycopg not installed; skipping postgres probe")
        return False

    try:
        conn = psycopg.connect(
            host=cfg["HOST"],
            port=cfg["PORT"],
            dbname=cfg["NAME"],
            user=cfg["USER"],
            password=cfg["PASSWORD"],
            connect_timeout=2,
        )
        with conn, conn.cursor() as cur:
            cur.execute(_DOC_EXISTS_QUERY)
            cur.fetchone()
        return True
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _probe_mariadb(cfg: dict[str, Any]) -> bool:
    try:
        import MySQLdb  # type: ignore
    except ImportError:  # pragma: no cover
        logger.debug("mysqlclient not installed; skipping mariadb probe")
        return False

    try:
        conn = MySQLdb.connect(
            host=cfg["HOST"],
            port=int(cfg["PORT"] or 3306),
            user=cfg["USER"],
            passwd=cfg["PASSWORD"],
            db=cfg["NAME"],
            connect_timeout=2,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM documents_document LIMIT 1;")
        cur.fetchone()
        return True
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def is_v2_database() -> bool:
    cfg = _get_db_config()
    if cfg["ENGINE"] == "sqlite":
        return _probe_sqlite(cfg["NAME"])
    if cfg["ENGINE"] == "postgres":
        return _probe_postgres(cfg)
    if cfg["ENGINE"] == "mariadb":
        return _probe_mariadb(cfg)
    return False


def choose_settings_module() -> str:
    # ENV override
    toggle = os.getenv("PAPERLESS_MIGRATION_MODE")
    if toggle is not None:
        chosen = (
            "paperless_migration.settings"
            if str(toggle).lower() in ("1", "true", "yes", "on")
            else "paperless.settings"
        )
        os.environ["PAPERLESS_MIGRATION_MODE"] = "1" if "migration" in chosen else "0"
        return chosen

    # Auto-detect via DB probe
    if is_v2_database():
        logger.warning("Detected v2 schema; booting migration mode.")
        os.environ["PAPERLESS_MIGRATION_MODE"] = "1"
        return "paperless_migration.settings"

    os.environ["PAPERLESS_MIGRATION_MODE"] = "0"
    return "paperless.settings"


if __name__ == "__main__":  # pragma: no cover
    logger.info(
        "v2 database detected" if is_v2_database() else "v2 database not detected",
    )
