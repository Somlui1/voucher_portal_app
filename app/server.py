import os
import sys
import uvicorn

if __name__ == "__main__":
    # Ensure project root is in sys.path so we can import app.main
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Check if SSL certificates exist, otherwise run on standard HTTP
    ssl_key = os.path.join(project_root, "key.pem")
    ssl_cert = os.path.join(project_root, "cert.pem")
    
    ssl_args = {}
    if os.path.exists(ssl_key) and os.path.exists(ssl_cert):
        ssl_args = {
            "ssl_keyfile": ssl_key,
            "ssl_certfile": ssl_cert
        }
        print("Starting server with HTTPS...")
    else:
        print("SSL certificates (key.pem/cert.pem) not found. Starting server with HTTP...")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        **ssl_args
    )
