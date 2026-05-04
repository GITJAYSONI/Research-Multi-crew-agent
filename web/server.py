"""Compatibility entrypoint for the static web frontend.

The original local static server is named serve.py. This file exists because
some project notes refer to web/server.py. Keep scraping and analysis logic in
the backend pipeline/api_server.py; this server only serves frontend assets.
"""

from serve import Handler
from http.server import ThreadingHTTPServer


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 5173), Handler)
    print("AI chatbot frontend running at http://localhost:5173")
    server.serve_forever()
