"""Flask application entry point."""

from __future__ import annotations

import os

from flask import Flask, send_from_directory

from .api import api, init_fleet
from .services.fleet_manager import FleetManager
from .subsystems import registry as subsystem_registry


def create_app() -> Flask:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app = Flask(__name__, static_folder=static_dir, static_url_path="/static")

    # Initialise the fleet against the default Battery Thermal subsystem.
    fleet = FleetManager(subsystem_registry.get("battery_thermal"))
    init_fleet(fleet)
    app.register_blueprint(api)

    @app.get("/")
    def index():  # type: ignore[unused-ignore]
        return send_from_directory(static_dir, "index.html")

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
