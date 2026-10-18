import subprocess
import os
import tempfile
from io import BytesIO
import time
from PIL import Image

from .game_window import is_window, get_window_size
from .x11_input import take_screenshot_x11


# 抓帧后端：x11（默认，XGetImage 读窗口）或 gamescope（gamescopectl 读合成输出）。
# gamescope 后端用在游戏跑在 gamescope 私有 X 服务器时：XGetImage 在那种环境里
# 只能读到全黑的窗口备份，必须改从 gamescope 自己的输出取帧。
CAPTURE_BACKEND = os.environ.get("LALC_CAPTURE", "x11").lower()


def _take_screenshot_gamescope(save_path=None):
    """
    通过 gamescopectl 抓 gamescope 的合成输出（全输出分辨率，无窗口边框）。
    不经过 X，不受窗口可见性影响。
    """
    fd, tmp = tempfile.mkstemp(suffix=".png", prefix="lalc_gs_")
    os.close(fd)
    try:
        r = subprocess.run(
            ["gamescopectl", "screenshot", tmp],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            raise RuntimeError(f"gamescopectl 抓帧失败: {r.stderr.strip() or r.stdout.strip()}")

        # gamescopectl 只是请求，文件由 gamescope 在下一帧写出，需要等它落地
        img = None
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                img = Image.open(tmp)
                img.load()
                break
            except Exception:
                img = None
                time.sleep(0.05)
        if img is None:
            raise RuntimeError("gamescopectl 写出的截图文件超时未就绪")

        if save_path:
            img.save(save_path)
        return img
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


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
    默认使用 X11 XGetImage 捕获指定窗口，不激活窗口、不移动鼠标。
    设置 LALC_CAPTURE=gamescope 时改用 gamescopectl 抓 gamescope 的输出。
    :param hwnd: X11 window ID
    :param width: 忽略（自动获取）
    :param height: 忽略（自动获取）
    :param save_path: 保存路径（None则不保存）
    :return: PIL.Image对象
    """
    if CAPTURE_BACKEND == "gamescope":
        return _take_screenshot_gamescope(save_path)

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
