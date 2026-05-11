import io
import sys
from loguru import logger


def setup_logger(level: str = "INFO"):
    # Force UTF-8 on Windows stderr to avoid garbled Chinese output
    if sys.platform == "win32":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    return logger
