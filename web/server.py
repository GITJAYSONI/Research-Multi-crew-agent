"""Compatibility entrypoint for the static web frontend.

The original local static server is named serve.py. This file exists because
some project notes refer to web/server.py. Keep scraping and analysis logic in
the backend pipeline/api_server.py; this server only serves frontend assets.
"""

from serve import Handler
from http.server import ThreadingHTTPServer
from pathlib import Path


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    web_root = Path(__file__).resolve().parent
    handler = lambda *args, **kwargs: Handler(*args, directory=str(web_root), **kwargs)
    server = ReusableThreadingHTTPServer(("127.0.0.1", 5173), handler)
    try:
        print("AI chatbot frontend running at http://localhost:5173")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAI chatbot frontend stopped.")
    finally:
        server.server_close()
