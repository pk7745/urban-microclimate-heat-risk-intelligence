"""
Server entrypoint for Urban Microclimate & Heat-Risk Intelligence System Flask REST API.
"""
import os
import argparse
from app import create_app

app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Urban Microclimate Flask REST API")
    parser.add_argument("--host", default=os.getenv("FLASK_HOST", "0.0.0.0"), help="Host IP to bind to")
    parser.add_argument("--port", type=int, default=int(os.getenv("FLASK_PORT", "5000")), help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    print(f"============================================================")
    print(f" URBAN MICROCLIMATE REST API STARTING")
    print(f" Listening on: http://{args.host}:{args.port}")
    print(f" HBase REST:   http://localhost:8085")
    print(f" Health check: http://localhost:{args.port}/api/v1/health")
    print(f"============================================================")
    app.run(host=args.host, port=args.port, debug=args.debug)
