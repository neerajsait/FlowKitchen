"""
backup.py — Automated database backup script for FoodPilot ERP.

Usage:
    python backup.py               # Run backup manually
    python backup.py --schedule    # Run as a cron-style background scheduler

Cron setup (Linux/Mac):
    0 2 * * * /path/to/venv/bin/python /path/to/backend/backup.py >> /var/log/foodpilot_backup.log 2>&1

Windows Task Scheduler:
    Action: python backup.py
    Trigger: Daily at 2:00 AM
"""

import os
import sys
import gzip
import shutil
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("backup")

# ── Config ────────────────────────────────────────────────────────────────────
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./backups"))
KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "30"))  # Auto-delete backups older than N days
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "food")
SQLITE_PATH = os.getenv("SQLITE_PATH", "./food.db")
DB_URL = os.getenv("DATABASE_URL", "")

def _is_mysql():
    """Return True if the active database is MySQL."""
    if DB_URL:
        return "mysql" in DB_URL.lower()
    return bool(MYSQL_HOST and MYSQL_USER and MYSQL_DB)

def backup_mysql():
    """Dump MySQL database to a gzipped .sql file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"{MYSQL_DB}_{timestamp}.sql.gz"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "mysqldump",
        f"--host={MYSQL_HOST}",
        f"--user={MYSQL_USER}",
        f"--password={MYSQL_PASSWORD}",
        "--single-transaction",
        "--routines",
        "--triggers",
        MYSQL_DB,
    ]

    logger.info(f"Starting MySQL backup → {backup_file}")
    with gzip.open(backup_file, "wb") as gz_out:
        result = subprocess.run(cmd, stdout=gz_out, stderr=subprocess.PIPE)

    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")
        logger.error(f"mysqldump failed: {err}")
        backup_file.unlink(missing_ok=True)
        return False

    size_mb = backup_file.stat().st_size / (1024 * 1024)
    logger.info(f"MySQL backup complete: {backup_file} ({size_mb:.2f} MB)")
    return True

def backup_sqlite():
    """Copy SQLite .db file to a timestamped backup."""
    db_path = Path(SQLITE_PATH)
    if not db_path.exists():
        logger.warning(f"SQLite DB not found at {db_path}. Skipping.")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"{db_path.stem}_{timestamp}.db.gz"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting SQLite backup → {backup_file}")
    with open(db_path, "rb") as f_in, gzip.open(backup_file, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    size_mb = backup_file.stat().st_size / (1024 * 1024)
    logger.info(f"SQLite backup complete: {backup_file} ({size_mb:.2f} MB)")
    return True

def cleanup_old_backups():
    """Remove backup files older than KEEP_DAYS days."""
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    removed = 0
    for f in BACKUP_DIR.glob("*.gz"):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            logger.info(f"Removed old backup: {f.name}")
            removed += 1
    if removed:
        logger.info(f"Cleanup: removed {removed} old backup(s) older than {KEEP_DAYS} days.")
    else:
        logger.info("No old backups to clean up.")

def run_backup():
    """Main backup entry point."""
    logger.info("=" * 60)
    logger.info("FoodPilot ERP — Database Backup")
    logger.info("=" * 60)

    ok = backup_mysql() if _is_mysql() else backup_sqlite()
    cleanup_old_backups()

    if ok:
        logger.info("Backup finished successfully.")
        return 0
    else:
        logger.error("Backup FAILED.")
        return 1

if __name__ == "__main__":
    if "--schedule" in sys.argv:
        # APScheduler-based recurring backup (runs process in foreground)
        try:
            from apscheduler.schedulers.blocking import BlockingScheduler
        except ImportError:
            logger.error("apscheduler not installed. Run: pip install apscheduler")
            sys.exit(1)

        sched = BlockingScheduler()
        # Daily at 02:00
        sched.add_job(run_backup, "cron", hour=2, minute=0, id="db_backup")
        logger.info("Backup scheduler started. Daily backups at 02:00.")
        try:
            sched.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")
    else:
        sys.exit(run_backup())
