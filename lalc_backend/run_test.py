"""
快速启动 server + 运行任务，日志保存到 logs/ 目录
前提：游戏窗口已打开，游戏语言为 English
用法：
  cd lalc_backend
  python3 run_test.py              # 跑 main（从头开始）
  python3 run_test.py mirror_enter  # 直接进镜牢
  python3 run_test.py luxcavation   # 直接刷经验本
"""

import asyncio
import websockets
import json
import os
import sys
from datetime import datetime
from server import ServerController


async def run():
    # 确保 logs 目录存在
    os.makedirs("logs", exist_ok=True)
    log_path = f"logs/test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file = open(log_path, "w", encoding="utf-8")

    def log(msg, end="\n"):
        print(msg, end=end, flush=True)
        log_file.write(msg + end)
        log_file.flush()

    # 1. 启动 server
    server = ServerController()
    start_server = await websockets.serve(
        server.client_handler, "localhost", 8765,
        ping_interval=None
    )
    log("✅ Server 已启动 → ws://localhost:8765")
    log("   (按 Ctrl+C 停止)\n")

    # 2. 连接 client
    async with websockets.connect("ws://localhost:8765") as ws:
        await ws.recv()
        log("✅ Client 已连接\n")

        # 3. 发送 start 命令
        task_name = sys.argv[1] if len(sys.argv) > 1 else "main"
        log(f"🚀 开始执行 {task_name} 任务...")
        await ws.send(json.dumps({
            "type": "request",
            "id": "test-001",
            "payload": {
                "command": "start",
                "args": [task_name],
            },
        }))

        # 4. 心跳保活
        async def heartbeat_loop():
            while True:
                await asyncio.sleep(5)
                try:
                    await ws.send(json.dumps({"type": "heartbeat"}))
                except:
                    break

        hb_task = asyncio.create_task(heartbeat_loop())
        try:
            for _ in range(999):
                msg = await asyncio.wait_for(ws.recv(), timeout=15)
                data = json.loads(msg)
                if data.get("type") == "task_log":
                    log(f"  📋 {data.get('payload', {}).get('log', '')}")
                elif data.get("type") == "response":
                    status = data.get("payload", {}).get("status", "")
                    if status == "error":
                        log(f"  ❌ {data['payload'].get('message', '')}")
        except asyncio.TimeoutError:
            log("  ⏸️  超时，停止接收")
        finally:
            hb_task.cancel()

    start_server.close()
    log(f"\n✅ 日志已保存到 {log_path}")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n🛑 已停止")
