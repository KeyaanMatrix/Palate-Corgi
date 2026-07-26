"""Command dispatch. BASE — frozen, and it never needs editing.

Subcommands are discovered by importing each package's own commands.py and
reading its COMMANDS dict. Adding a command means editing YOUR file, not this
one — which is why this file can never be a merge conflict.

    python -m palate ingest.sync 500
    python -m palate profile.build
    python -m palate plan.itinerary Lisbon 3
"""

import importlib
import sys

# Every package that may expose commands. Owners fill in their own commands.py.
_PACKAGES = ["llm", "ingest", "profile", "chat", "enrich", "plan"]


def _registry() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for pkg in _PACKAGES:
        for path in (f"palate.{pkg}.commands", f"palate.{pkg}"):
            try:
                module = importlib.import_module(path)
            except ImportError:
                continue
            commands = getattr(module, "COMMANDS", None)
            if isinstance(commands, dict):
                found[pkg] = commands
                break
    return found


def _usage(registry: dict[str, dict]) -> str:
    lines = ["usage: python -m palate <package>.<command> [args...]", ""]
    for pkg, commands in sorted(registry.items()):
        for name in sorted(commands):
            lines.append(f"  {pkg}.{name}")
    if len(lines) == 2:
        lines.append("  (no commands registered yet)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    registry = _registry()

    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_usage(registry))
        return 0

    target, _, name = argv[0].partition(".")
    commands = registry.get(target)
    if not commands or name not in commands:
        print(f"unknown command: {argv[0]}\n")
        print(_usage(registry))
        return 1

    result = commands[name](argv[1:])
    return 0 if result is None else int(bool(result) is False)
