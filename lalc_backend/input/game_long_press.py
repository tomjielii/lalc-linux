import time
import random

from .game_click import mouse_down, mouse_up


def mouse_long_press(hwnd, x, y, duration=3):
    """
    鼠标长按：按下鼠标，保持指定时间后释放
    :param hwnd: X11 window ID
    :param x: x坐标（客户端坐标）
    :param y: y坐标（客户端坐标）
    :param duration: 按下后到释放前的间隔时间（秒），默认3秒
    :return: 操作是否成功
    """
    try:
        mouse_down(hwnd, x, y)
        time.sleep(duration)
        mouse_up(hwnd, x, y)
        return True
    except Exception as e:
        raise e


if __name__ == "__main__":
    # 测试函数：需要先运行main.py获取hwnd
    from .game_window import (
        set_window_size,
        find_game_window,
    )

    try:
        hwnd = find_game_window()
        if not hwnd:
            print("未找到游戏窗口")
            exit(1)
        print(f"成功连接游戏窗口，句柄: {hwnd}")
        set_window_size(hwnd)
        print("测试长按（3秒）...")
        time.sleep(1)
        mouse_long_press(hwnd, 850, 660, duration=3)
        print("长按测试完成")

    except Exception as e:
        print(f"长按测试失败: {str(e)}")
