#!/usr/bin/env python3
"""
Who's In the Erg Room?
Main entry point - starts scanner and web server.
"""

import argparse
import signal
import sys

from app.web import create_app
from app.scanner import stop_scanner
from app.config import WEB_HOST, WEB_PORT


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\nShutting down...")
    stop_scanner()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Who's In the Erg Room?")
    parser.add_argument(
        "--no-camera", 
        action="store_true",
        help="Run without camera (test mode)"
    )
    parser.add_argument(
        "--debug",
        action="store_true", 
        help="Run Flask in debug mode"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=WEB_PORT,
        help=f"Port to run web server on (default: {WEB_PORT})"
    )
    
    args = parser.parse_args()
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run app
    use_camera = not args.no_camera
    app = create_app(use_camera=use_camera)
    
    print(f"""
╔═══════════════════════════════════════════╗
║     Who's In the Erg Room?                ║
╠═══════════════════════════════════════════╣
║  Web UI:  http://{WEB_HOST}:{args.port:<5}              ║
║  Admin:   http://{WEB_HOST}:{args.port}/admin         ║
╚═══════════════════════════════════════════╝
    """)
    
    app.run(
        host=WEB_HOST, 
        port=args.port, 
        debug=args.debug,
        threaded=True
    )


if __name__ == "__main__":
    main()
