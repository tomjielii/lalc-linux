import shutil
import sys

_REQUIRED = {
    "xdotool": "xdotool（鼠标/键盘操作）",
    "import": "imagemagick（窗口截图）",
}

missing = [f"  {cmd}  — {desc}" for cmd, desc in _REQUIRED.items() if not shutil.which(cmd)]
if missing:
    print(
        "⚠ 以下系统命令未找到，请通过包管理器安装：\n"
        + "\n".join(missing)
        + "\n  Arch:  sudo pacman -S xdotool imagemagick"
        + "\n  Ubuntu: sudo apt install xdotool imagemagick"
        + "\n  Fedora: sudo dnf install xdotool ImageMagick",
        file=sys.stderr,
    )
