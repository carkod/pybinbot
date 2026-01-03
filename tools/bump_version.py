import os
import re
from pathlib import Path


def main() -> None:
    part = os.environ.get("PART", "patch")

    path = Path("pyproject.toml")
    text = path.read_text()

    pattern = re.compile(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', re.M)
    match = pattern.search(text)
    if not match:
        raise SystemExit("version not found in pyproject.toml")

    major, minor, patch = map(int, match.groups())

    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise SystemExit(f"Unknown PART: {part}")

    new_version = f"{major}.{minor}.{patch}"

    def repl(m: re.Match[str]) -> str:
        return f'version = "{new_version}"'

    new_text = pattern.sub(repl, text, count=1)
    path.write_text(new_text)
    print(f"Bumped {part} version to {new_version}")


if __name__ == "__main__":
    main()
