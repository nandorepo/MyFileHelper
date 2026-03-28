# 模块依赖关系图

## 📊 依赖关系

```
┌─────────────────────────────────────────────────────────┐
│                    app.js (启动点)                      │
│                    14 行，完全简洁                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
        ┌───────────────────────────────────────┐
        │      app_init.js (编排和初始化)      │
        │           76 行                       │
        │   - 模块组合                          │
        │   - 依赖注入                          │
        │   - 初始化顺序管理                    │
        └───────────────────────────────────────┘
              ↙      ↙      ↙      ↙      ↙
        ┌──────────┬────────────┬──────────┬──────────────┐
        │          │            │          │              │
   ┌────▼─┐  ┌────▼────┐ ┌─────▼──┐ ┌────▼────┐ ┌─────▼────┐
   │event │  │ socket  │ │  UI    │ │ socket  │ │  login   │
   │handle│  │ handler │ │ manager│ │  pause  │ │ manager  │
   │ ers  │  │         │ │        │ │ manager │ │          │
   │140行 │  │  48行   │ │ 100行  │ │  90行   │ │  93行    │
   └──────┘  └────┬────┘ └─────┬──┘ └────┬────┘ └─────┬────┘
                  │            │         │            │
                  │            │         │            │
                  └────────────┼─────────┴────────────┘
                               │
                               ↓
                        ┌──────────────┐
                        │  utils.js    │
                        │   99 行      │
                        │ (基础工具库) │
                        └──────────────┘
```

## 🔗 详细依赖关系

| 模块 | 依赖的模块 | 提供的函数 | 说明 |
|------|----------|---------|------|
| **utils.js** | 无 | `log`, `logError`, `getBrowserStorageKey`, `getI18nRuntime`, `serializeLogValue`, `sendClientLog`, `ensureSocketIoLoaded` | 基础工具库，被所有模块依赖 |
| **ui_manager.js** | utils.js | `initializeUiElements`, `applyI18nToUI`, `setLoginError`, `updateOverflow`, `renderTerminals` | UI 组件管理 |
| **login_manager.js** | utils.js, ui_manager.js | `createLoginManager()` | 用户登录和会话管理 |
| **socket_pause_manager.js** | utils.js | `createSocketPauseManager()` | Android 上传时的 Socket 管理 |
| **event_handlers.js** | utils.js, ui_manager.js | `attachUIEventListeners`, `attachDragDropListeners`, `uploadFile` | 所有 UI 事件处理 |
| **socket_handlers.js** | utils.js, ui_manager.js | `attachSocketEventListeners` | Socket.IO 事件处理 |
| **app_init.js** | 所有上述模块 | `initializeModules` | 模块初始化和编排 |
| **app.js** | app_init.js, utils.js | (无) | 启动入口 |

## 💾 文件加载大小统计

| 文件 | 大小 | 行数 | 压缩后* |
|------|------|------|---------|
| utils.js | 2.6 KB | 99 | ~1.0 KB |
| ui_manager.js | 3.3 KB | 100 | ~1.3 KB |
| login_manager.js | 2.7 KB | 93 | ~1.0 KB |
| socket_pause_manager.js | 2.5 KB | 90 | ~0.9 KB |
| event_handlers.js | 4.2 KB | 140 | ~1.5 KB |
| socket_handlers.js | 1.7 KB | 48 | ~0.7 KB |
| app_init.js | 3.0 KB | 76 | ~1.1 KB |
| app.js | 0.4 KB | 14 | ~0.2 KB |
| **总计** | **20.4 KB** | **659 行** | **~7.7 KB** |

*压缩后为 gzip 压缩估计值

## 🚀 加载顺序

```
1. socket_loader.js (第三方库)
2. i18n.js (第三方库)
3. upload_flow.js (第三方库)
4. file_preview.js (第三方库)
5. message_renderer.js (第三方库)
6. message_view.js (第三方库)
   ↓
7. utils.js ⭐ (基础，无依赖)
8. ui_manager.js (依赖 utils)
9. login_manager.js (依赖 utils, ui_manager)
10. socket_pause_manager.js (依赖 utils)
11. event_handlers.js (依赖 utils, ui_manager)
12. socket_handlers.js (依赖 utils, ui_manager)
13. app_init.js (依赖所有上述)
    ↓
14. app.js ⭐ (启动，依赖 app_init)
```

## ✅ 验证清单

- [x] 所有模块都已创建
- [x] 脚本加载顺序正确
- [x] 依赖关系清晰
- [x] 初始化顺序修复（loginManager 和 socketPause 在 uploadFlow 之前）
- [x] HTML 中的脚本标签已更新
- [x] 每个模块 < 150 行（易于阅读）
- [x] 模块职责清晰（单一职责原则）

## 🔍 测试方法

### 在浏览器开发者工具中测试

1. 打开网页
2. 打开浏览器控制台（F12）
3. 检查没有 JavaScript 错误
4. 验证功能：
   - [x] 可以输入终端名称并登录
   - [x] 可以发送消息
   - [x] 可以上传文件
   - [x] 实时收到其他终端消息

### 查看加载的脚本

```javascript
// 在控制台执行
document.querySelectorAll('script[src*="static"]').forEach(s => {
  console.log(s.src.split('/').pop())
})
```

应该看到所有 14 个脚本都加载成功。

