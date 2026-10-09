import re
import stat
from pathlib import Path

import pyrlottie

from log import logger

_EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
_BIN_DIR_PATTERN = re.compile(r"^(linux|windows|darwin|macos)_")


def ensure_pyrlottie_exec_bit() -> None:
    """pyrlottie 的 wheel 中 lottie2gif / gif2webp 等二进制没有执行位, 补上 +x"""
    pkg_dir = Path(pyrlottie.__file__).parent
    for bin_dir in pkg_dir.iterdir():
        if not bin_dir.is_dir() or not _BIN_DIR_PATTERN.match(bin_dir.name):
            continue
        for binary in bin_dir.iterdir():
            if not binary.is_file():
                continue
            try:
                if binary.stat().st_mode & _EXEC_BITS != _EXEC_BITS:
                    binary.chmod(binary.stat().st_mode | _EXEC_BITS)
                    logger.debug(f"已为 {binary} 添加执行位")
            except OSError as e:
                logger.warning(f"无法为 {binary} 添加执行位: {e}")
