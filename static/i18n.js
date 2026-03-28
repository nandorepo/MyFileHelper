// Locale catalog and translator factory.
(function () {
  const SUPPORTED_LOCALES = {
    zh: "zh-CN",
    en: "en-US",
  };

  const I18N = {
    "en-US": {
      appTitle: "MyFileHelper",
      terminalLabel: "Online Terminals",
      more: "More",
      messagePlaceholder: "Type a message and press Enter",
      uploadTitle: "Upload file",
      send: "Send",
      loginTitle: "Enter terminal name",
      loginPlaceholder: "e.g. MacBook-Pro",
      join: "Join",
      unnamedFile: "Unnamed file",
      unsupportedPreview: "Unsupported file preview",
      clickToPreview: "Click file name to preview",
      download: "Download",
      saveAs: "Save as",
      copyLink: "Copy link",
      copyLinkFailed: "Copy link failed",
      saveAsFailed: "Save failed",
      waiting: "Waiting",
      initializing: "Initializing",
      initFailed: "Init failed",
      uploading: "Uploading",
      done: "Done",
      failed: "Failed",
      socketLoadFailed: "Socket.IO load failed. Please check network and refresh.",
      connectionNotReady: "Connection not ready. Please try again shortly.",
      enterTerminalName: "Please enter a terminal name.",
      registerTimeout: "Register timeout. Check console logs and retry.",
      loginFailedRetry: "Login failed. Please retry.",
      unexpectedLoginError: "Unexpected error during login. Check console.",
      connectionClosed: "Connection closed. Please retry.",
      cannotConnectServer: "Cannot connect to server. Check backend status.",
      socketScriptFailed: "Socket.IO script failed to load. Please check network/proxy settings.",
      selfName: "Me",
    },
    "zh-CN": {
      appTitle: "文件传输助手",
      terminalLabel: "在线终端",
      more: "更多",
      messagePlaceholder: "输入消息并按 Enter 发送",
      uploadTitle: "上传文件",
      send: "发送",
      loginTitle: "输入终端名称",
      loginPlaceholder: "例如：MacBook-Pro",
      join: "加入",
      unnamedFile: "未命名文件",
      unsupportedPreview: "暂不支持该文件预览",
      clickToPreview: "点击文件名进行预览",
      download: "下载",
      saveAs: "另存为",
      copyLink: "复制链接",
      copyLinkFailed: "复制链接失败",
      saveAsFailed: "保存失败",
      waiting: "等待中",
      initializing: "初始化中",
      initFailed: "初始化失败",
      uploading: "上传中",
      done: "完成",
      failed: "失败",
      socketLoadFailed: "Socket.IO 加载失败，请检查网络后刷新。",
      connectionNotReady: "连接尚未就绪，请稍后重试。",
      enterTerminalName: "请输入终端名称。",
      registerTimeout: "注册超时，请查看控制台日志后重试。",
      loginFailedRetry: "登录失败，请重试。",
      unexpectedLoginError: "登录时发生异常，请检查控制台。",
      connectionClosed: "连接已关闭，请重试。",
      cannotConnectServer: "无法连接服务器，请检查后端状态。",
      socketScriptFailed: "Socket.IO 脚本加载失败，请检查网络/代理设置。",
      selfName: "我",
    },
  };

  function resolveLocale() {
    const nav = (navigator.language || "").toLowerCase();
    if (nav.startsWith("zh")) {
      return SUPPORTED_LOCALES.zh;
    }
    return SUPPORTED_LOCALES.en;
  }

  function createI18n() {
    const locale = resolveLocale();
    const fallbackLocale = SUPPORTED_LOCALES.en;
    const dict = I18N[locale] || I18N[fallbackLocale];
    return {
      locale,
      t: (key) => dict[key] || I18N[fallbackLocale][key] || key,
    };
  }

  window.MyFileHelperI18n = {
    createI18n,
  };
})();

