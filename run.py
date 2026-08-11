import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug is OFF unless FLASK_DEBUG=1 is explicitly set (never in production).
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5050))
    app.run(host=host, port=port, debug=debug)
