from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        from .worker import run_worker

        return run_worker(sys.argv[2])

    from .app import run_app

    return run_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
