# SPDX-FileCopyrightText: 2026 The SoundSight contributors
# SPDX-License-Identifier: Apache-2.0
"""Allow ``python -m soundsight``."""

import sys

from soundsight.cli import main

if __name__ == "__main__":
    sys.exit(main())
