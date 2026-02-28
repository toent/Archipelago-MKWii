from datetime import datetime

def report_handler(msg: str, mgr=None):
    if not mgr:
        return

    if not mgr.config.get("reporting", False):
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open("report.log", "a") as f:
        f.write(f"[{now}] {msg}\n")