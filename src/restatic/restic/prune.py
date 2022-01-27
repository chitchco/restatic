from .restic_thread import ResticThread


class ResticPruneThread(ResticThread):
    def log_event(self, msg):
        self.app.backup_log_event.emit(msg)

    def started_event(self):
        self.app.backup_started_event.emit()
        self.app.backup_log_event.emit("Pruning old snapshots..")

    def finished_event(self, result):
        self.app.backup_finished_event.emit(result)
        self.result.emit(result)

        if result["returncode"] == 0:
            self.app.backup_log_event.emit("Pruning done. No error reported.")
        else:
            self.app.backup_log_event.emit("Pruning done. There was an error.")

    @classmethod
    def prepare(cls, profile):
        ret = super().prepare_keep(profile)
        if not ret["ok"]:
            return ret
        else:
            popenargs = [
                f'--keep-hourly {profile.prune_hour}',
                f'--keep-daily {profile.prune_day}',
                f'--keep-weekly {profile.prune_week}',
                f'--keep-monthly {profile.prune_month}',
                f'--keep-yearly {profile.prune_year}'
                '--prune'
            ]
            print(popenargs)
            ret["ok"] = False  # Set back to false, so we can do our own checks here.
        cmd = ["restic", "-r", f"{profile.repo.url}", "forget", "--json", *popenargs]
        print(cmd)

        ret["ok"] = True
        ret["cmd"] = cmd

        return ret

    @classmethod
    def prepare(cls,  profile):
        ret = super().prepare(profile)
        if not ret["ok"]:
            return ret
        else:
            cmd = [
                "restic",
                "-r",
                f"{profile.repo.url}",
                'forget',
                '--keep-hourly',
                f'{profile.prune_hour}',
                f'--keep-daily',
                f'{profile.prune_day}',
                f'--keep-weekly',
                f'{profile.prune_week}',
                f'--keep-monthly',
                f'{profile.prune_month}',
                '--keep-yearly',
                f'{profile.prune_year}',
                '--prune',
                '--json'
            ]
            ret["ok"] = False  # Set back to false, so we can do our own checks here.

        ret["ok"] = True
        ret["cmd"] = cmd

        return ret
