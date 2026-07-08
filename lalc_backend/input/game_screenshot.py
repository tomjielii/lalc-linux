import subprocess
from io import BytesIO
import time
from PIL import Image

from .game_window import is_window, get_window_size
from .x11_input import take_screenshot_x11


def _get_logical_client_rect(hwnd):
    """
    获取窗口尺寸
    :param hwnd: X11 window ID
    :return: (width, height)
    """
    return get_window_size(hwnd)


def take_screenshot(hwnd, width=None, height=None, save_path=None):
    """
    对游戏窗口进行截图
    使用 X11 XGetImage 捕获指定窗口，不激活窗口、不移动鼠标。
    :param hwnd: X11 window ID
    :param width: 忽略（自动获取）
    :param height: 忽略（自动获取）
    :param save_path: 保存路径（None则不保存）
    :return: PIL.Image对象
    """
    if not is_window(hwnd):
        raise Exception(f"无效窗口句柄: {hwnd}")

    pil_img = take_screenshot_x11(hwnd)

    if save_path:
        pil_img.save(save_path)

    return pil_img


def performance_test(hwnd, save_image=False, count=100):
    """
    对截图功能进行性能测试
    :param hwnd: X11 window ID
    :param save_image: 是否保存图片
    :param count: 测试次数
    :return: (total_time, avg_time)
    """
    print(f"开始性能测试: 连续截图{count}次, 保存图片: {save_image}")

    start_time = time.time()
    for i in range(count):
        take_screenshot(hwnd, save_path="screenshot_test.png" if save_image else None)
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / count
    print(f"  总耗时: {total_time:.2f}s  平均: {avg_time:.4f}s  FPS: {1/avg_time:.1f}")
    return total_time, avg_time


if __name__ == "__main__":
    import os
    from .game_window import find_game_window

    os.makedirs("test_output", exist_ok=True)

    hwnd = find_game_window()
    if not hwnd:
        print("未找到游戏窗口"); exit(1)
    print(f"窗口句柄: {hwnd}")

    save_path = "test_output/screenshot_test.png"
    img = take_screenshot(hwnd, save_path=save_path)
    print(f"截图成功: {img.size[0]}x{img.size[1]} → {save_path}")

    # 性能测试（取消注释即可运行）
    # performance_test(hwnd, save_image=False, count=50)
