# 将网站转换为桌面应用示例

这是一个使用 Electron 将网页链接封装成桌面应用（Windows/macOS/Linux）的最小化示例。

## 核心原理

核心逻辑位于 `main.js` 文件中。它创建了一个浏览器窗口，并加载指定的 URL，使其看起来像一个原生应用。

## 快速开始

1.  **安装依赖**:
    ```bash
    npm install
    ```

2.  **运行应用**:
    ```bash
    npm start
    ```
    这将启动一个窗口并加载默认网站（百度）。

## 如何修改目标网站

打开 `main.js` 文件，找到以下代码行并修改为你想要的网址：

```javascript
// main.js
const targetUrl = 'https://www.your-website.com'; 
```

## 下一步：如何打包成 .exe 或 .dmg

要将此项目打包成可分发的文件（如 `.exe`），你可以使用 `electron-builder` 或 `electron-forge`。

### 使用 Electron Forge 打包（推荐）

1.  将项目导入为 Forge 项目:
    ```bash
    npx electron-forge import
    ```

2.  打包应用:
    ```bash
    npm run make
    ```

构建完成后，你将在 `out/` 文件夹中找到生成的可执行文件。
