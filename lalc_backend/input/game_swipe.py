import subprocess
import time
import random

from .game_click import mouse_down, mouse_up
from .game_window import is_window


def _move_pointer(hwnd, x, y):
    """用 xdotool 移动真实指针；失败时抛异常，避免拖拽路径悄悄错位。"""
    r = subprocess.run(
        ["xdotool", "mousemove", "--window", hwnd, str(int(x)), str(int(y))],
        capture_output=True, text=True, timeout=5,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"xdotool mousemove 失败: {r.stderr.strip() or r.stdout.strip()}"
        )


def mouse_swipe(hwnd, start_x, start_y, end_x, end_y, speed=1):
    """
    鼠标拖拽：从起点坐标滑动到终点坐标
    - mouse_down/mouse_up: 使用 XSendEvent，不移动物理鼠标
    - 中间拖拽步骤: 使用 xdotool mousemove --window（拖拽必须物理移动鼠标）
    :param hwnd: X11 window ID
    :param start_x: 起点x坐标（客户端坐标）
    :param start_y: 起点y坐标（客户端坐标）
    :param end_x: 终点x坐标（客户端坐标）
    :param end_y: 终点y坐标（客户端坐标）
    :param speed: 拖拽速度，数值越小越快
    :return: 操作是否成功
    """
    if not is_window(hwnd):
        raise Exception(f"错误：窗口句柄无效（hwnd={hwnd}）")

    try:
        sx = int(start_x) + random.randint(-3, 3)
        sy = int(start_y) + random.randint(-3, 3)
        ex = int(end_x) + random.randint(-3, 3)
        ey = int(end_y) + random.randint(-3, 3)

        steps = int(20 * speed)
        sleep_time = 0.01 / speed
        delta_x = (ex - sx) / steps
        delta_y = (ey - sy) / steps

        # 先把真实指针移到起点再按下：XSendEvent 点击不动真实指针，
        # 残留的旧位置 + 起按瞬间的跳变会被游戏算进拖拽向量，导致滚动过量
        _move_pointer(hwnd, sx, sy)
        time.sleep(0.05)

        # 移动到起点并按下
        mouse_down(hwnd, sx, sy)
        time.sleep(0.05 + random.random() * 0.05)

        # 逐步移动鼠标（使用 --window 相对坐标）
        for i in range(steps + 1):
            cx = int(sx + delta_x * i)
            cy = int(sy + delta_y * i)
            _move_pointer(hwnd, cx, cy)
            time.sleep(sleep_time)

        time.sleep(0.3)
        mouse_up(hwnd, ex, ey)
        time.sleep(0.3)

        return True

    except Exception as e:
        raise Exception(f"拖拽失败：{str(e)}")


if __name__ == "__main__":
    # 测试函数：需要先运行main.py获取hwnd
    from .game_window import find_game_window

    try:
        hwnd = find_game_window()
        if not hwnd:
            print("未找到游戏窗口")
            exit(1)
        print(f"成功连接游戏窗口，句柄: {hwnd}")

        print("测试拖拽...")
        mouse_swipe(hwnd, 460, 270, 460, 340)  # 镜牢选路复位
        print("拖拽测试完成")

    except Exception as e:
        print(f"拖拽测试失败: {str(e)}")