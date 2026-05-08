from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


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
    server = ReusableThreadingHTTPServer(("127.0.0.1", 5173), handler)
    try:
        print("AI chatbot frontend running at http://localhost:5173")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAI chatbot frontend stopped.")
    finally:
        server.server_close()
