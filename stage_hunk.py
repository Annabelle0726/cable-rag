"""Stage one hunk of a file that another writer is also editing.

`web/tailwind.css` currently carries both this session's hover-wash rule and a
concurrent session's dark-palette rewrite. Committing the file wholesale would
take their work-in-progress with it, so the hunk that mentions the marker is
extracted into a patch and applied to the index only — the remaining changes stay
in the working tree, untouched and uncommitted.

Usage: stage_hunk.py <path> <marker>
"""

import subprocess
import sys
from pathlib import Path

path, marker = sys.argv[1], sys.argv[2]

diff = subprocess.run(
    ["git", "diff", "-U5", "--", path],
    capture_output=True,
    text=True,
    encoding="utf-8",
).stdout

if not diff.strip():
    print("no diff for", path)
    sys.exit(1)

lines = diff.splitlines(keepends=True)
header, hunks, current = [], [], None

for line in lines:
    if line.startswith("@@"):
        if current is not None:
            hunks.append(current)
        current = [line]
    elif current is None:
        header.append(line)
    else:
        current.append(line)

if current is not None:
    hunks.append(current)

keep = [h for h in hunks if any(line.startswith("+") and marker in line for line in h)]
print(f"file has {len(hunks)} hunk(s); {len(keep)} add a line matching {marker!r}")

if not keep:
    sys.exit(1)

patch = Path("hover.patch")
patch.write_text(
    "".join(header) + "".join("".join(h) for h in keep),
    encoding="utf-8",
    newline="",
)

applied = subprocess.run(
    ["git", "apply", "--cached", "--recount", str(patch)],
    capture_output=True,
    text=True,
)
print("git apply --cached:", applied.returncode, applied.stderr.strip())
sys.exit(applied.returncode)
