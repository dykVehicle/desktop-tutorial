# AI Model Aggregator & Comparison Tool

这是一个集成了多种大模型（LLM）的聚合聊天工具，支持同时向多个模型发送提示词，并横向对比输出结果。

## 功能特点

- **多模型集成**：支持 OpenAI Compatible 接口（如 OpenAI, DeepSeek, OpenRouter, LocalAI 等）。
- **并发请求**：一次输入，同时触发多个选中的模型。
- **结果对比**：并排显示不同模型的回答，方便直观对比。
- **智能总结**：支持使用选定的模型对多个回答进行总结和差异分析。
- **跨平台**：
  - Web (网页版)
  - Desktop (Windows .exe, Linux .deb)
  - Android (通过 Capacitor 打包)

## 开发与构建

### 前置要求

- Node.js (v18+)
- NPM

### 1. 安装依赖

```bash
npm install
```

### 2. 开发模式

**Web 模式:**
```bash
npm run dev
```

**桌面应用模式 (Electron):**
```bash
npm run electron:dev
```

### 3. 构建发布

**构建 Web 产物:**
```bash
npm run build
```
产物位于 `dist/` 目录。

**构建桌面应用 (EXE/DEB):**
```bash
npm run electron:build
```
产物位于 `release/` 目录。

**构建 Android APK:**
本项目代码支持通过 Capacitor 构建 Android 应用。由于构建 APK 需要 Android Studio 环境，请按照以下步骤操作：

1. 初始化 Capacitor:
   ```bash
   npm install @capacitor/core @capacitor/cli @capacitor/android
   npx cap init
   npx cap add android
   ```

2. 构建 Web 资源并同步:
   ```bash
   npm run build
   npx cap sync
   ```

3. 打开 Android Studio 进行打包:
   ```bash
   npx cap open android
   ```
   在 Android Studio 中点击 "Build -> Build Bundle(s) / APK(s) -> Build APK(s)" 即可生成 APK 文件。

## 使用说明

1. 进入应用后，点击左下角的 "Settings & Models"。
2. 添加你的模型配置 (API Key, Base URL)。
   - 例如 DeepSeek: Base URL: `https://api.deepseek.com/v1`, Model Name: `deepseek-chat`
3. 在聊天输入框上方勾选要使用的模型。
4. 发送消息，所有选中的模型将同时响应。
5. 点击回合底部的 "Compare Results" 按钮获取对比总结。
