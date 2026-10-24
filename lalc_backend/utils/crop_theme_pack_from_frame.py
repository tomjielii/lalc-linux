"""
从已保存的真实选卡包帧里裁剪主题包卡面，生成可直接放入 img/theme_packs/ 的模板。

用法（在 lalc_backend/ 下）：
  .venv/bin/python crop_theme_pack_from_frame.py --frame logs/<时间>/images/xxxx.png \
      --name "Storefront Campout" [--dry]

说明：
- 复用生产链路：theme_pack_detail 定位卡片 -> OCR 读卡包名 -> 按 x 距离关联 -> get_rect_from_center 裁 170x330。
- OCR 读错的名字（如 Storefront Campod）会用 difflib 近似匹配到 --name。
- 默认直接覆盖 img/theme_packs/<name>.png（原解包图在 git 里有备份，可随时 git checkout 恢复）；
  --dry 只显示裁剪结果不落盘。
- 不写 logs/、不触发 LALCLogger 的历史目录清理。
"""

import argparse
import difflib
import logging
import tempfile
from pathlib import Path

# ── 必须在导入 recognize 之前接管 LALCLogger（同 verify_templates.py）────────
import utils.logger as _ul


def _offline_init(self, retain_folder_count: int = 3):
    self.logger = logging.getLogger("lalc_logger")
    self.log_dir = Path(tempfile.mkdtemp(prefix="lalc_verify_"))


_ul.LALCLogger.__init__ = _offline_init
_ul.LALCLogger._clean_old_folders = lambda self, keep: None
# ──────────────────────────────────────────────────────────────────────────

from PIL import Image  # noqa: E402

from recognize.img_recognizer import recognize_handler  # noqa: E402
from recognize.rapid_ocr import detect_text_in_image  # noqa: E402
from utils.get_save_theme_packs import get_rect_from_center  # noqa: E402
from utils.logger import init_logger  # noqa: E402

OCR_MASK = [100, 440, 1100, 60]  # 生产参数：卡包名文字条


def load_frame(path: str) -> Image.Image:
    im = Image.open(path).convert("RGB")
    if im.size != (1280, 720):
        im = im.resize((1280, 720), Image.LANCZOS)
    return im


def main():
    ap = argparse.ArgumentParser(description="从真实帧裁剪主题包卡面")
    ap.add_argument("--frame", required=True, help="选卡包画面帧的路径")
    ap.add_argument("--name", required=True, help="目标卡包名（用于落盘文件名）")
    ap.add_argument("--dry", action="store_true", help="只看不保存")
    args = ap.parse_args()

    lg = init_logger()
    lg.debug = lambda msg="", image=None, task_name=None, compress_image=True: None

    frame = load_frame(args.frame)

    # 1. 定位画面上的卡片
    matches = recognize_handler.template_match(frame, "theme_pack_detail")
    if not matches:
        print("未检测到任何卡片（theme_pack_detail 无匹配）")
        raise SystemExit(1)

    # 2. OCR 读卡包名
    ocr_results = recognize_handler.detect_text_in_image(frame, mask=OCR_MASK)
    if not ocr_results:
        print("OCR 没有读到卡包名")
        raise SystemExit(1)
    print("OCR 结果:", [(t[0], t[1]) for t in ocr_results])

    # 3. 找目标名字（容忍 OCR 误读，如 Storefront Campod）
    target = None
    for text, cx, _, _ in ocr_results:
        if difflib.SequenceMatcher(None, text.lower(), args.name.lower()).ratio() > 0.75:
            target = (text, cx)
            break
    if target is None:
        close = difflib.get_close_matches(args.name, [t[0] for t in ocr_results], cutoff=0.6)
        print(f"OCR 结果里没有近似 {args.name!r} 的名字（近似候选：{close}）")
        raise SystemExit(1)
    print(f"目标：OCR 读到 {target[0]!r}（x={target[1]}），对应 {args.name}")

    # 4. 按 x 距离关联卡片
    best = min(matches, key=lambda m: abs(m[0] - target[1]))
    if abs(best[0] - target[1]) > 100:
        print(f"最近的卡片中心 x={best[0]}，与名字 x={target[1]} 距离超过 100，关联不可靠")
        raise SystemExit(1)

    # 5. 裁剪（与生产同款 170x330）
    x1, y1 = get_rect_from_center(best[0], best[1])[0]
    x2, y2 = get_rect_from_center(best[0], best[1])[1]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.width, x2), min(frame.height, y2)
    cropped = frame.crop((x1, y1, x2, y2))
    if cropped.size != (170, 330):
        cropped = cropped.resize((170, 330), Image.LANCZOS)

    out = Path("img/theme_packs") / f"{args.name}.png"
    if args.dry:
        dry_path = Path(tempfile.gettempdir()) / f"crop_dry_{args.name}.png"
        cropped.save(dry_path)
        print(f"[dry] 裁剪 {cropped.size}，预览已存 {dry_path}，正式路径应为 {out}")
    else:
        cropped.save(out)
        print(f"已保存 {out}（{cropped.size}，来自 {args.frame}，卡片中心 {best[0]},{best[1]}）")


if __name__ == "__main__":
    main()
