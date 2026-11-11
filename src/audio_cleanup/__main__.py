"""Allow ``python -m audio_cleanup``."""

import sys

from audio_cleanup.cli import main

if __name__ == "__main__":
    sys.exit(main())
