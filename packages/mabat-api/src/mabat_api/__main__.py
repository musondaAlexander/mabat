"""``mabat-api`` console script: serve the app with uvicorn."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="mabat-api", description="Serve mabat over HTTP.")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: loopback)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run("mabat_api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
