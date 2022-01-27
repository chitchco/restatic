import sys
from PyQt5 import uic, QtCore
from PyQt5.QtWidgets import QTableWidgetItem, QTableView, QHeaderView

from restatic.restic.prune import ResticPruneThread
# from restatic.restic.keep import ResticKeepThread
from restatic.restic.list import ResticListThread
from restatic.restic.check import ResticCheckThread
from restatic.restic.mount import ResticMountThread
from restatic.restic.umount import ResticUmountThread
from restatic.views.extract_dialog import ExtractDialog
from restatic.utils import get_asset, choose_folder_dialog
from restatic.models import BackupProfileMixin, ArchiveModel

uifile = get_asset("UI/archivetab.ui")
ArchiveTabUI, ArchiveTabBase = uic.loadUiType(
    uifile, from_imports=True, import_from="restatic.views"
)


class ArchiveTab(ArchiveTabBase, ArchiveTabUI, BackupProfileMixin):
    prune_intervals = ["hour", "day", "week", "month", "year"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(parent)
        self.mount_point = None

        header = self.archiveTable.horizontalHeader()
        header.setVisible(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setStretchLastSection(True)

        if sys.platform != "darwin":
            self._set_status("")  # Set platform-specific hints.

        self.archiveTable.setSelectionBehavior(QTableView.SelectRows)
        self.archiveTable.setEditTriggers(QTableView.NoEditTriggers)
        self.archiveTable.setAlternatingRowColors(True)

        # Populate pruning options from database
        for i in self.prune_intervals:
            getattr(self, f"prune_{i}").setValue(getattr(self.profile(), f"prune_{i}"))
            getattr(self, f"prune_{i}").valueChanged.connect(self.save_prune_setting)

        self.mountButton.clicked.connect(self.mount_action)
        self.listButton.clicked.connect(self.list_action)
        self.pruneButton.clicked.connect(self.prune_action)
        self.checkButton.clicked.connect(self.check_action)
        self.extractButton.clicked.connect(self.extract_action)

        self.populate_from_profile()

    def _set_status(self, text):
        self.mountErrors.setText(text)
        self.mountErrors.repaint()

    def _toggle_all_buttons(self, enabled=True):
        self.checkButton.setEnabled(enabled)
        self.listButton.setEnabled(enabled)
        self.pruneButton.setEnabled(enabled)
        self.mountButton.setEnabled(enabled)

    def populate_from_profile(self):

        profile = self.profile()

        if profile.repo is not None:
            self.currentRepoLabel.setText(profile.repo.url)
            self.archiveTable.setRowCount(0)  # clear the table

            for row, archive in enumerate(
                ArchiveModel.select().where(ArchiveModel.repo == profile.repo)
            ):
                self.archiveTable.insertRow(row)
                formatted_time = str(archive.time)
                # formatted_time = archive.time.strftime("%Y-%m-%d %H:%M") # FIXME
                self.archiveTable.setItem(row, 0, QTableWidgetItem(archive.name))
                self.archiveTable.setItem(row, 1, QTableWidgetItem(formatted_time))
                self.archiveTable.setItem(row, 2, QTableWidgetItem(archive.hostname))
            # self.archiveTable.setRowCount(len(archives))
            self._toggle_all_buttons(enabled=True)

        else:
            self.archiveTable.setRowCount(0)
            self.currentRepoLabel.setText("N/A")
            self._toggle_all_buttons(enabled=False)

    def check_action(self):
        params = ResticCheckThread.prepare(self.profile())
        if params["ok"]:
            thread = ResticCheckThread(params["cmd"], params, parent=self)
            thread.updated.connect(self._set_status)
            thread.result.connect(self.check_result)
            self._toggle_all_buttons(False)
            thread.start()

    def check_result(self, result):
        if result["returncode"] == 0:
            self._toggle_all_buttons(True)

    # def pruneit_action(self):
    #     self.keep_action()
    #     self.prune_action()

    # def keep_action(self):
    #     params = ResticKeepThread.prepare(self.profile())
    #     if params["ok"]:
    #         thread = ResticKeepThread(params["cmd"], params, parent=self)
    #         thread.updated.connect(self._set_status)
    #         thread.result.connect(self.keep_result)
    #         self._toggle_all_buttons(False)
    #         thread.start()

    # def keep_result(self, result):
    #     if result["returncode"] == 0:
    #         self._set_status("Pruning finished.")
    #         self.list_action()
    #     else:
    #         self._toggle_all_buttons(True)

    def prune_action(self):
        params = ResticPruneThread.prepare(self.profile())
        if params["ok"]:
            thread = ResticPruneThread(params["cmd"], params, parent=self)
            thread.updated.connect(self._set_status)
            thread.result.connect(self.prune_result)
            self._toggle_all_buttons(False)
            thread.start()

    def prune_result(self, result):
        if result["returncode"] == 0:
            self._set_status("Pruning finished.")
            self.list_action()
        else:
            self._toggle_all_buttons(True)

    def list_action(self):
        params = ResticListThread.prepare(self.profile())
        if params["ok"]:
            thread = ResticListThread(params["cmd"], params, parent=self)
            thread.updated.connect(self._set_status)
            thread.result.connect(self.list_result)
            self._toggle_all_buttons(False)
            thread.start()

    def list_result(self, result):
        self._toggle_all_buttons(True)
        if result["returncode"] == 0:
            self._set_status("Refreshed snapshots.")
            self.populate_from_profile()

    def mount_action(self):
        profile = self.profile()
        params = ResticMountThread.prepare(profile)
        if not params["ok"]:
            self._set_status(params["message"])
            return

        # Conditions are met (restic binary available, etc)
        row_selected = self.archiveTable.selectionModel().selectedRows()
        if row_selected:
            snapshot_cell = self.archiveTable.item(row_selected[0].row(), 3)
            if snapshot_cell:
                snapshot_name = snapshot_cell.text()
                params["cmd"][-1] += f"::{snapshot_name}"

        def receive():
            mount_point = dialog.selectedFiles()
            if mount_point:
                params["cmd"].append(mount_point[0])
                self.mount_point = mount_point[0]
                if params["ok"]:
                    self._toggle_all_buttons(False)
                    thread = ResticMountThread(params["cmd"], params, parent=self)
                    thread.updated.connect(self.mountErrors.setText)
                    thread.result.connect(self.mount_result)
                    thread.start()

        dialog = choose_folder_dialog(self, "Choose Mount Point")
        dialog.open(receive)

    def mount_result(self, result):
        self._toggle_all_buttons(True)
        if result["returncode"] == 0:
            self._set_status("Mounted successfully.")
            self.mountButton.setText("Unmount")
            self.mountButton.clicked.disconnect()
            self.mountButton.clicked.connect(self.umount_action)
        else:
            self.mount_point = None

    def umount_action(self):
        if self.mount_point is not None:
            profile = self.profile()
            params = ResticUmountThread.prepare(profile)
            if not params["ok"]:
                self._set_status(params["message"])
                return

            if self.mount_point in params["active_mount_points"]:
                params["cmd"].append(self.mount_point)
                thread = ResticUmountThread(params["cmd"], params, parent=self)
                thread.updated.connect(self.mountErrors.setText)
                thread.result.connect(self.umount_result)
                thread.start()
            else:
                self._set_status("Mount point not active. Try restarting Restatic.")
                return

    def umount_result(self, result):
        self._toggle_all_buttons(True)
        if result["returncode"] == 0:
            self._set_status("Un-mounted successfully.")
            self.mountButton.setText("Mount")
            self.mountButton.clicked.disconnect()
            self.mountButton.clicked.connect(self.mount_action)
            self.mount_point = None

    def save_prune_setting(self, new_value):
        profile = self.profile()
        for i in self.prune_intervals:
            setattr(profile, f"prune_{i}", getattr(self, f"prune_{i}").value())
        profile.save()

    def extract_action(self):
        window = ExtractDialog()
        window.setParent(self, QtCore.Qt.Sheet)
        window.show()
