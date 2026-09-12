from __future__ import annotations

import sys

from trading_bot.app import auto_trader as _impl

sys.modules[__name__] = _impl
