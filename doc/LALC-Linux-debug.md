# LALC Linux 调试与交接

> 项目根目录：`/home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany`  
> 环境：Arch / niri / gamescope / Flutter / Python 3.10

## 0. 先看状态

```bash
pgrep -a -f 'LimbusCompany|gamescope|server.py|lalc_frontend'
ss -ltnp | grep 8765
ls /tmp/.X11-unix
DISPLAY=:1 xdotool search --name LimbusCompany
```

当前机器通常游戏在 `DISPLAY=:1`，窗口 `2560x1440`。找不到就试 `:2`、`:0`。

## 1. 游戏启动项（Steam）

```
gamescope -W 2560 -H 1440 -w 2560 -h 1440 --force-grab-cursor -- %command%
```

- 不要设 `PROTON_ENABLE_WAYLAND=1`
- 后端会缩放到 1280×720 再匹配
- 想用 1280×720 就把四个参数改成 `1280 720`

## 2. 启动后端

```bash
cd /home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany/lalc_backend

DISPLAY=:1 LALC_CAPTURE=gamescope .venv/bin/python server.py
```

后台：

```bash
cd /home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany/lalc_backend
nohup env DISPLAY=:1 LALC_CAPTURE=gamescope .venv/bin/python server.py \
  > /tmp/lalc_backend.out 2>&1 &
```

- `LALC_CAPTURE=gamescope`：走 `gamescopectl` 抓帧
- 普通 X11 / XWayland 不要设这个变量
- Linux 用 `server.py`，不要用 `main.py`（Windows 专用）

## 3. 启动前端

```bash
cd /home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany/lalc_frontend
./build/linux/x64/release/bundle/lalc_frontend
```

开发模式：

```bash
cd /home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany/lalc_frontend
flutter run -d linux
```

前端连 `ws://localhost:8765`，连上后日志有 `[RX]Heartbeat acknowledged`。

重新构建：

```bash
cd /home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany/lalc_frontend
PUB_HOSTED_URL=https://pub.flutter-io.cn \
FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn \
flutter pub get

FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn \
flutter build linux --release
```

## 4. 不用前端，直接跑任务

```bash
cd /home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany/lalc_backend

DISPLAY=:1 LALC_CAPTURE=gamescope .venv/bin/python run_test.py
DISPLAY=:1 LALC_CAPTURE=gamescope .venv/bin/python run_test.py mirror_enter
DISPLAY=:1 LALC_CAPTURE=gamescope .venv/bin/python run_test.py luxcavation
```

运行前先停掉占用 8765 的后端。游戏窗口要先打开，语言 English。

## 5. 日志 / 截图

```bash
cd /home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany/lalc_backend
ls -td logs/*/ | head -1
tail -f "$(ls -td logs/*/ | head -1)run.log"
ls -lt "$(ls -td logs/*/ | head -1)images" | head
```

手动抓帧：

```bash
gamescopectl screenshot /tmp/limbus_shot.png
```

## 6. 停止

```bash
pkill -f 'lalc_backend/server.py'
pkill -f 'lalc_frontend'
```

不要随便杀 `gamescope` / `LimbusCompany`。

## 7. 常见问题

**模板全匹配 `[]`，像图库坏了**

先抓一帧看是不是黑图：

```bash
gamescopectl screenshot /tmp/shot.png
```

- 黑图：确认 `LALC_CAPTURE=gamescope`
- 超时：确认游戏在 gamescope 里、DISPLAY 正确
- 不要先怀疑图库

**前端连不上**

```bash
ss -ltnp | grep 8765
```

检查后端是否启动、端口是否被旧进程占用。前端会试 8765–8767。

**找不到窗口**

- 游戏没启动
- DISPLAY 错
- 游戏变成原生 Wayland（去掉 `PROTON_ENABLE_WAYLAND=1`）

**改图没生效**

后端启动时才加载 `img/`，改完重启。图片要求：PNG、文件名唯一、按 1280×720 裁剪、不要拉伸。

## 8. 给 GLM 的交接规则

**范围**

- 只维护 Linux 适配：`lalc_backend/` + `lalc_frontend/`
- 不要整体搬上游 `architecture-refactor` 分支
- 上游参考版本：`HSLix/LixAssistantLimbusCompany` `v5.0.0`（2026-07-12）
- `limbus_unpack/` 是独立素材目录，不属于 LALC 运行代码

**不要动**

- `lalc_backend/config/*.json`：用户配置，不提交
- `lalc_backend/img/`：不要批量覆盖，先看 manifest / 匹配表
- `lalc_backend/logs/`、`.venv/`、`lalc_frontend/build/`
- 不要加 `PROTON_ENABLE_WAYLAND=1`

**改完必须验证**

```bash
cd /home/tomjieli/01_Code_Docs/LixAssistantLimbusCompany/lalc_backend
DISPLAY=:1 LALC_CAPTURE=gamescope .venv/bin/python run_test.py mirror_enter
```

或后端 + 前端各开一个终端。

**设计约束**

- 截图参考分辨率固定 1280×720
- 坐标是窗口客户区坐标
- `LALC_CAPTURE=x11|gamescope` 语义不能改
- 抓帧失败要明确报错，不能静默返回旧图
- 识别失败先看 `logs/<时间>/run.log` 里的 `IMAGE:` 和 `images/`
- 任务节点在 `config/task/*.json`，流程在 `workflow/`

**当前已知问题**

- 游戏已更新到 2026-10，上游 v5.0.0 素材/流程不完全适配
- `mirror_choose_star` 已改新星光页，点击坐标可能还要调
- 饰品观测（消耗星光）未实现
- 主题包卡面是分层的，解包底图不一定能直接识别
