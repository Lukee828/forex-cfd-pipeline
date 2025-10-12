from __future__ import annotations
from pathlib import Path
import shutil
import datetime as _dt

try:
    import yaml  # optional
except Exception:
    yaml = None

from alpha_factory.alpha_registry import AlphaRegistry


def _get_db_path(self) -> Path | None:
    for k in ("db_path", "path", "database"):
        p = getattr(self, k, None)
        if isinstance(p, (str, Path)) and str(p):
            return Path(str(p))
    return None


def _load_cfg() -> dict:
    cfg_path = Path("src/alpha_factory/config_registry.yaml")
    if not cfg_path.exists():
        return {}
    text = cfg_path.read_text(encoding="utf-8")
    if yaml:
        try:
            obj = yaml.safe_load(text) or {}
            return obj.get("registry", obj) or {}
        except Exception:
            pass
    # naive parser (fallback)
    out, section = {}, None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.endswith(":") and ":" not in s[:-1]:
            section = s[:-1]
            continue
        if ":" in s:
            k, v = s.split(":", 1)
            k, v = k.strip(), v.strip()
            if v.lower() in ("true", "false"):
                v = v.lower() == "true"
            else:
                try:
                    v = int(v)
                except Exception:
                    v = v.strip().strip("'\"")
            if section == "registry":
                out[k] = v
            else:
                out[k] = v
    return out


def _ensure_schema(self) -> "AlphaRegistry":
    import duckdb

    dbp = _get_db_path(self)
    if dbp and dbp.name != ":memory:":
        dbp.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(dbp) if dbp else ":memory:")
    try:
        con.execute(
            """
        CREATE TABLE IF NOT EXISTS alphas(
          id           BIGINT,
          timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          config_hash  TEXT,
          metrics      JSON,
          tags         TEXT
        );
        """
        )
        con.execute(
            """
        CREATE TABLE IF NOT EXISTS runs_metadata(
          run_id TEXT PRIMARY KEY,
          alpha_id TEXT NOT NULL,
          run_hash TEXT,
          timestamp TIMESTAMP,
          source_version TEXT,
          config_hash TEXT,
          config_diff TEXT,
          tags TEXT,
          notes TEXT
        );
        """
        )
    finally:
        con.close()
    return self


def _backup(
    self, retention_days: int | None = None, backup_dir: str | None = None
) -> str | None:
    cfg = _load_cfg()
    retention_days = (
        retention_days if retention_days is not None else cfg.get("retention_days")
    )
    backup_dir = backup_dir or cfg.get("backup_dir")

    dbp = _get_db_path(self)
    if not dbp or str(dbp) == ":memory:":
        return None
    src = dbp
    out_dir = Path(backup_dir) if backup_dir else (src.parent / "backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}.{ts}{src.suffix or '.duckdb'}"
    shutil.copy2(src, dst)

    if isinstance(retention_days, int) and retention_days > 0:
        cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=int(retention_days))
        for p in out_dir.glob(f"{src.stem}.*{src.suffix or '.duckdb'}"):
            try:
                ts_part = p.name.split(".")[1]
                dt = _dt.datetime.strptime(ts_part, "%Y%m%d_%H%M%S")
                if dt < cutoff:
                    p.unlink(missing_ok=True)
            except Exception:
                pass
    return str(dst)


def _vacuum(self) -> bool:
    import duckdb

    dbp = _get_db_path(self)
    con = duckdb.connect(str(dbp) if dbp else ":memory:")
    try:
        con.execute("VACUUM;")
        return True
    finally:
        con.close()


# patch
AlphaRegistry.ensure_schema = _ensure_schema
AlphaRegistry.backup = _backup
AlphaRegistry.vacuum = _vacuum
