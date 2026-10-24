"""
选卡包界面一键体检+收割（手动+自动混合工作流）。

用法：手动把游戏开到"选主题包"画面（4 张卡 + 刷新按钮那屏），然后：
  .venv/bin/python pack_screen_check.py          # 识别 + 体检 + 坏图自动重裁替换
  .venv/bin/python pack_screen_check.py --dry    # 只识别和报告，不写 img/

行为：
1. 抓当前 gamescope 画面（全分辨率 2560x1440 -> 1280x720）
2. 校验确实在选卡包界面（theme_pack_detail 定位），不是则直接退出
3. OCR 读出画面上每张卡的名字，和生产同款方式关联卡片位置
4. 对每个"图库里已有"的包做健康检查（生产参数模板匹配）：
   - 过阈值 -> 报分数
   - 不过阈值但卡就在画面上 -> 从当前帧重裁 170x330，自验证 >=0.9 后
     备份旧图(<name>.old.png)并替换，报告新旧分数
5. OCR 读到但图库没有的包 -> 用 OCR 名字存新模板（人工看一眼报告确认拼写）
6. 挂着 NEW 徽章的未探索位置会跳过留档（游戏对未探索包显示占位卡面，
   裁了也是错的），只报告位置。

不写 logs/、不触发历史目录清理、不点击任何东西。
"""

import argparse
import difflib
import logging
import tempfile
from pathlib import Path

# ── 在导入 recognize 之前接管 LALCLogger（离线工具一律不走 logs/）──────────
import utils.logger as _ul


def _offline_init(self, retain_folder_count: int = 3):
    self.logger = logging.getLogger("lalc_logger")
    self.log_dir = Path(tempfile.mkdtemp(prefix="lalc_verify_"))


_ul.LALCLogger.__init__ = _offline_init
_ul.LALCLogger._clean_old_folders = lambda self, keep: None
# ──────────────────────────────────────────────────────────────────────────

from PIL import Image  # noqa: E402

import recognize.img_recognizer as _ir  # noqa: E402
from input.game_screenshot import _take_screenshot_gamescope  # noqa: E402
from recognize.img_recognizer import recognize_handler  # noqa: E402
from recognize.img_registry import get_images_by_tag  # noqa: E402
from recognize.template_match import template_match as base_match  # noqa: E402
from recognize.utils import mask_screenshot  # noqa: E402
from utils.get_save_theme_packs import get_rect_from_center  # noqa: E402

PROD_MASK_TEMPLATE = [20, 20, 130, 290]
PROD_THRESHOLD = 0.8
SELF_VERIFY_THRESHOLD = 0.9
OCR_MASK = [100, 440, 1100, 60]


def load_frame() -> Image.Image:
    img = _take_screenshot_gamescope().convert("RGB")
    if img.size != (1280, 720):
        # 生产用 NEAREST(1) 缩放（input_handler.py:175），图库模板都在这个采样下匹配，
        # 换别的滤波器模板分会被压低，必须保持一致
        img = img.resize((1280, 720), 1)
    return img


def main():
    ap = argparse.ArgumentParser(description="选卡包界面一键体检+收割")
    ap.add_argument("--dry", action="store_true", help="只报告，不写 img/")
    ap.add_argument("--heal-below", type=float, default=PROD_THRESHOLD,
                    help=f"低于此分数即重裁替换（默认 {PROD_THRESHOLD}=生产阈值；"
                         f"边缘分想强制换用 0.85）")
    ap.add_argument("--frame", help="用指定的已存帧代替现场抓拍（离线复查用）")
    args = ap.parse_args()

    _ir.logger.debug = lambda *a, **k: None  # 静音 debug 存图

    if args.frame:
        frame = Image.open(args.frame).convert("RGB")
        if frame.size != (1280, 720):
            frame = frame.resize((1280, 720), 1)
    else:
        frame = load_frame()

    # 1. 界面校验：优先用模板定位卡片；模板不认（如卡牌处于选中/放大浏览态）
    #    时，退回用标题 OCR 判断（"SELECT FLOOR X THEME PACK"）
    matches = recognize_handler.template_match(frame, "theme_pack_detail")
    title_ocr = recognize_handler.detect_text_in_image(frame, mask=[400, 80, 480, 110])
    is_pack_screen = any("THEME PACK" in t[0].upper() for t in title_ocr)
    if not matches and not is_pack_screen:
        print("当前不是选卡包界面（没找到卡片，标题也没有 THEME PACK），不处理。")
        raise SystemExit(1)
    pos_source = "theme_pack_detail 模板" if matches else "OCR 标题+名字中心推算"
    print(f"定位方式：{pos_source}" + (f"（{len(matches)} 张卡）" if matches else ""))

    # NEW 徽章位置（未探索包显示占位卡面，不能留档）
    new_marks = recognize_handler.template_match(frame, "mirror_theme_pack_new")

    # 2. OCR 名字并关联
    ocr = recognize_handler.detect_text_in_image(frame, mask=OCR_MASK)
    if not ocr:
        print("OCR 没读到任何卡包名，界面可能还在加载。")
        raise SystemExit(1)

    # 无模板定位时，由名字位置推卡片中心：卡中心 ≈ (名字cx, 名字y - 102)
    CARD_CENTER_Y_OFFSET = 102

    all_packs = [x[0] for x in get_images_by_tag("theme_packs")]
    healthy, healed, unknown, skipped_new = [], [], [], []

    used_matches = set()
    for text, cx, cy, _ in ocr:
        # 找这张名字对应的卡片位置
        if matches:
            best, best_d = None, 10**9
        if matches:
            best, best_d = None, 10**9
            for i, m in enumerate(matches):
                d = abs(m[0] - cx)
                if d <= 100 and d < best_d and i not in used_matches:
                    best, best_d = m, d
            if best is None:
                continue
            used_matches.add(tuple(best))
        else:
            best = (cx, cy - CARD_CENTER_Y_OFFSET, 1.0)

        # NEW 徽章附近的位置跳过留档
        if any(best[0] - n[0] <= 180 and abs(best[1] - n[1]) <= 50 for n in new_marks):
            skipped_new.append(text)
            continue

        # 名字归一（容忍 OCR 误读和长名碎片，如 "Bullet" <- "Full-Stopped by a Bullet"）
        canon = difflib.get_close_matches(text, all_packs, cutoff=0.75, n=1)
        if not canon and len(text) >= 4:
            for p in all_packs:
                if text in p or (len(text) >= 8 and p in text):
                    canon = [p]
                    break
        name = canon[0] if canon else text.strip()

        if not canon:
            if len(text) < 6:
                print(f"  · OCR 碎片 {text!r}（x={cx}），跳过")
                continue
            # 完整陌生名字：可能是图库没有的新包
            (x1, y1), (x2, y2) = get_rect_from_center(*best[:2])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.width, x2), min(frame.height, y2)
            crop = frame.crop((x1, y1, x2, y2))
            if crop.size != (170, 330):
                crop = crop.resize((170, 330), Image.LANCZOS)
            out = Path(tempfile.gettempdir()) / f"new_pack_{name}.png"
            crop.save(out)
            unknown.append((name, text))
            print(f"[新包?] OCR 读到 {text!r}，图库没有。预览存 {out}，确认后手动放入 img/theme_packs/")
            continue

        # 3. 健康检查
        res = recognize_handler.template_match(
            frame, name, threshold=0.3,
            mask_template=PROD_MASK_TEMPLATE,
        )
        best_score = max((r[2] for r in res), default=None)

        if canon and best_score is not None and best_score >= args.heal_below:
            healthy.append((name, best_score, text))
            continue

        # 4. 重裁
        (x1, y1), (x2, y2) = get_rect_from_center(*best[:2])
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.width, x2), min(frame.height, y2)
        crop = frame.crop((x1, y1, x2, y2))
        if crop.size != (170, 330):
            crop = crop.resize((170, 330), Image.LANCZOS)

        # 自验证：新裁图必须在同一帧上 >= 0.9 才允许落盘（防 OCR 关联错位裁出垃圾）
        self_res = base_match(frame, mask_screenshot(crop, *PROD_MASK_TEMPLATE), threshold=0.5)
        self_score = max((r[2] for r in self_res), default=0.0)
        if self_score < SELF_VERIFY_THRESHOLD:
            print(f"  ✗ {name}: 重裁图自验证仅 {self_score:.3f}（<{SELF_VERIFY_THRESHOLD}），"
                  f"疑似关联错位，不替换。OCR 原文 {text!r}，卡片中心 {best[0]},{best[1]}")
            continue

        if args.dry:
            dry_path = Path(tempfile.gettempdir()) / f"dry_{name}.png"
            crop.save(dry_path)
            healed.append((name, best_score, None, dry_path))
            continue

        out = Path("img/theme_packs") / f"{name}.png"
        backup = out.with_suffix(".old.png")
        if backup.exists():
            backup.unlink()
        out.rename(backup)
        crop.save(out)
        healed.append((name, best_score, backup, out))

    # 5. 汇总
    print("\n===== 汇总 =====")
    for name, score, ocr_text in healthy:
        print(f"  ✓ {name}: {score:.3f}（OCR 读到 {ocr_text!r}）")
    for name, old_score, backup, out in healed:
        old_s = "无候选" if old_score is None else f"{old_score:.3f}"
        where = f"已替换 {out}（旧图备份 {backup.name}）" if isinstance(out, Path) else f"预览 {out}"
        print(f"  ↻ {name}: 原分数 {old_s} 未过 {args.heal_below}，{where}")
    for name, text in unknown:
        print(f"  ? 图库没有 {name!r}（OCR: {text!r}）")
    for text in skipped_new:
        print(f"  ⊘ {text!r} 挂着 NEW 徽章（未探索占位卡面），跳过留档，探索一次后再收")
    if not (healthy or healed or unknown or skipped_new):
        print("  （画面上的卡都没能关联名字）")


if __name__ == "__main__":
    main()
