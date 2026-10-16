from datetime import datetime
import logging

class ReportHandler():
    def __init__(self, mgr=None, logger:logging.Logger=None):
        super().__init__()
        self.mgr = mgr
        self.logger = logger

    def report(self, type: str, msg: str):

        if self.logger:
            if type == "INFO":
                self.logger.info(msg)
            elif type == "WARNING":
                self.logger.warning(msg)
            elif type == "ERROR":
                self.logger.error(msg)
            elif type == "DEBUG":
                self.logger.debug(msg)

        if not self.mgr:
            return

        if not self.mgr.config.get("reporting", False):
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open("report.log", "a") as f:
            f.write(f"[{now}] {type}: {msg}\n")