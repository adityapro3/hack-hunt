import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    print("$", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=False)
    return completed.returncode


def _python_module(*parts: str) -> list[str]:
    return [sys.executable, "-m", *parts]


def _configure_windows_proactor_policy() -> None:
    if sys.platform != "win32":
        return

    policy_type = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if policy_type is None:
        return

    current = asyncio.get_event_loop_policy()
    if not isinstance(current, policy_type):
        asyncio.set_event_loop_policy(policy_type())


def cmd_app(args: argparse.Namespace) -> int:
    _configure_windows_proactor_policy()
    reload_enabled = args.reload
    if sys.platform == "win32" and reload_enabled:
        print(
            "Windows reload mode is disabled because it can break Playwright subprocess support."
        )
        reload_enabled = False

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=reload_enabled,
    )
    return 0


def cmd_frontend(args: argparse.Namespace) -> int:
    next_package = PROJECT_ROOT / "frontend" / "package.json"

    if next_package.exists():
        command = ["npm", "run", "dev", "--", "--port", str(args.port)]
        return _run(command, cwd=PROJECT_ROOT / "frontend")

    print("No supported frontend entrypoint found (expected frontend/package.json or frontend/app.py).")
    return 1


def _alembic_base() -> list[str]:
    return _python_module("alembic", "-c", "backend/infra/postgres/alembic.ini")


def cmd_db_upgrade(args: argparse.Namespace) -> int:
    return _run([*_alembic_base(), "upgrade", args.revision])


def cmd_db_downgrade(args: argparse.Namespace) -> int:
    return _run([*_alembic_base(), "downgrade", args.revision])


def cmd_db_revision(args: argparse.Namespace) -> int:
    command = [*_alembic_base(), "revision", "-m", args.message]
    if args.autogenerate:
        command.append("--autogenerate")
    return _run(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler",
        description="Oppora project command runner",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    app_parser = subparsers.add_parser("app", help="Run FastAPI backend")
    app_parser.add_argument("--host", default="0.0.0.0")
    app_parser.add_argument("--port", type=int, default=8000)
    app_parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=(sys.platform != "win32"),
    )
    app_parser.set_defaults(func=cmd_app)

    frontend_parser = subparsers.add_parser("frontend", help="Run Next.js frontend dev server")
    frontend_parser.add_argument("--port", type=int, default=3000)
    frontend_parser.set_defaults(func=cmd_frontend)

    db_parser = subparsers.add_parser("db", help="Database migration commands")
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)

    db_upgrade = db_sub.add_parser("upgrade", help="Upgrade migrations")
    db_upgrade.add_argument("revision", nargs="?", default="head")
    db_upgrade.set_defaults(func=cmd_db_upgrade)

    db_downgrade = db_sub.add_parser("downgrade", help="Downgrade migrations")
    db_downgrade.add_argument("revision", nargs="?", default="-1")
    db_downgrade.set_defaults(func=cmd_db_downgrade)

    db_revision = db_sub.add_parser("revision", help="Create migration revision")
    db_revision.add_argument("-m", "--message", required=True)
    db_revision.add_argument("--autogenerate", action="store_true")
    db_revision.set_defaults(func=cmd_db_revision)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    exit_code = args.func(args)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
