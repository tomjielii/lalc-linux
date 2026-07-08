import os
import signal
import subprocess
import time
import re
from utils.logger import init_logger


logger = init_logger()


def is_window(hwnd):
    """
    校验窗口 ID 是否有效
    :param hwnd: X11 window ID
    :return: True 有效, False 无效
    """
    r = subprocess.run(["xdotool", "getwindowgeometry", hwnd],
                       capture_output=True, text=True)
    return r.returncode == 0


def focus_window(hwnd):
    """
    将窗口切到前台并给予输入焦点
    :param hwnd: X11 window ID
    :return: True 成功, False 失败
    """
    if not is_window(hwnd):
        return False

    # 如果窗口被最小化，先恢复显示
    subprocess.run(["xdotool", "windowmap", hwnd],
                   capture_output=True, text=True)
    time.sleep(0.1)

    # 没有前后台概念
    subprocess.run(["xdotool", "windowfocus", hwnd],
                   capture_output=True, text=True)
    time.sleep(0.1)
    return True


def find_game_window(window_title="LimbusCompany", window_class="steam"):
    # 第1层：按标题搜
    result = subprocess.run(
        ["xdotool", "search", "--name", window_title],
        capture_output=True, text=True
    )
    if not result.stdout.strip():
        return None

    # 第2层：遍历结果，确认类名包含 "steam"
    for wid in result.stdout.strip().split("\n"):
        cls = subprocess.run(
            ["xdotool", "getwindowclassname", wid],
            capture_output=True, text=True
        ).stdout.strip()
        if window_class in cls:
            return wid

    return None  # 两层都没找到，返回 None


def set_window_to_top(hwnd, client_width=1280, client_height=720):
    """
    将窗口移动到屏幕左上角并设置指定大小
    :param hwnd: X11 window ID
    :param client_width: 窗口宽度, 默认1280
    :param client_height: 窗口高度, 默认720
    """
    if not is_window(hwnd):
        return

    subprocess.run(
        ["xdotool", "windowmove", hwnd, "0", "0"],
        capture_output=True, text=True
    )
    subprocess.run(
        ["xdotool", "windowsize", hwnd, str(client_width), str(client_height)],
        capture_output=True, text=True
    )


def set_window_size(hwnd, width=1280, height=720):
    """
    设置窗口大小
    :param hwnd: X11 window ID
    :param width: 窗口宽度
    :param height: 窗口高度
    """
    if not is_window(hwnd):
        return
    subprocess.run(
        ["xdotool", "windowsize", hwnd, str(width), str(height)],
        capture_output=True, text=True
    )


def set_window_position(hwnd, x, y):
    """
    设置窗口位置
    :param hwnd: X11 window ID
    :param x: 窗口左上角x坐标
    :param y: 窗口左上角y坐标
    """
    if not is_window(hwnd):
        return
    subprocess.run(
        ["xdotool", "windowmove", hwnd, str(x), str(y)],
        capture_output=True, text=True
    )


def get_window_size(hwnd):
    """
    获取当前窗口大小
    :param hwnd: X11 window ID
    :return: (width, height) 元组，无效窗口返回 None
    """
    if not is_window(hwnd):
        return None

    r = subprocess.run(
        ["xdotool", "getwindowgeometry", hwnd],
        capture_output=True, text=True
    )
    m = re.search(r"Geometry: (\d+)x(\d+)", r.stdout)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


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


def close_window(hwnd):
    """
    关闭指定窗口
    :param hwnd: 窗口句柄
    """
    if not is_window(hwnd):
        return False

    subprocess.run(["xdotool", "windowclose", hwnd],
                   capture_output=True, text=True)
    return True


def request_limbus_process_exit(timeout: float = 20):
    """
    请求 LimbusCompany 进程退出。
    向进程发送 SIGTERM（礼貌的终止请求），然后等待它自行退出。
    超时后不强制 kill，仅打日志警告。
    :param timeout: 发送 SIGTERM 后最大等待秒数
    :return: True 进程已退出, False 超时后进程仍在
    """
    patterns = ["LimbusCompany", "LimbusCompany.exe"]
    found_any = False

    # 先发 SIGTERM 请求退出
    for pat in patterns:
        try:
            r = subprocess.run(
                ["pgrep", "-f", pat],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0 or not r.stdout.strip():
                continue

            pids = r.stdout.strip().split()
            for pid in pids:
                logger.info(f"请求 LimbusCompany 进程 (PID: {pid}) 退出")
                os.kill(int(pid), signal.SIGTERM)
                found_any = True
        except subprocess.TimeoutExpired:
            logger.warning(f"查找进程 {pat} 超时")
        except Exception as e:
            logger.error(f"请求进程 {pat} 退出时出错: {str(e)}")

    if not found_any:
        logger.info("未发现 LimbusCompany 进程运行")
        return True

    # 等待进程退出
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        still_alive = False
        for pat in patterns:
            r = subprocess.run(
                ["pgrep", "-f", pat],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout.strip():
                still_alive = True
                break
        if not still_alive:
            logger.info("LimbusCompany 进程已退出")
            return True

    logger.warning(f"发送退出请求后 {timeout}s 进程仍未退出，请手动检查")
    return False


def close_limbus_window(window_title="LimbusCompany", window_class="steam"):
    """
    关闭LimbusCompany游戏窗口
    :param window_title: 窗口标题
    :param window_class: 窗口类名
    :return: 是否成功关闭窗口
    """
    try:
        hwnd = find_game_window(window_title, window_class)
        if not hwnd:
            logger.info("未找到LimbusCompany窗口")
            return True

        logger.info("正在关闭LimbusCompany窗口")
        close_window(hwnd)

        # 等待窗口关闭
        timeout = 5
        while timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
            if not is_window(hwnd):
                logger.info("LimbusCompany窗口已关闭")
                return True

        logger.warning("关闭LimbusCompany窗口超时")
        return False
    except Exception as e:
        logger.error(f"关闭LimbusCompany窗口时出错: {str(e)}")
        return False


if __name__ == "__main__":

    # 查找游戏窗口
    hwnd = find_game_window()
    
    if not hwnd:
        print("未找到游戏窗口，请确保游戏正在运行")
        exit(-1)
    
    print(f"找到游戏窗口，句柄: {hwnd}")

    close_limbus_window()

    request_limbus_process_exit()