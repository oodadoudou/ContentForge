============================================================
           模块七: 通用下载器 (07_downloader)
============================================================

【简介】
  本模块提供针对特定网站的专用下载工具。目前支持从 Diritto
  网站下载小说内容。


【核心脚本】
  - diritto_downloader.py


【使用方法】
  本模块的所有功能都已整合到项目根目录的 main.py 交互式菜单中。

  1. 在终端中，进入 ContentForge 根目录，运行 `python main.py`。
  2. 在主菜单选择 "7. 通用下载器"。
  3. 根据子菜单的提示选择您需要的功能。


--------------------- 功能与用法详解 ---------------------

+ + + 1. [Diritto] 小说下载器 + + +

  - **对应脚本**: `diritto_downloader.py`
  - **功能**: 自动抓取指定 Diritto 小说页面的所有章节内容，
    将每一章保存为独立的 TXT 文件，最后将所有章节打包成一个
    ZIP 压缩文件，存放在您的默认工作目录中。
  - **应用场景**: 当您需要备份或离线阅读 Diritto 上的小说时使用。

  - **【重要】准备工作**:
    此工具需要通过“远程调试”模式连接到您已登录的 Chrome 浏览器
    才能工作。请在运行脚本前，务必按以下步骤操作：

    1.  **完全关闭所有 Chrome 浏览器窗口**。
        (请检查任务栏或 Dock，确保 Chrome 已完全退出)。

    2.  **使用命令行启动 Chrome**。
        您需要打开系统的终端 (Windows 的 CMD/PowerShell 或 macOS 的终端)。

        - **对于 Windows 用户**:
          在终端中输入以下命令并按回车：
          ```bash
          "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
          ```
          *(如果您的 Chrome 安装在其他路径，请相应修改)*

        - **对于 macOS 用户**:
          在终端中输入以下命令并按回车：
          ```bash
          /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
          ```

    3.  **保持终端和新打开的 Chrome 窗口不要关闭**。
        成功后，您会看到一个独立的 Chrome 窗口被打开。现在您可以
        正常登录 Diritto 网站了。

  - **操作流程**:
    1.  完成上述准备工作，并保持 Chrome 运行。
    2.  返回 ContentForge，在主菜单进入本模块并选择下载功能。
    3.  根据提示，粘贴您要下载的小说目录页的 URL。
    4.  程序将自动开始抓取，您可以在终端看到实时进度。
