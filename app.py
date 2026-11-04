# Vercel & WSGI Python Entrypoint
from api.index import handler, app

if __name__ == "__main__":
    import http.server
    server = http.server.HTTPServer(("0.0.0.0", 8501), handler)
    print("Serving BEBOP API on http://0.0.0.0:8501 ...")
    server.serve_forever()
