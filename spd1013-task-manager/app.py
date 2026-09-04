# -*- coding: utf-8 -*-
"""启动入口。

用法：
    python app.py
然后浏览器打开 http://127.0.0.1:5000  （默认账号 admin / spd1013）

只监听 127.0.0.1，不对外网开放；调试模式默认关闭，需要热重载时用：
    SPD_DEBUG=1 python app.py
"""
import os

from spdapp import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("SPD_DEBUG", "0") == "1"
    cfg = app.config
    print("=" * 62)
    print(f"  {cfg['APP_NAME']}")
    print(f"  姓名：{cfg['STUDENT_NAME']}   学号：{cfg['STUDENT_ID']}   "
          f"项目标识：{cfg['PROJECT_CODE']}")
    print(f"  数据库文件：{cfg['DATABASE']}")
    print(f"  访问地址：http://127.0.0.1:5000   "
          f"（账号 {cfg['DEFAULT_USERNAME']} / {cfg['DEFAULT_PASSWORD']}）")
    print("=" * 62)
    app.run(host="127.0.0.1", port=5000, debug=debug)
