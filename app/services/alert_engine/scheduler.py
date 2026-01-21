
from fastapi_utils.tasks import repeat_every
from .config import POLL_INTERVAL_SECONDS
from .service import process_usgs_feed


def start_scheduler(app):
    @app.on_event("startup")
    @repeat_every(seconds=POLL_INTERVAL_SECONDS)
    def poll_usgs():
        process_usgs_feed()
