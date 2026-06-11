"""Convenience launcher: ``python run.py`` starts the platform on port 5000."""

from app.main import app

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
