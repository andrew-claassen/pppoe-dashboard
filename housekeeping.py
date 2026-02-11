import sqlite3
import logging
from datetime import datetime, timedelta
import os
import threading
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE = "/opt/online/db/subscribers.db"

def get_db():
    db_dir = os.path.dirname(DATABASE)
    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    return conn

def cleanup_old_data():
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Calculate timestamp from 1 hours ago
        cutoff_time = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"Cleaning data older than {cutoff_time}")

        # Get count of records to be deleted
        cursor.execute("SELECT COUNT(*) FROM subscribers WHERE timestamp < ?", (cutoff_time,))
        count = cursor.fetchone()[0]

        if count > 0:
            cursor.execute("DELETE FROM subscribers WHERE timestamp < ?", (cutoff_time,))
            conn.commit()
            logger.info(f"Deleted {count} old records from database")
        else:
            logger.info("No old records to delete")

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        logger.exception(e)
    finally:
        conn.close()

def run_scheduler():
    def cleanup_wrapper():
        logger.info("=== STARTING HOUSEKEEPING ===")
        cleanup_old_data()
        # Schedule next run (1 hours)
        threading.Timer(3600, cleanup_wrapper).start()

    cleanup_wrapper()  # Start first run

if __name__ == "__main__":
    logger.info("Housekeeping service started")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Housekeeping service stopped")

