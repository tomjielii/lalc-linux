"""
使用 X11 XSendEvent 发送输入事件，物理鼠标完全不移动。

原理：XSendEvent 直接将构造好的事件发给目标窗口，
不经过指针 warp（不像 xdotool 底层走 XTest 会先挪指针）。
这等效于 Win32 的 PostMessage。

适用于 Linux (X11 / XWayland)，无需额外依赖（只需系统自带的 libX11.so.6）。
"""

import ctypes
import time
import random

# ── 加载 libX11 ──────────────────────────────────────────────
_lib = ctypes.cdll.LoadLibrary("libX11.so.6")

# ── X11 类型 ─────────────────────────────────────────────────
Display = ctypes.c_void_p
Window = ctypes.c_ulong
Bool = ctypes.c_int

# ── 事件常量（X.h） ──────────────────────────────────────────
ButtonPress = 4
ButtonRelease = 5
KeyPress = 2
KeyRelease = 3

ButtonPressMask = 1 << 2
ButtonReleaseMask = 1 << 3
KeyPressMask = 1 << 0
KeyReleaseMask = 1 << 1
NoEventMask = 0

# ── Keysym 常量（keysymdef.h） ────────────────────────────────
# 可打印字符用 ASCII 值；控制键用 X11 定义的符号
XK_Return = 0xFF0D
XK_Escape = 0xFF1B
XK_BackSpace = 0xFF08
XK_Tab = 0xFF09
XK_space = 0x0020
XK_Shift_L = 0xFFE1
XK_Shift_R = 0xFFE2
XK_Control_L = 0xFFE3
XK_Control_R = 0xFFE4
XK_Alt_L = 0xFFE9
XK_Alt_R = 0xFFEA
XK_Super_L = 0xFFEB
XK_Super_R = 0xFFEC
XK_Caps_Lock = 0xFFE5
XK_Delete = 0xFFFF

_KEYSYM_MAP: dict[str, int] = {
    "enter": XK_Return,
    "return": XK_Return,
    "esc": XK_Escape,
    "escape": XK_Escape,
    "backspace": XK_BackSpace,
    "tab": XK_Tab,
    "space": XK_space,
    "shift": XK_Shift_L,
    "shift_l": XK_Shift_L,
    "shift_r": XK_Shift_R,
    "ctrl": XK_Control_L,
    "ctrl_l": XK_Control_L,
    "ctrl_r": XK_Control_R,
    "alt": XK_Alt_L,
    "alt_l": XK_Alt_L,
    "alt_r": XK_Alt_R,
    "super": XK_Super_L,
    "super_l": XK_Super_L,
    "super_r": XK_Super_R,
    "cmd": XK_Super_L,
    "win": XK_Super_L,
    "caps_lock": XK_Caps_Lock,
    "delete": XK_Delete,
}


def _resolve_keysym(key: str) -> int:
    """将键名字符串转为 X11 Keysym 值。"""
    s = key.lower()
    if s in _KEYSYM_MAP:
        return _KEYSYM_MAP[s]
    # 单个字符：用 ASCII 码
    if len(s) == 1:
        return ord(s)
    raise ValueError(f"未知的键名: {key}")


# ── X11 函数签名 ──────────────────────────────────────────────
_lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
_lib.XOpenDisplay.restype = Display

_lib.XDefaultRootWindow.argtypes = [Display]
_lib.XDefaultRootWindow.restype = Window

_lib.XKeysymToKeycode.argtypes = [Display, ctypes.c_ulong]
_lib.XKeysymToKeycode.restype = ctypes.c_ubyte  # KeyCode

_lib.XSendEvent.argtypes = [
    Display, Window, Bool, ctypes.c_long, ctypes.c_void_p
]
_lib.XSendEvent.restype = ctypes.c_int  # Status

_lib.XFlush.argtypes = [Display]
_lib.XFlush.restype = ctypes.c_int

_lib.XCloseDisplay.argtypes = [Display]
_lib.XCloseDisplay.restype = None

# ── X11 事件结构体定义 ────────────────────────────────────────
# 布局与 C 语言 X11/Xlib.h 一致（x86-64 Linux, GCC 默认对齐）


class XAnyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", Bool),
        ("display", Display),
        ("window", Window),
    ]


class XButtonEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", Bool),
        ("display", Display),
        ("window", Window),
        ("root", Window),
        ("subwindow", Window),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("button", ctypes.c_uint),
        ("same_screen", Bool),
    ]


class XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", Bool),
        ("display", Display),
        ("window", Window),
        ("root", Window),
        ("subwindow", Window),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", Bool),
    ]


# XEvent union: 在 64-bit 上 pad[24] 使大小为 192 字节
class XEvent(ctypes.Structure):
    _fields_ = [("pad", ctypes.c_long * 24)]


def _build_xevent(
    display: int, window: int, root: int, event_type: int,
    x: int = 0, y: int = 0, button_or_keycode: int = 0,
    state: int = 0,
) -> XEvent:
    """构造一个 XEvent 并填充通用字段。"""
    ev = XEvent()
    ctypes.memset(ctypes.addressof(ev), 0, ctypes.sizeof(ev))

    # 通过 XAnyEvent 写前 5 个公共字段
    any_ev = XAnyEvent.from_buffer(ev)
    any_ev.type = event_type
    any_ev.send_event = False  # 不标记为合成事件，避免 Wine 特殊处理
    any_ev.display = display
    any_ev.window = window

    if event_type in (ButtonPress, ButtonRelease):
        be = XButtonEvent.from_buffer(ev)
        be.root = root
        be.x = x
        be.y = y
        be.x_root = x  # 近似值，实际不重要
        be.y_root = y
        be.button = button_or_keycode
        be.same_screen = True
    elif event_type in (KeyPress, KeyRelease):
        ke = XKeyEvent.from_buffer(ev)
        ke.root = root
        ke.x = x
        ke.y = y
        ke.x_root = x
        ke.y_root = y
        ke.keycode = button_or_keycode
        ke.same_screen = True

    return ev


# ── 全局 Display 连接（单例） ────────────────────────────────
_display: int | None = None  # Display* 指针
_root: int = 0


def _ensure_display():
    """确保 Display 已打开。"""
    global _display, _root
    if _display is not None:
        return
    _display = _lib.XOpenDisplay(None)
    if not _display:
        raise RuntimeError("无法打开 X11 Display（XOpenDisplay 返回 NULL）")
    _root = _lib.XDefaultRootWindow(_display)


def take_screenshot_x11(hwnd: str) -> "Image.Image":
    """
    使用 XGetImage 截取指定窗口的内容，不激活窗口、不移动鼠标。
    返回 PIL Image（RGBA 模式）。
    """
    from PIL import Image as _PILImage
    import numpy as _np

    _ensure_display()
    wid = int(hwnd)

    # 用 xdotool 获取窗口尺寸（纯读取，不抢焦点）
    import subprocess as _sp, re as _re
    r = _sp.run(
        ["xdotool", "getwindowgeometry", hwnd],
        capture_output=True, text=True, timeout=5
    )
    m = _re.search(r"Geometry: (\d+)x(\d+)", r.stdout)
    if not m:
        raise RuntimeError(f"无法获取窗口尺寸: {r.stdout}")
    w, h = int(m.group(1)), int(m.group(2))

    # XGetImage: 获取窗口像素数据
    _lib.XGetImage.argtypes = [
        Display, Window, ctypes.c_int, ctypes.c_int,
        ctypes.c_uint, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int
    ]
    _lib.XGetImage.restype = ctypes.c_void_p

    img_ptr = _lib.XGetImage(_display, wid, 0, 0, w, h, 0xFFFFFFFFFFFFFFFF, 2)  # ZPixmap
    if not img_ptr:
        raise RuntimeError("XGetImage 失败")

    # 读取 bytes_per_line 和 depth（XImage 结构体前 5 个 int + 1 个指针后的字段）
    depth = ctypes.c_int.from_address(img_ptr + 9 * 8)  # 偏移: 5*4(ints)+padding? 
    bpl = ctypes.c_int.from_address(img_ptr + 8 * 8)
    data_ptr = ctypes.c_void_p.from_address(img_ptr + 4 * 8)

    # 更可靠的方式: 逐字段读取
    # XImage struct: width(int), height(int), xoffset(int), format(int),
    #                data(char*), byte_order(int), bitmap_unit(int),
    #                bitmap_bit_order(int), bitmap_pad(int), depth(int),
    #                bytes_per_line(int), bits_per_pixel(int), ...
    fields = [
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("xoffset", ctypes.c_int),
        ("format", ctypes.c_int),
        ("data", ctypes.c_void_p),
        ("byte_order", ctypes.c_int),
        ("bitmap_unit", ctypes.c_int),
        ("bitmap_bit_order", ctypes.c_int),
        ("bitmap_pad", ctypes.c_int),
        ("depth", ctypes.c_int),
        ("bytes_per_line", ctypes.c_int),
        ("bits_per_pixel", ctypes.c_int),
    ]
    class XImageStruct(ctypes.Structure):
        _fields_ = fields  # type: ignore

    ximg = XImageStruct.from_address(img_ptr)
    buf = (ctypes.c_ubyte * (ximg.height * ximg.bytes_per_line)).from_address(ximg.data)

    # 根据 bits_per_pixel 转为 PIL Image
    if ximg.bits_per_pixel == 32:
        arr = _np.frombuffer(buf, dtype=_np.uint8).reshape(ximg.height, ximg.bytes_per_line)
        arr = arr[:, :ximg.width * 4].reshape(ximg.height, ximg.width, 4)
        # X11 默认 BGRA → RGBA
        pil_img = _PILImage.fromarray(arr[:, :, [2, 1, 0, 3]], "RGBA")
    elif ximg.bits_per_pixel == 24:
        arr = _np.frombuffer(buf, dtype=_np.uint8).reshape(ximg.height, ximg.bytes_per_line)
        arr = arr[:, :ximg.width * 3].reshape(ximg.height, ximg.width, 3)
        pil_img = _PILImage.fromarray(arr[:, :, [2, 1, 0]], "RGB")
    else:
        arr = _np.frombuffer(buf, dtype=_np.uint8).reshape(ximg.height, ximg.bytes_per_line)
        pil_img = _PILImage.fromarray(arr, "L")

    # 释放 XImage
    _lib.XDestroyImage.argtypes = [ctypes.c_void_p]
    _lib.XDestroyImage(img_ptr)

    return pil_img


# ── 公开 API ──────────────────────────────────────────────────


def send_click(hwnd: str, x: int, y: int, button: int = 1):
    """
    向指定窗口发送鼠标点击（按下+释放），物理鼠标不移动。

    :param hwnd: X11 窗口 ID
    :param x: 窗口内坐标 x
    :param y: 窗口内坐标 y
    :param button: 1=左键, 2=中键, 3=右键
    """
    _ensure_display()
    wid = int(hwnd)

    mask = ButtonPressMask | ButtonReleaseMask

    ev_press = _build_xevent(
        _display, wid, _root, ButtonPress,
        x=x, y=y, button_or_keycode=button,
    )
    _lib.XSendEvent(_display, wid, 0, mask, ctypes.byref(ev_press))

    ev_release = _build_xevent(
        _display, wid, _root, ButtonRelease,
        x=x, y=y, button_or_keycode=button,
    )
    _lib.XSendEvent(_display, wid, 0, mask, ctypes.byref(ev_release))

    _lib.XFlush(_display)


def send_mouse_down(hwnd: str, x: int, y: int, button: int = 1):
    """
    向指定窗口发送鼠标按下，物理鼠标不移动。
    """
    _ensure_display()

    ev = _build_xevent(
        _display, int(hwnd), _root, ButtonPress,
        x=x, y=y, button_or_keycode=button,
    )
    _lib.XSendEvent(_display, int(hwnd), 0, ButtonPressMask, ctypes.byref(ev))
    _lib.XFlush(_display)


def send_mouse_up(hwnd: str, x: int, y: int, button: int = 1):
    """
    向指定窗口发送鼠标释放，物理鼠标不移动。
    """
    _ensure_display()

    ev = _build_xevent(
        _display, int(hwnd), _root, ButtonRelease,
        x=x, y=y, button_or_keycode=button,
    )
    _lib.XSendEvent(_display, int(hwnd), 0, ButtonReleaseMask, ctypes.byref(ev))
    _lib.XFlush(_display)


def send_mouse_move(hwnd: str, x: int, y: int):
    """
    ⚠️ 注意: XSendEvent 不支持 MotionNotify 带坐标直接发送（Unity 可能忽略）。
    这里改用 xdotool mousemove --window 作为 fallback。
    """
    # 回退到 xdotool（带 --window），至少坐标不会溢出到其他窗口
    import subprocess
    subprocess.run(
        ["xdotool", "mousemove", "--window", hwnd, str(int(x)), str(int(y))],
        capture_output=True, text=True,
    )


def send_key(hwnd: str, key: str):
    """
    向指定窗口发送按键（按下+释放），物理鼠标不移动。

    :param hwnd: X11 窗口 ID
    :param key: 键名（如 'p', 'enter', 'esc', 'space'）
    """
    _ensure_display()
    wid = int(hwnd)
    keysym = _resolve_keysym(key)
    keycode = _lib.XKeysymToKeycode(_display, keysym)
    if not keycode:
        raise ValueError(f"无法将键 '{key}' (keysym={keysym:#x}) 转为 keycode")

    mask = KeyPressMask | KeyReleaseMask

    ev_press = _build_xevent(
        _display, wid, _root, KeyPress,
        button_or_keycode=keycode,
    )
    _lib.XSendEvent(_display, wid, 0, mask, ctypes.byref(ev_press))

    ev_release = _build_xevent(
        _display, wid, _root, KeyRelease,
        button_or_keycode=keycode,
    )
    _lib.XSendEvent(_display, wid, 0, mask, ctypes.byref(ev_release))

    _lib.XFlush(_display)


def send_key_down(hwnd: str, key: str):
    """向指定窗口发送按键按下（不释放），物理鼠标不移动。"""
    _ensure_display()
    wid = int(hwnd)
    keysym = _resolve_keysym(key)
    keycode = _lib.XKeysymToKeycode(_display, keysym)
    if not keycode:
        raise ValueError(f"无法将键 '{key}' (keysym={keysym:#x}) 转为 keycode")

    ev = _build_xevent(
        _display, wid, _root, KeyPress,
        button_or_keycode=keycode,
    )
    _lib.XSendEvent(_display, wid, 0, KeyPressMask, ctypes.byref(ev))
    _lib.XFlush(_display)


def send_key_up(hwnd: str, key: str):
    """向指定窗口发送按键释放，物理鼠标不移动。"""
    _ensure_display()
    wid = int(hwnd)
    keysym = _resolve_keysym(key)
    keycode = _lib.XKeysymToKeycode(_display, keysym)
    if not keycode:
        raise ValueError(f"无法将键 '{key}' (keysym={keysym:#x}) 转为 keycode")

    ev = _build_xevent(
        _display, wid, _root, KeyRelease,
        button_or_keycode=keycode,
    )
    _lib.XSendEvent(_display, wid, 0, KeyReleaseMask, ctypes.byref(ev))
    _lib.XFlush(_display)
