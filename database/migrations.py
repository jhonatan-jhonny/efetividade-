from threading import Lock

from database.connection import engine
from database.models import Base


_initialization_lock = Lock()
_initialized = False


def init_db() -> None:
    global _initialized
    if _initialized:
        return
    with _initialization_lock:
        if not _initialized:
            Base.metadata.create_all(bind=engine)
            _initialized = True


if __name__ == "__main__":
    init_db()
