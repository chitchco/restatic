import sys
import os
import peewee

from filelock import FileLock, Timeout

from restatic.models import init_db
from restatic.application import RestaticApp
from restatic.config import SETTINGS_DIR
from restatic.updater import get_updater


def main():
    pid_file = os.path.join(SETTINGS_DIR, "restatic.pid")
    try:
        with FileLock(pid_file, timeout=0):
            # Init database
            dbpath = os.path.join(SETTINGS_DIR, "settings.db")
            print("Using database " + dbpath)
            sqlite_db = peewee.SqliteDatabase(dbpath)
            init_db(sqlite_db)

            app = RestaticApp(sys.argv)
            app.updater = get_updater()
            sys.exit(app.exec_())
    except Timeout:
        print("An instance of Restatic is already running.")


if __name__ == "__main__":
    main()
