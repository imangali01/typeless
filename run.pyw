"""Console-less launcher (used by autostart): pythonw.exe run.pyw"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from typeless.app import main  # noqa: E402

sys.exit(main())
