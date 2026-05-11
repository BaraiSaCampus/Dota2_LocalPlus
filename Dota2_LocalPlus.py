from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication, QMessageBox

import economy_overlay
import install_gsi_config


def main() -> int:
    gsi_result = install_gsi_config.main()
    if gsi_result != 0:
        app = QApplication.instance() or QApplication([])
        QMessageBox.warning(
            None,
            "Dota2 LocalPlus",
            "没有找到 Dota2 根目录，无法自动写入 GSI 配置。\n\n"
            "请把整个 Dota2_LocalPlus 文件夹放到 Dota2 游戏根目录下：\n"
            "...\\steamapps\\common\\dota 2 beta\\Dota2_LocalPlus",
        )
        return gsi_result

    economy_overlay.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

