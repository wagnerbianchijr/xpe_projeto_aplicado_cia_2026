"""ASGI entry point. `uvicorn main:app` serves the dashboard."""
from app import create_app
from config import load_settings
from db import Database, create_pool

_settings = load_settings()
_pool = create_pool(_settings.database_url)
app = create_app(Database(_pool), refresh_seconds=_settings.refresh_seconds)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=_settings.host, port=_settings.port)


if __name__ == "__main__":
    main()
