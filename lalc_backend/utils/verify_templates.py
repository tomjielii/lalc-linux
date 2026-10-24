"""
离线验证主题包模板识别：拿 logs/ 里已保存的真实选卡包帧回放 template_match，
不需要开游戏、不需要 DISPLAY。

用法（在 lalc_backend/ 下）：
  # 用某次 run 的日志自动提取选卡包帧，测 4 个新包 + 2 个对照组
  .venv/bin/python verify_templates.py --log logs/<时间>/run.log --new-packs

  # 全量主题包都测（慢一些）
  .venv/bin/python verify_templates.py --log logs/<时间>/run.log --all-packs

  # 指定帧和模板
  .venv/bin/python verify_templates.py --frames "logs/<时间>/images/*.png" \
      --templates "Storefront Campout,An Anarchy of Colors"

说明：
- 帧来自 DEBUG 日志，是 640×360 的缩放图；脚本会放大回 1280×720 再匹配，
  属于保守测试：半分辨率回放能过 0.8 的，实机必然能过。
- 对照组是实机已识别到的旧包（Flat-broke Gamblers / Nest, Workshop, and Technology），
  用来验证回放链路本身没问题：对照组过不了阈值说明帧或链路有问题，结论作废。
- 星光页（mirror_choose_star）是纯坐标点击，不做模板识别，不在此脚本范围内。
- 本脚本不写 logs/、不触发 LALCLogger 的历史目录清理（在导入 recognize 前已接管）。
"""

import argparse
import glob
import logging
import re
import sys
import tempfile
from pathlib import Path

# ── 必须在导入 recognize 之前接管 LALCLogger ──────────────────────────────
# 原版 LALCLogger.__init__ 会在 logs/ 下新建目录，并把历史目录清理到只剩 3 个，
# 离线工具绝不能触发这个副作用。
import utils.logger as _ul


def _offline_init(self, retain_folder_count: int = 3):
    self.logger = logging.getLogger("lalc_logger")
    self.log_dir = Path(tempfile.mkdtemp(prefix="lalc_verify_"))


_ul.LALCLogger.__init__ = _offline_init
_ul.LALCLogger._clean_old_folders = lambda self, keep: None
# ──────────────────────────────────────────────────────────────────────────

from PIL import Image  # noqa: E402

from recognize.img_recognizer import recognize_handler  # noqa: E402
from recognize.img_registry import get_images_by_tag, get_image  # noqa: E402
from utils.logger import init_logger  # noqa: E402

# 生产参数：task_action/mirror.py exec_mirror_theme_pack
PROD_MASK_TEMPLATE = [20, 20, 130, 290]
PROD_THRESHOLD = 0.8
PROBE_THRESHOLD = 0.3  # 探测用低阈值，只为了拿最高分，不影响判定

NEW_PACKS = [
    "Storefront Campout",
    "An Anarchy of Colors",
    "Creed of Preservation",
    "Readvent of Gluttony",
]
CONTROL_PACKS = [
    "Flat-broke Gamblers",
    "Nest, Workshop, and Technology",
]

# 选卡包帧的日志特征：卡包模板匹配固定使用 [20, 20, 130, 290] 裁剪
PACK_SCREEN_MARK = "截取模板图片[20, 20, 130, 290]"
IMAGE_RE = re.compile(r"IMAGE:(images/\S+?\.png)")


def extract_frames_from_log(log_path: str, limit: int):
    frames = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            if PACK_SCREEN_MARK not in line:
                continue
            m = IMAGE_RE.search(line)
            if m:
                frames.append(m.group(1))
    # 去重保序
    seen = set()
    uniq = [f for f in frames if not (f in seen or seen.add(f))]
    if limit and len(uniq) > limit:
        step = len(uniq) / limit
        uniq = [uniq[int(i * step)] for i in range(limit)]
    return uniq


def load_frame(path: str) -> Image.Image:
    im = Image.open(path).convert("RGB")
    if im.size != (1280, 720):
        im = im.resize((1280, 720), Image.LANCZOS)
    return im


def best_score(frame: Image.Image, template: str):
    res = recognize_handler.template_match(
        frame, template, threshold=PROBE_THRESHOLD,
        mask_template=PROD_MASK_TEMPLATE,
    )
    if not res:
        return None
    return max(r[2] for r in res)


def main():
    global PROBE_THRESHOLD
    ap = argparse.ArgumentParser(description="离线回放主题包模板匹配")
    ap.add_argument("--log", help="run.log 路径，自动提取选卡包帧")
    ap.add_argument("--frames", help="帧的 glob，与 --log 二选一")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--new-packs", action="store_true", help="4 个新包 + 2 个对照组")
    g.add_argument("--all-packs", action="store_true", help="全部主题包模板")
    g.add_argument("--templates", help="逗号分隔的模板名")
    ap.add_argument("--threshold", type=float, default=PROD_THRESHOLD)
    ap.add_argument("--probe", type=float, default=PROBE_THRESHOLD)
    ap.add_argument("--limit", type=int, default=60, help="最多回放的帧数")
    args = ap.parse_args()

    PROBE_THRESHOLD = args.probe

    # 静音 debug 日志，避免探测命中时往磁盘写图
    lg = init_logger()
    lg.debug = lambda msg="", image=None, task_name=None, compress_image=True: None

    if not args.log and not args.frames:
        ap.error("需要 --log 或 --frames 之一")

    if args.frames:
        frames = sorted(glob.glob(args.frames))
    else:
        frames = extract_frames_from_log(args.log, args.limit)
        base = args.log.rsplit("/", 1)[0] if "/" in args.log else "."
        frames = [f"{base}/{p}" for p in frames]
    if not frames:
        print("没有找到可回放的帧")
        sys.exit(1)
    print(f"回放帧数：{len(frames)}（首帧 {frames[0]}）")

    if args.all_packs:
        templates = [x[0] for x in get_images_by_tag("theme_packs")]
    elif args.templates:
        templates = [t.strip() for t in args.templates.split(",")]
    else:
        templates = NEW_PACKS + CONTROL_PACKS

    results = []
    for i, tp in enumerate(templates):
        best, best_frame, n_pass = None, None, 0
        for fp in frames:
            try:
                s = best_score(load_frame(fp), tp)
            except Exception as e:
                print(f"  帧读取失败 {fp}: {e}")
                continue
            if s is not None and (best is None or s > best):
                best, best_frame = s, fp
            if s is not None and s >= args.threshold:
                n_pass += 1
        results.append((tp, best, best_frame, n_pass))
        score_str = "n/a" if best is None else f"{best:.3f}"
        print(f"  [{i + 1}/{len(templates)}] {tp}: 最高分 {score_str}"
              f"（阈值 {args.threshold}，达标帧 {n_pass}/{len(frames)}）")

    print("\n===== 汇总（按最高分升序） =====")
    def sort_key(r):
        return (r[1] is not None, r[1] if r[1] is not None else 0)
    for tp, best, best_frame, n_pass in sorted(results, key=sort_key):
        if best is None:
            verdict = "全程无候选（模板可能没注册或尺寸异常）"
        elif best >= args.threshold:
            verdict = f"可识别（出现在 {n_pass} 帧）"
        else:
            verdict = "历史帧中未出现/未达阈值"
        score_str = "-1" if best is None else f"{best:.3f}"
        print(f"{score_str}  {tp}  <- {best_frame or '-'}  {verdict}")


if __name__ == "__main__":
    main()
