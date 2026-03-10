import logging
import sys
from pathlib import Path
from datetime import datetime
from core.config_loader import settings


def get_logger(name="XYC"):
    cfg = settings()
    level = getattr(logging, cfg.get("log", {}).get("level", "INFO"))
    log_dir = Path(cfg.get("log", {}).get("dir", "logs"))
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(threadName)s] %(levelname)s %(message)s",
                            datefmt="%H:%M:%S")

    # 控制台
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 文件
    fh = logging.FileHandler(
        log_dir / f"xyc_{datetime.now():%Y-%m-%d}.log",
        encoding="utf-8"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger