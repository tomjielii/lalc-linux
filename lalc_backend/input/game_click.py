import subprocess
import re
import time
import random

from .game_window import is_window, get_window_size
from .x11_input import (
    send_click as _x11_click,
    send_mouse_down as _x11_mouse_down,
    send_mouse_up as _x11_mouse_up,
)

def get_cursor_pos():
    """
    获取当前鼠标位置
    :return: (x, y) 屏幕坐标元组，失败返回 (None, None)
    """
    r = subprocess.run(
        ["xdotool", "getmouselocation"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        return None, None

    m = re.search(r"x:(\d+)\s+y:(\d+)", r.stdout)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def is_mouse_in_window(hwnd):
    """
    判断鼠标是否在窗口内
    :param hwnd: X11 window ID
    :return: (True/False, mouse_x, mouse_y)，无效窗口返回 False
    """
    if not is_window(hwnd):
        return False

    mouse_x, mouse_y = get_cursor_pos()
    if mouse_x is None:
        return False

    r = subprocess.run(
        ["xdotool", "getwindowgeometry", hwnd],
        capture_output=True, text=True
    )
    m = re.search(r"Position: (\d+),(\d+)", r.stdout)
    if not m:
        return False
    wx, wy = int(m.group(1)), int(m.group(2))

    w, h = get_window_size(hwnd)
    if w is None:
        return False

    return (wx <= mouse_x <= wx + w and wy <= mouse_y <= wy + h, mouse_x, mouse_y)


def move_mouse_to_top_right_corner(hwnd):
    """
    将鼠标移动到窗口右上角
    :param hwnd: X11 window ID
    """
    if not is_window(hwnd):
        return

    w, h = get_window_size(hwnd)
    if w is None:
        return

    corner_x = w + 10
    corner_y = -5
    subprocess.run(
        ["xdotool", "mousemove", "--window", hwnd, str(corner_x), str(corner_y)],
        capture_output=True, text=True
    )

def mouse_click(hwnd, x, y):
    """
    鼠标点击（按下+释放）
    使用 X11 XSendEvent 向目标窗口发送点击事件，物理鼠标完全不移动。
    :param hwnd: X11 window ID
    :param x: 客户端坐标 x（相对于窗口客户区左上角）
    :param y: 客户端坐标 y
    :return: 操作是否成功
    """
    if not is_window(hwnd):
        return False

    try:
        click_x = int(x) + random.randint(-3, 3)
        click_y = int(y) + random.randint(-3, 3)

        _x11_click(hwnd, click_x, click_y)
        time.sleep(0.1 + random.random() * 0.05)

        return True

    except Exception as e:
        raise e


def mouse_down(hwnd, x, y):
    """
    鼠标按下（不释放）
    使用 X11 XSendEvent 向目标窗口发送按下事件，物理鼠标完全不移动。
    :param hwnd: X11 window ID
    :param x: 客户端坐标 x（相对于窗口客户区左上角）
    :param y: 客户端坐标 y
    :return: 操作是否成功
    """
    if not is_window(hwnd):
        return False

    try:
        click_x = int(x) + random.randint(-3, 3)
        click_y = int(y) + random.randint(-3, 3)

        _x11_mouse_down(hwnd, click_x, click_y)
        time.sleep(0.05 + random.random() * 0.03)

        return True

    except Exception as e:
        raise e


def mouse_up(hwnd, x, y):
    """
    鼠标释放
    使用 X11 XSendEvent 向目标窗口发送释放事件，物理鼠标完全不移动。
    :param hwnd: X11 window ID
    :param x: 客户端坐标 x（相对于窗口客户区左上角）
    :param y: 客户端坐标 y
    :return: 操作是否成功
    """
    if not is_window(hwnd):
        return False

    try:
        click_x = int(x) + random.randint(-3, 3)
        click_y = int(y) + random.randint(-3, 3)

        _x11_mouse_up(hwnd, click_x, click_y)
        time.sleep(0.05 + random.random() * 0.03)

        return True

    except Exception as e:
        raise e



if __name__ == "__main__":
    from .game_window import find_game_window, get_window_size

    hwnd = find_game_window()
    if not hwnd:
        print("未找到游戏窗口"); exit(1)

    # 取窗口中心偏右下的位置作为测试点
    w, h = get_window_size(hwnd)
    if w is None:
        print("无法获取窗口大小"); exit(1)
    tx, ty = w // 2 + 50, h // 2 + 50

    print(f"窗口句柄: {hwnd}  测试坐标: ({tx}, {ty})")

    tests = [
        ("click", mouse_click),
        ("down",  mouse_down),
        ("hold…", None),
        ("up",    mouse_up),
    ]

    print()
    for name, func in tests:
        if func is None:
            print(f"  ⏳ 按下保持 1s…"); time.sleep(1); continue
        try:
            r = func(hwnd, tx, ty)
            print(f"  {'✓' if r else '✗'} {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
        time.sleep(0.3)

    print("\n完成")