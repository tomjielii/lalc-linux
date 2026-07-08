import time
import random

from .game_window import is_window
from .x11_input import (
    send_key as _x11_key,
    send_key_down as _x11_key_down,
    send_key_up as _x11_key_up,
)


def key_press(hwnd, key, duration=0.05):
    """
    按键（按下+释放）
    使用 X11 XSendEvent 向目标窗口发送按键事件，物理鼠标完全不移动。
    :param hwnd: X11 window ID
    :param key: 键名（如 'p', 'enter', 'esc'）
    :param duration: 按键持续时间（秒）
    :return: 操作是否成功
    """
    if not is_window(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")

    try:
        _x11_key(hwnd, key)
        time.sleep(duration + random.random() * 0.03)
        return True
    except Exception as e:
        raise Exception(f"按键失败 '{key}': {e}")


def key_down(hwnd, key):
    """
    按键按下（不释放）
    :param hwnd: X11 window ID
    :param key: 键名
    :return: 操作是否成功
    """
    if not is_window(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")

    try:
        _x11_key_down(hwnd, key)
        return True
    except Exception as e:
        raise Exception(f"按键按下失败 '{key}': {e}")


def key_up(hwnd, key):
    """
    按键释放
    :param hwnd: X11 window ID
    :param key: 键名
    :return: 操作是否成功
    """
    if not is_window(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")

    try:
        _x11_key_up(hwnd, key)
        return True
    except Exception as e:
        raise Exception(f"按键释放失败 '{key}': {e}")


if __name__ == "__main__":
    from .game_window import find_game_window, get_window_size

    hwnd = find_game_window()
    if not hwnd:
        print("未找到游戏窗口"); exit(1)
    print(f"窗口句柄: {hwnd}")

    tests = [
        ("press 'p'",     key_press, "p"),
        ("down 'space'",  key_down,  "space"),
        ("hold…",         None,      None),
        ("up 'space'",    key_up,    "space"),
    ]

    print()
    for name, func, k in tests:
        if func is None:
            print(f"  ⏳ 按住 0.5s…"); time.sleep(0.5); continue
        try:
            func(hwnd, k)
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
        time.sleep(0.3)

    print("\n完成")