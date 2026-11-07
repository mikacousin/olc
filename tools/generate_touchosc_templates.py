#!/usr/bin/env python3
"""CLI utility to generate OpenLightingConsole TouchOSC templates."""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.backends.osc.touchosc import generate_all_templates  # noqa: E402


def main() -> int:
    """Generate TouchOSC template files into data/templates/touchosc/."""
    out_dir = ROOT / "data" / "templates" / "touchosc"
    print(f"Generating TouchOSC templates in: {out_dir}")
    generated = generate_all_templates(str(out_dir))
    for t_type, file_path in generated.items():
        path = Path(file_path)
        size = path.stat().st_size
        print(f"  ✓ [{t_type}] {path.name} ({size:,} bytes)")
    print("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
