import os


def is_admin_enabled() -> bool:
    return os.environ.get("OPENWEBRX_ADMIN_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
