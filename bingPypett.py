"""Legacy entry point.

The original Pyppeteer prototype stored raw authentication cookies in a JSON
file and is no longer supported. Use pyRewards.py instead. This shim keeps
older shortcuts working without writing sensitive cookie files.
"""

from pyrewards.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
