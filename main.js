const { app, BrowserWindow } = require('electron')

function createWindow () {
  // 创建浏览器窗口
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: false, // 安全起见，加载远程内容时禁用 Node.js 集成
      contextIsolation: true
    }
  })

  // 这里的 URL 就是你想封装成 App 的网站地址
  // 你可以把它改成任何你想要的网址，比如 'https://www.google.com'
  const targetUrl = 'https://www.baidu.com'; 

  // 加载远程 URL
  win.loadURL(targetUrl)

  // 移除默认菜单栏（可选，让它看起来更像原生 App）
  // win.setMenu(null)
}

// 当 Electron 完成初始化并准备创建浏览器窗口时调用此方法
app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    // 在 macOS 上，当点击 dock 图标并且没有其他窗口打开时，
    // 通常在应用程序中重新创建一个窗口。
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

// 除了 macOS 外，当所有窗口都被关闭的时候退出程序。
// 因此，通常对应用程序和它们的菜单栏来说应该时刻保持激活状态，
// 直到用户使用 Cmd + Q 明确退出
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
