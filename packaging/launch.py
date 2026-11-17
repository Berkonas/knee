import os
import sys

if getattr(sys, "frozen", False):  # keep matplotlib's font cache between launches (faster start)
    from trailbuddy.core.paths import user_data_dir

    cfg = user_data_dir() / "matplotlib"
    cfg.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(cfg)

from trailbuddy.__main__ import main  # noqa: E402

sys.exit(main())
