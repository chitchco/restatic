import os
import sys
#import fcntl
import portalocker

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from .tray_menu import TrayMenu
from .scheduler import RestaticScheduler
from .models import BackupProfileModel
from .restic.create import ResticCreateThread
from .views.main_window import MainWindow
from .utils import get_asset
from restatic.config import SETTINGS_DIR


class RestaticApp(QApplication):
    """
    All windows and QWidgets are children of this app.

    When running Restic-commands, the class `ResticThread` will emit events
    via the `RestaticApp` class to which other windows will subscribe to.
    """

    backup_started_event = QtCore.pyqtSignal()
    backup_finished_event = QtCore.pyqtSignal(dict)
    backup_cancelled_event = QtCore.pyqtSignal()
    backup_log_event = QtCore.pyqtSignal(str)
    backup_progress_event = QtCore.pyqtSignal(int)

    def __init__(self, args, single_app=False):

        # Ensure only one app instance is running.
        # From https://stackoverflow.com/questions/220525/
        #              ensure-a-single-instance-of-an-application-in-linux#221159
        if single_app:
            pid_file = os.path.join(SETTINGS_DIR, "restatic.pid")
            lockfile = open(pid_file, "w+")
            try:
                # fcntl.lockf(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                portalocker.lock(lockfile, portalocker.LOCK_EX | portalocker.LOCK_NB)
                self.lockfile = lockfile
            except OSError:
                print("An instance of Restatic is already running.")
                sys.exit(1)

        super().__init__(args)
        self.setQuitOnLastWindowClosed(False)
        self.scheduler = RestaticScheduler(self)

        # Prepare tray and main window
        self.tray = TrayMenu(self)
        self.main_window = MainWindow(self)
        self.main_window.show()

        self.backup_started_event.connect(self.backup_started_event_response)
        self.backup_finished_event.connect(self.backup_finished_event_response)
        self.backup_cancelled_event.connect(self.backup_cancelled_event_response)

    def create_backup_action(self, profile_id=None):
        if not profile_id:
            profile_id = self.main_window.current_profile.id

        profile = BackupProfileModel.get(id=profile_id)
        msg = ResticCreateThread.prepare(profile)
        if msg["ok"]:
            thread = ResticCreateThread(msg["cmd"], msg, parent=self)
            thread.start()
        else:
            self.backup_log_event.emit(msg["message"])

    def open_main_window_action(self):
        self.main_window.show()
        self.main_window.raise_()

    def backup_started_event_response(self):
        icon = QIcon(get_asset("icons/hdd-o-active.png"))
        self.tray.setIcon(icon)

    def backup_finished_event_response(self):
        icon = QIcon(get_asset("icons/hdd-o.png"))
        self.tray.setIcon(icon)
        self.main_window.scheduleTab._draw_next_scheduled_backup()

    def backup_cancelled_event_response(self):
        icon = QIcon(get_asset("icons/hdd-o.png"))
        self.tray.setIcon(icon)
