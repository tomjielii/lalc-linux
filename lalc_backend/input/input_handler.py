import copy
import subprocess
import time
import threading

from .game_window import (
    find_game_window,
    set_window_size,
    set_window_position,
    set_window_to_top,
    focus_window,
    get_window_size,
    close_window,
    close_limbus_window,
)
from .game_click import get_cursor_pos
from .game_screenshot import take_screenshot
from .game_click import mouse_click, mouse_down, mouse_up
from .game_keyboard import key_press
from .game_swipe import mouse_swipe
from .idle_monitor import wait_input_idle
from utils.logger import init_logger


logger = init_logger()


# 状态接口定义各类操作的行为
class InputState:
    """输入状态抽象类"""

    def click(self, hwnd, x, y):
        raise NotImplementedError

    def long_press(self, hwnd, x, y, duration):
        raise NotImplementedError

    def key_press(self, hwnd, key):
        raise NotImplementedError

    def swipe(self, hwnd, start_x, start_y, end_x, end_y):
        raise NotImplementedError

    def set_focus(self, hwnd):
        raise NotImplementedError


class ActiveInputState(InputState):
    """输入状态（Linux 下前后台无区别，统一为一个实现）"""

    def click(self, hwnd, x, y):
        return mouse_click(hwnd, x, y)

    def long_press(self, hwnd, x, y, duration=3):
        return mouse_long_press(hwnd, x, y, duration)

    def key_press(self, hwnd, key):
        return key_press(hwnd, key)

    def swipe(self, hwnd, start_x, start_y, end_x, end_y):
        return mouse_swipe(hwnd, start_x, start_y, end_x, end_y)

    def set_focus(self, hwnd):
        return focus_window(hwnd)


DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 720


class _Input:
    _singleton = None  # 保存唯一实例，供 wait_input_idle 访问

    def __init__(self):
        if _Input._singleton is None:
            _Input._singleton = self

        self._hwnd = None
        self._state = ActiveInputState()

        self._screenshot = None
        self._width = 0
        self._height = 0

        self._pause_flag = threading.Event()
        self._stop_flag = threading.Event()
        self._pause_flag.set()

    def reset_mouse_position(self):
        if self._hwnd:
            w, h = get_window_size(self._hwnd)
            if w is not None:
                subprocess.run(
                    ["xdotool", "mousemove", "--window", self._hwnd, str(w + 10), str(-5)],
                    capture_output=True, text=True
                )

    # 与任务流水线同步
    def pause(self):
        self._pause_flag.clear()
        logger.debug("InputHandler 已暂停")

    def resume(self):
        self._pause_flag.set()
        logger.debug("InputHandler 已恢复")

    def stop(self):
        self._stop_flag.set()
        self.resume()  # 若正在暂停，先解开
        logger.debug("InputHandler 已停止")

    def reset(self):
        self._pause_flag.set()
        self._stop_flag.clear()
        self.refresh_window_state()
        logger.debug("InputHandler 已重置到初始状态")

    def refresh_window_state(self):
        """
        刷新窗口句柄并更新相关属性。
        """
        self._hwnd = find_game_window()
        self._update_window_size()

    def _update_window_size(self):
        if self._hwnd:
            self._width, self._height = get_window_size(self._hwnd)

    @property
    def screenshot(self):
        return copy.copy(self._screenshot)  # 获取时返回副本

    @screenshot.setter
    def screenshot(self, value):
        self._screenshot = value  # 修改时直接设置

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def open_limbus(self):
        self.refresh_window_state()
        if not self._hwnd:
            logger.info("未找到游戏窗口，尝试自动打开游戏，随后等待 30 秒")
            subprocess.Popen(["steam", "steam://rungameid/1973530"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(30)
            self.refresh_window_state()
            if not self._hwnd:
                logger.warning("等待 30 秒后仍未找到游戏窗口")

    def capture_screenshot(self, reset=True, save_path=None):
        """
        截取游戏窗口屏幕并存储在screenshot属性中。
        """
        if self._hwnd:
            self.refresh_window_state()
            # 只在当前窗口大小与默认大小不同时才设置窗口大小
            if (
                self._width != DEFAULT_WINDOW_WIDTH
                or self._height != DEFAULT_WINDOW_HEIGHT
            ):
                self.set_window_size()

            self._screenshot = take_screenshot(
                self._hwnd, width=self.width, height=self.height, save_path=save_path
            )

            return self.screenshot
        else:
            raise Exception("hwnd init Error")

    def set_window_size(self, width=DEFAULT_WINDOW_WIDTH, height=DEFAULT_WINDOW_HEIGHT):
        """
        设置窗口尺寸为指定大小。
        注意：这需要实际调用窗口大小调整函数的实现。
        """
        # 检查当前窗口大小是否已经等于目标大小
        if self._width == width and self._height == height:
            logger.debug(f"窗口大小已经是 {width}x{height}，跳过设置")
            return

        self._width = width
        self._height = height
        if self._hwnd:
            set_window_size(self._hwnd, self._width, self._height)
            self.refresh_window_state()
        else:
            raise Exception("hwnd init Error")

    def set_window_position(self, x, y):
        """
        设置窗口位置为指定坐标。
        :param x: 窗口左上角x坐标
        :param y: 窗口左上角y坐标
        """
        if self._hwnd:
            set_window_position(self._hwnd, x, y)
        else:
            raise Exception("hwnd init Error")

    def set_window_to_top(self, client_width=1280, client_height=720):
        """
        将窗口客户区调整到屏幕顶部，并设置客户区大小
        :param client_width: 客户区宽度
        :param client_height: 客户区高度
        """
        if self._hwnd:
            set_window_to_top(self._hwnd, client_width, client_height)
            # 更新窗口尺寸信息
            self._update_window_size()
        else:
            raise Exception("hwnd init Error")

    def close_window(self):
        from .game_window import is_window
        if self._hwnd and is_window(self._hwnd):
            logger.debug("正在关闭游戏窗口")
            close_window(self._hwnd)
            time.sleep(0.5)
            self._hwnd = None
            self._width = 0
            self._height = 0
            logger.debug("游戏窗口已关闭")
            return True
        else:
            logger.debug("没有有效的窗口句柄，无法关闭窗口")
            return False

    def close_limbus_window(self):
        """
        关闭LimbusCompany游戏窗口
        """
        logger.info("尝试关闭LimbusCompany窗口")
        result = close_limbus_window()
        if result:
            # 清空hwnd
            self._hwnd = None
            self._width = 0
            self._height = 0
        return result

    def click(self, x, y):
        if self._stop_flag.is_set():
            return
        self._pause_flag.wait()
        if not self._hwnd:
            raise Exception("hwnd init Error")
        logger.debug(f"click ({x}, {y})")
        wait_input_idle()
        if self._stop_flag.is_set():
            return
        self._pause_flag.wait()
        return self._state.click(self._hwnd, x, y)

    def key_press(self, key):
        if self._stop_flag.is_set():
            return
        self._pause_flag.wait()
        if not self._hwnd:
            raise Exception("hwnd init Error")
        logger.debug(f"key_press '{key}'")
        return self._state.key_press(self._hwnd, key)

    def swipe(self, start_x, start_y, end_x, end_y):
        if self._stop_flag.is_set():
            return
        self._pause_flag.wait()
        if not self._hwnd:
            raise Exception("hwnd init Error")
        wait_input_idle()
        if self._stop_flag.is_set():
            return
        self._pause_flag.wait()
        logger.debug(f"swipe ({start_x},{start_y}) → ({end_x},{end_y})")
        return self._state.swipe(self._hwnd, start_x, start_y, end_x, end_y)

    def long_press(self, x, y, duration=3):
        if self._stop_flag.is_set():
            return
        self._pause_flag.wait()
        if not self._hwnd:
            raise Exception("hwnd init Error")
        logger.debug(f"long_press ({x},{y}) {duration}s")
        wait_input_idle()
        if self._stop_flag.is_set():
            return
        self._pause_flag.wait()
        return self._state.long_press(self._hwnd, x, y, duration)

    def set_focus(self) -> bool:
        if not self._hwnd:
            raise Exception("hwnd init Error")
        return self._state.set_focus(self._hwnd)


input_handler = _Input()

if __name__ == "__main__":
    import os
    from .game_window import find_game_window

    os.makedirs("test_output", exist_ok=True)

    game_input = input_handler
    game_input.refresh_window_state()
    game_input.set_window_size()

    print(f"窗口句柄: {game_input._hwnd}  尺寸: {game_input.width}x{game_input.height}")

    # 截图测试
    print("\n--- 截图 ---")
    save_path = "test_output/screenshot_test.png"
    img = game_input.capture_screenshot(save_path=save_path)
    print(f"  ✓ {img.size} → {save_path}")

    # 点击测试
    print("\n--- 点击 (12 罪人) ---")
    sinners = [
        (375, 340), (540, 340), (700, 340), (880, 340), (1030, 340), (1210, 340),
        (375, 590), (540, 590), (700, 590), (880, 590), (1030, 590), (1210, 590),
    ]
    for x, y in sinners:
        game_input.click(x, y)
    print("  ✓ 全部点击完成")

    # 键盘测试
    # game_input.key_press("esc")

    print("\n完成")
