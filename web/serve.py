from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".jsx": "text/javascript",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".html": "text/html",
    }


if __name__ == "__main__":
    web_root = Path(__file__).resolve().parent
    handler = lambda *args, **kwargs: Handler(*args, directory=str(web_root), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 5173), handler)
    print("AI chatbot frontend running at http://localhost:5173")
    server.serve_forever()
