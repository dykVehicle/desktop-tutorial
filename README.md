# 网站转 App 示例 (Desktop & Android)

这是一个示例项目，演示如何将任意网站（如 `https://cursor.com/cn/agents`）封装成：
1.  **桌面应用** (Windows/macOS/Linux) - 使用 Electron
2.  **Android 应用** - 使用 Capacitor

## ⚠️ 重要说明：关于 Android 编译

由于云端开发环境未预装 **Android SDK** 和 **Gradle**，**无法直接在云端生成 `.apk` 文件**。

我已经为你生成了**完整的 Android 项目源代码**（在 `android/` 目录下）。你需要将代码下载到本地，或使用支持 Android 构建的 CI/CD 环境来生成最终的 APK。

## 📱 Android 版使用指南

### 1. 准备环境
确保你的本地电脑已安装：
*   **Node.js** (v18+)
*   **Android Studio** (包含 Android SDK)

### 2. 生成 APK 的步骤

1.  **下载代码**: 克隆此仓库到本地。
2.  **安装依赖**:
    ```bash
    npm install
    ```
3.  **同步配置**:
    ```bash
    npm run android:sync
    ```
4.  **打开 Android Studio 进行编译**:
    ```bash
    npm run android:open
    ```
    这将启动 Android Studio。
    *   等待 Gradle Sync 完成。
    *   点击顶部菜单栏的 **Build** -> **Build Bundle(s) / APK(s)** -> **Build APK(s)**。
    *   编译完成后，IDE 会提示你 APK 的位置（通常在 `android/app/build/outputs/apk/debug/`）。

### 3. 修改目标网站
当前默认目标是 `https://cursor.com/cn/agents`。
如果要修改，请编辑 `capacitor.config.json` 文件：
```json
{
  "server": {
    "url": "https://你的新网址.com", 
    "cleartext": true
  }
}
```
修改后记得运行 `npm run android:sync`。

---

## 🖥️ 桌面版 (Electron) 使用指南

### 快速开始
1.  **安装依赖**: `npm install`
2.  **运行预览**: `npm start`

### 打包桌面端
参考 [Electron Forge](https://www.electronforge.io/) 或 [Electron Builder](https://www.electron.build/) 文档。

## 目录结构
*   `android/`: Android 原生项目代码
*   `main.js`: Electron 主进程代码
*   `capacitor.config.json`: Capacitor 配置文件（定义了 Android 加载的 URL）
