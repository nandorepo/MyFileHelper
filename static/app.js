﻿const DEBUG = true;
const REGISTER_ACK_TIMEOUT_MS = 8000;
const CLIENT_LOG_ENABLED = false; // 旧 API 已移除，客户端日志不上报

function getBrowserStorageKey() {
  const ua = (navigator.userAgent || "").toLowerCase();
  if (ua.includes("edg/")) {
    return "mytransfer_terminal_name_edge";
  }
  if (ua.includes("chrome/")) {
    return "mytransfer_terminal_name_chrome";
  }
  return "mytransfer_terminal_name";
}

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

const SOCKET_IO_CANDIDATES = [
  "/static/vendor/socket.io.min.js",
  "/socket.io/socket.io.js",
  "https://cdn.socket.io/4.7.5/socket.io.min.js",
  "https://cdn.jsdelivr.net/npm/socket.io-client@4.7.5/dist/socket.io.min.js",
  "https://unpkg.com/socket.io-client@4.7.5/dist/socket.io.min.js",
  "https://cdn.bootcdn.net/ajax/libs/socket.io/4.7.5/socket.io.min.js",
];

function log(...args) {
  if (!DEBUG) {
    return;
  }
  console.log("[MyTransfer]", ...args);
  sendClientLog("info", args);
}

function logError(...args) {
  console.error("[MyTransfer]", ...args);
  sendClientLog("error", args);
}

function serializeLogValue(value, depth = 0) {
  if (depth > 3) {
    return "[MaxDepth]";
  }

  if (value === null || value === undefined) {
    return value;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }

  if (value instanceof Error) {
    return {
      name: value.name,
      message: value.message,
      stack: value.stack,
    };
  }

  if (Array.isArray(value)) {
    return value.map((item) => serializeLogValue(item, depth + 1));
  }

  if (typeof value === "object") {
    const out = {};
    Object.keys(value).forEach((key) => {
      out[key] = serializeLogValue(value[key], depth + 1);
    });
    return out;
  }

  return String(value);
}

function sendClientLog(level, args) {
  if (!CLIENT_LOG_ENABLED) {
    return;
  }

  const payload = {
    ts: new Date().toISOString(),
    level,
    page: window.location.href,
    args: args.map((item) => serializeLogValue(item)),
  };

  fetch("/ui/client-log", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => {
    // Do not recurse by logging transport errors.
  });
}

window.addEventListener("error", (event) => {
  logError("window error", event.message, event.error || "");
});

window.addEventListener("unhandledrejection", (event) => {
  logError("unhandledrejection", event.reason);
});

function loadScript(src) {
  log("loading script", src);
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = () => {
      log("script loaded", src);
      resolve(src);
    };
    script.onerror = () => {
      const error = new Error(`load failed: ${src}`);
      logError(error.message);
      reject(error);
    };
    document.head.appendChild(script);
  });
}

async function ensureSocketIoLoaded() {
  if (typeof io === "function") {
    log("io already available before dynamic load");
    return true;
  }

  for (const src of SOCKET_IO_CANDIDATES) {
    try {
      await loadScript(src);
      if (typeof io === "function") {
        log("io available after loading", src);
        return true;
      }
      log("script loaded but io is still undefined", src);
    } catch (error) {
      logError("script candidate failed", src, error);
    }
  }

  logError("all socket.io candidates failed");
  return typeof io === "function";
}

function initApp(socket) {
  const currentLocale = resolveLocale();
  const fallbackLocale = "en-US";
  const dict = I18N[currentLocale] || I18N[fallbackLocale];
  const t = (key) => dict[key] || I18N[fallbackLocale][key] || key;

  document.documentElement.lang = currentLocale;

  const loginMask = document.getElementById("login-mask");
  const loginForm = document.getElementById("login-form");
  const loginInput = document.getElementById("login-input");
  const loginError = document.getElementById("login-error");
  const loginButton = loginForm.querySelector(".login-button");

  const messageForm = document.getElementById("message-form");
  const messageInput = document.getElementById("message-input");
  const messageList = document.getElementById("message-list");

  const terminalWrapper = document.getElementById("terminal-wrapper");
  const terminalMore = document.getElementById("terminal-more");
  const terminalDropdown = document.getElementById("terminal-dropdown");
  const fileInput = document.getElementById("file-input");

  const terminalLabel = document.querySelector(".terminal-label");
  const brandTitle = document.querySelector(".brand-title");
  const messageInputNode = document.getElementById("message-input");
  const uploadLabelNode = document.querySelector("label[for='file-input']");
  const sendButtonNode = messageForm.querySelector(".send-button");
  const loginTitleNode = document.querySelector(".login-title");

  if (brandTitle) {
    brandTitle.textContent = t("appTitle");
  }
  if (terminalLabel) {
    terminalLabel.textContent = t("terminalLabel");
  }
  if (terminalMore) {
    terminalMore.textContent = t("more");
  }
  if (messageInputNode) {
    messageInputNode.placeholder = t("messagePlaceholder");
  }
  if (uploadLabelNode) {
    uploadLabelNode.title = t("uploadTitle");
  }
  if (sendButtonNode) {
    sendButtonNode.textContent = t("send");
  }
  if (loginTitleNode) {
    loginTitleNode.textContent = t("loginTitle");
  }
  if (loginInput) {
    loginInput.placeholder = t("loginPlaceholder");
  }
  if (loginButton) {
    loginButton.textContent = t("join");
  }

  let registerInFlight = false;
  let currentUsername = "";
  const pendingUploads = new Map();
  const renderedFileIds = new Set();
  const renderedClientMsgIds = new Set();
  const isAndroid = /Android/i.test(navigator.userAgent || "");
  const pauseSocketOnAndroidUpload = true;
  let latestServerCreatedAt = "";
  let pauseRefCount = 0;
  let pickerPauseActive = false;
  let suppressDisconnectNotice = false;
  let pausedSocket = false;
  let pausedWasConnected = false;
  let pickerRequestedAt = 0;
  let pickerSafetyTimer = null;
  let fileContextMenu = null;

  function requestSocketPause(reason) {
    if (!socket || !pauseSocketOnAndroidUpload || !isAndroid) {
      return;
    }
    pauseRefCount += 1;
    if (pauseRefCount !== 1) {
      return;
    }
    if (!socket.connected) {
      return;
    }
    pausedSocket = true;
    pausedWasConnected = true;
    suppressDisconnectNotice = true;
    log("pause socket", reason || "unknown");
    socket.disconnect();
  }

  function releaseSocketPause(reason) {
    if (!socket || !pauseSocketOnAndroidUpload || !isAndroid) {
      return;
    }
    pauseRefCount = Math.max(0, pauseRefCount - 1);
    if (pauseRefCount !== 0 || !pausedSocket) {
      return;
    }
    pausedSocket = false;
    if (pausedWasConnected) {
      pausedWasConnected = false;
      log("resume socket", reason || "unknown");
      socket.connect();
    }
  }

  function beginPickerPause() {
    if (pickerPauseActive) {
      return;
    }
    pickerPauseActive = true;
    if (pickerSafetyTimer) {
      clearTimeout(pickerSafetyTimer);
      pickerSafetyTimer = null;
    }
    requestSocketPause("picker");
    pickerSafetyTimer = setTimeout(() => {
      pickerSafetyTimer = null;
      endPickerPause();
    }, 30000);
  }

  function endPickerPause() {
    if (!pickerPauseActive) {
      return;
    }
    pickerPauseActive = false;
    if (pickerSafetyTimer) {
      clearTimeout(pickerSafetyTimer);
      pickerSafetyTimer = null;
    }
    releaseSocketPause("picker");
  }

  function markPickerRequest() {
    pickerRequestedAt = Date.now();
    beginPickerPause();
  }

  try {
    const key = getBrowserStorageKey();
    const cached = (localStorage.getItem(key) || "").trim();
    if (cached) {
      currentUsername = cached;
      loginInput.value = cached;
    }
  } catch (_error) {
    // Ignore localStorage errors.
  }

  log("initApp", {
    hasSocket: Boolean(socket),
    hasLoginForm: Boolean(loginForm),
    hasLoginInput: Boolean(loginInput),
    hasMessageForm: Boolean(messageForm),
    hasCachedUsername: Boolean(currentUsername),
  });

  function setLoginError(text) {
    log("setLoginError", text || "<empty>");
    if (!text) {
      loginError.textContent = "";
      loginError.classList.add("hidden");
      return;
    }
    loginError.textContent = text;
    loginError.classList.remove("hidden");
  }

  const OFFICE_EXTENSIONS = new Set([
    "doc",
    "docx",
    "xls",
    "xlsx",
    "xlsm",
    "xlsb",
    "ppt",
    "pptx",
    "pps",
    "ppsx",
  ]);

  function getFileName(file) {
    return file.original_name || file.filename || t("unnamedFile");
  }

  function getFileMime(file) {
    return (file.mime || file.mime_type || "").toLowerCase();
  }

  function getFileExt(file) {
    const name = getFileName(file);
    const idx = name.lastIndexOf(".");
    if (idx < 0 || idx === name.length - 1) {
      return "";
    }
    return name.slice(idx + 1).toLowerCase();
  }

  function getInlineFileUrl(file) {
    return file.inline_url || file.url || file.alias_url || file.download_url || "";
  }

  function appendQueryParam(url, key, value) {
    if (!url) {
      return "";
    }
    const hasQuery = url.includes("?");
    const connector = hasQuery ? "&" : "?";
    return `${url}${connector}${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
  }

  function getDownloadFileUrl(file) {
    if (file.alias_url) {
      return file.alias_url;
    }
    if (file.download_url) {
      return file.download_url;
    }
    if (file.file_id) {
      return `/media/${file.file_id}?download=1`;
    }
    return appendQueryParam(getInlineFileUrl(file), "download", "1");
  }

  function getAbsoluteFileUrl(file) {
    const url = getDownloadFileUrl(file) || getInlineFileUrl(file);
    if (!url) {
      return "";
    }
    return new URL(url, window.location.href).toString();
  }

  function triggerBrowserDownload(file) {
    const href = getDownloadFileUrl(file);
    if (!href) {
      return;
    }
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = getFileName(file);
    anchor.rel = "noopener noreferrer";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  async function saveFileAs(file) {
    if (typeof window.showSaveFilePicker !== "function") {
      triggerBrowserDownload(file);
      return;
    }

    const downloadUrl = getAbsoluteFileUrl(file);
    if (!downloadUrl) {
      return;
    }

    let handle;
    markPickerRequest();
    try {
      handle = await window.showSaveFilePicker({
        suggestedName: getFileName(file),
      });
    } finally {
      endPickerPause();
    }

    if (!handle) {
      return;
    }

    const response = await fetch(downloadUrl, { credentials: "same-origin" });
    if (!response.ok) {
      throw new Error(`download failed: ${response.status}`);
    }

    const writable = await handle.createWritable();
    try {
      await writable.write(await response.blob());
      await writable.close();
    } catch (error) {
      await writable.abort();
      throw error;
    }
  }

  function hideFileContextMenu() {
    if (!fileContextMenu) {
      return;
    }
    fileContextMenu.classList.add("hidden");
    fileContextMenu.style.left = "";
    fileContextMenu.style.top = "";
    fileContextMenu._file = null;
  }

  function ensureFileContextMenu() {
    if (fileContextMenu) {
      return fileContextMenu;
    }
    const menu = document.createElement("div");
    menu.className = "file-context-menu hidden";
    menu.innerHTML = `
      <button type="button" class="file-context-action" data-action="download"></button>
      <button type="button" class="file-context-action" data-action="saveAs"></button>
      <button type="button" class="file-context-action" data-action="copyLink"></button>
    `;

    menu.addEventListener("click", async (event) => {
      const action = event.target && event.target.dataset ? event.target.dataset.action : "";
      const file = menu._file;
      hideFileContextMenu();
      if (!file || !action) {
        return;
      }

      try {
        if (action === "download") {
          triggerBrowserDownload(file);
          return;
        }
        if (action === "saveAs") {
          await saveFileAs(file);
          return;
        }
        if (action === "copyLink") {
          await navigator.clipboard.writeText(getAbsoluteFileUrl(file));
        }
      } catch (error) {
        const messageKey = action === "copyLink" ? "copyLinkFailed" : "saveAsFailed";
        logError(messageKey, error);
        window.alert(t(messageKey));
      }
    });

    document.body.appendChild(menu);
    fileContextMenu = menu;
    return menu;
  }

  function showFileContextMenu(event, file) {
    const menu = ensureFileContextMenu();
    menu._file = file;
    const labels = {
      download: t("download"),
      saveAs: t("saveAs"),
      copyLink: t("copyLink"),
    };

    menu.querySelectorAll(".file-context-action").forEach((button) => {
      const action = button.dataset.action;
      button.textContent = labels[action] || action;
    });

    menu.classList.remove("hidden");
    menu.style.left = "0px";
    menu.style.top = "0px";

    const menuWidth = menu.offsetWidth;
    const menuHeight = menu.offsetHeight;
    const left = Math.min(event.clientX, window.innerWidth - menuWidth - 8);
    const top = Math.min(event.clientY, window.innerHeight - menuHeight - 8);
    menu.style.left = `${Math.max(8, left)}px`;
    menu.style.top = `${Math.max(8, top)}px`;
  }

  function isImageFile(file) {
    return getFileMime(file).startsWith("image/");
  }

  function isAudioFile(file) {
    return getFileMime(file).startsWith("audio/");
  }

  function isVideoFile(file) {
    return getFileMime(file).startsWith("video/");
  }

  function isPdfFile(file) {
    return getFileMime(file) === "application/pdf" || getFileExt(file) === "pdf";
  }

  function isOfficeFile(file) {
    const mime = getFileMime(file);
    const ext = getFileExt(file);
    return (
      OFFICE_EXTENSIONS.has(ext) ||
      mime === "application/msword" ||
      mime === "application/vnd.ms-excel" ||
      mime === "application/vnd.ms-powerpoint" ||
      mime === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
      mime === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
      mime === "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    );
  }

  function isPreviewInNewTabFile(file) {
    return isPdfFile(file) || isOfficeFile(file);
  }

  function buildFilePreview(file) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-file";

    const preview = document.createElement("div");
    preview.className = "file-preview";
    const inlineUrl = getInlineFileUrl(file);
    const fileName = getFileName(file);
    const clickablePreview = isPreviewInNewTabFile(file) && Boolean(inlineUrl);

    if (isImageFile(file) && inlineUrl) {
      const img = document.createElement("img");
      img.src = inlineUrl;
      img.alt = fileName;
      preview.appendChild(img);
    } else if (isAudioFile(file) && inlineUrl) {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.src = inlineUrl;
      preview.appendChild(audio);
    } else if (isVideoFile(file) && inlineUrl) {
      const video = document.createElement("video");
      video.controls = true;
      video.preload = "metadata";
      video.src = inlineUrl;
      preview.appendChild(video);
    } else if (clickablePreview) {
      preview.textContent = t("clickToPreview");
    } else {
      preview.textContent = t("unsupportedPreview");
    }

    const name = document.createElement(clickablePreview ? "a" : "div");
    name.className = "file-name";
    name.textContent = fileName;
    name.title = t("saveAs");
    name.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showFileContextMenu(event, file);
    });
    if (clickablePreview) {
      name.classList.add("preview-link");
      name.href = inlineUrl;
      name.target = "_blank";
      name.rel = "noopener noreferrer";

      wrapper.classList.add("preview-clickable");
      wrapper.addEventListener("click", (event) => {
        if (event.target && event.target.closest && event.target.closest(".download-link")) {
          return;
        }
        if (event.target && event.target.closest && event.target.closest(".preview-link")) {
          return;
        }
        window.open(inlineUrl, "_blank", "noopener,noreferrer");
      });
    }

    const actions = document.createElement("div");
    actions.className = "file-actions";
    const sizeText = document.createElement("span");
    sizeText.textContent = formatBytes(file.size);
    const link = document.createElement("a");
    link.className = "download-link";
    link.textContent = t("download");
    link.href = getDownloadFileUrl(file);
    link.rel = "noopener noreferrer";
    actions.appendChild(sizeText);
    actions.appendChild(link);

    wrapper.appendChild(preview);
    wrapper.appendChild(name);
    wrapper.appendChild(actions);
    return wrapper;
  }

  function buildMessageElement(message) {
    const item = document.createElement("div");
    item.className = "message-item";
    item.innerHTML = `
      <div class="message-meta">
        <span class="message-user">${message.user}</span>
        <span>${message.ts}</span>
      </div>
    `;

    if (message.kind === "file" && message.file) {
      item.appendChild(buildFilePreview(message.file));
    } else {
      const text = document.createElement("div");
      text.className = "message-text";
      text.textContent = message.text;
      item.appendChild(text);
    }
    return item;
  }

  function renderMessage(message) {
    try {
      if (message && message.kind === "file" && !message.file && Array.isArray(message.attachments)) {
        const first = message.attachments[0];
        if (first) {
          message.file = {
            file_id: first.file_id,
            original_name: first.filename,
            size: first.size,
            mime: first.mime_type,
            url: first.inline_url || first.url,
            inline_url: first.inline_url || first.url,
            download_url: first.download_url || first.url,
            alias_url: first.alias_url || "",
          };
          if (!message.text) {
            message.text = first.filename || t("unnamedFile");
          }
        }
      }
      if (message && message.created_at && !message._local_only) {
        if (!latestServerCreatedAt) {
          latestServerCreatedAt = message.created_at;
        } else {
          const nextTime = Date.parse(message.created_at);
          const prevTime = Date.parse(latestServerCreatedAt);
          if (!Number.isNaN(nextTime) && !Number.isNaN(prevTime) && nextTime > prevTime) {
            latestServerCreatedAt = message.created_at;
          }
        }
      }
      const fileId = message && message.file ? message.file.file_id : null;
      const clientMsgId = message ? message.client_msg_id : null;
      sendClientLog("info", [
        "renderMessage",
        {
          fileId,
          clientMsgId,
          listExists: Boolean(messageList),
          listCount: messageList ? messageList.children.length : 0,
          loginHidden: loginMask ? loginMask.classList.contains("hidden") : null,
          pendingByClient: clientMsgId ? pendingUploads.has(clientMsgId) : false,
          pendingByFile: fileId ? pendingUploads.has(fileId) : false,
        },
      ]);

      if (clientMsgId && pendingUploads.has(clientMsgId)) {
        const existing = pendingUploads.get(clientMsgId);
        const replacement = buildMessageElement(message);
        if (existing && existing.isConnected) {
          existing.replaceWith(replacement);
        } else {
          messageList.appendChild(replacement);
        }
        pendingUploads.delete(clientMsgId);
        if (fileId) {
          pendingUploads.delete(fileId);
        }
        if (fileId) {
          renderedFileIds.add(fileId);
        }
        renderedClientMsgIds.add(clientMsgId);
        messageList.scrollTop = messageList.scrollHeight;
        sendClientLog("info", ["renderMessage_done", "pending_client"]);
        return;
      }

      if (fileId && pendingUploads.has(fileId)) {
        const existing = pendingUploads.get(fileId);
        const replacement = buildMessageElement(message);
        if (existing && existing.isConnected) {
          existing.replaceWith(replacement);
        } else {
          messageList.appendChild(replacement);
        }
        pendingUploads.delete(fileId);
        if (clientMsgId) {
          pendingUploads.delete(clientMsgId);
        }
        renderedFileIds.add(fileId);
        if (clientMsgId) {
          renderedClientMsgIds.add(clientMsgId);
        }
        messageList.scrollTop = messageList.scrollHeight;
        sendClientLog("info", ["renderMessage_done", "pending_file"]);
        return;
      }

      if (fileId && renderedFileIds.has(fileId)) {
        sendClientLog("info", ["renderMessage_skip", "file_dup"]);
        return;
      }
      if (clientMsgId && renderedClientMsgIds.has(clientMsgId)) {
        sendClientLog("info", ["renderMessage_skip", "client_dup"]);
        return;
      }

      messageList.appendChild(buildMessageElement(message));
      if (fileId) {
        renderedFileIds.add(fileId);
      }
      if (clientMsgId) {
        renderedClientMsgIds.add(clientMsgId);
      }
      messageList.scrollTop = messageList.scrollHeight;
      sendClientLog("info", ["renderMessage_done", "append"]);
    } catch (error) {
      logError("renderMessage failed", error);
      sendClientLog("error", ["renderMessage_failed", serializeLogValue(error)]);
    }
  }

  async function syncMessagesAfterUpload() {
    // 旧的 REST 分页 API /ui/messages 已移除，实时消息由 Socket.IO 推送，无需轮询。
    return;
  }

  function formatBytes(size) {
    if (!Number.isFinite(size) || size <= 0) {
      return "0 B";
    }
    const units = ["B", "KB", "MB", "GB", "TB"];
    const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
    const value = size / Math.pow(1024, index);
    return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
  }

  function createUploadItem(file) {
    const item = document.createElement("div");
    item.className = "message-item";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    const user = document.createElement("span");
    user.className = "message-user";
    user.textContent = currentUsername || t("selfName");
    const ts = document.createElement("span");
    ts.textContent = new Date().toLocaleTimeString(currentLocale, { hour12: false });
    meta.appendChild(user);
    meta.appendChild(ts);

    const body = document.createElement("div");
    body.className = "message-file";
    const name = document.createElement("div");
    name.className = "upload-name";
    name.textContent = file.name;
    const status = document.createElement("div");
    status.className = "upload-meta";
    status.textContent = t("waiting");
    const progress = document.createElement("div");
    progress.className = "upload-progress";
    const bar = document.createElement("span");
    progress.appendChild(bar);

    body.appendChild(name);
    body.appendChild(status);
    body.appendChild(progress);

    item.appendChild(meta);
    item.appendChild(body);
    messageList.appendChild(item);
    messageList.scrollTop = messageList.scrollHeight;
    return { item, status, bar };
  }

  async function uploadFile(file) {
    requestSocketPause("upload");

    const clientMsgId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `cm_${Date.now()}_${Math.random().toString(16).slice(2)}`;

    const ui = createUploadItem(file);
    ui.status.textContent = t("initializing");

    const form = new FormData();
    form.append("file", file);
    form.append("client_msg_id", clientMsgId);
    form.append("chunked", "1");
    form.append("create_message", "1");
    form.append("mime_type", file.type || "");

    try {
      const result = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/ui/upload");
        xhr.responseType = "json";

        xhr.upload.onprogress = (event) => {
          if (!event.lengthComputable) return;
          const percent = Math.min(100, Math.max(0, Math.round((event.loaded / event.total) * 100)));
          ui.bar.style.width = `${percent}%`;
          ui.status.textContent = `${t("uploading")} (${percent}%)`;
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(xhr.response);
          } else {
            reject(new Error(`upload failed: ${xhr.status}`));
          }
        };

        xhr.onerror = () => reject(new Error("upload network error"));
        xhr.onabort = () => reject(new Error("upload aborted"));

        xhr.send(form);
      });

      const ok = result && (result.ok === true || result.code === 0);
      if (!ok) {
        throw new Error((result && (result.error || result.message)) || "upload failed");
      }

      const data = result.data || result;
      const fileData = data.file;
      const messageData = data.message;

      const nowTs = new Date().toLocaleTimeString(currentLocale, { hour12: false });

      if (messageData) {
        const message = { ...messageData };
        if (!message.ts) message.ts = nowTs;
        if ((!message.file || !message.file.file_id) && fileData) {
          const fileEntry = fileData;
          message.file = {
            file_id: fileEntry.file_id,
            original_name: fileEntry.filename,
            size: fileEntry.size,
            mime: fileEntry.mime_type,
            url: fileEntry.inline_url || fileEntry.url,
            inline_url: fileEntry.inline_url || fileEntry.url,
            download_url: fileEntry.download_url || fileEntry.url,
            alias_url: fileEntry.alias_url || "",
          };
        }
        if (!message.kind) message.kind = message.file ? "file" : "text";
        renderMessage(message);
      } else if (fileData) {
        const fileEntry = fileData;
        renderMessage({
          user: currentUsername || t("selfName"),
          ts: nowTs,
          kind: "file",
          text: fileEntry.filename || t("unnamedFile"),
          file: {
            file_id: fileEntry.file_id,
            original_name: fileEntry.filename,
            size: fileEntry.size,
            mime: fileEntry.mime_type,
            url: fileEntry.inline_url || fileEntry.url,
            inline_url: fileEntry.inline_url || fileEntry.url,
            download_url: fileEntry.download_url || fileEntry.url,
            alias_url: fileEntry.alias_url || "",
          },
          client_msg_id: clientMsgId,
          created_at: new Date().toISOString(),
          _local_only: true,
        });
      }

      ui.status.textContent = t("done");
      ui.bar.style.width = "100%";
    } catch (error) {
      ui.status.textContent = t("failed");
      logError("upload failed", error);
    } finally {
      releaseSocketPause("upload");
    }
  }

  function formatBytes(size) {
    if (!Number.isFinite(size) || size <= 0) {
      return "0 B";
    }
    const units = ["B", "KB", "MB", "GB", "TB"];
    const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
    const value = size / Math.pow(1024, index);
    return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
  }

  function updateOverflow() {
    const isOverflowing = terminalWrapper.scrollWidth > terminalWrapper.clientWidth;
    if (isOverflowing) {
      terminalMore.classList.remove("hidden");
    } else {
      terminalMore.classList.add("hidden");
      terminalDropdown.classList.add("hidden");
    }
  }

  function renderTerminals(list) {
    terminalWrapper.innerHTML = "";
    list.forEach((name) => {
      const pill = document.createElement("span");
      pill.className = "terminal-pill";
      pill.textContent = name;
      terminalWrapper.appendChild(pill);
    });

    terminalDropdown.innerHTML = "";
    list.forEach((name) => {
      const row = document.createElement("div");
      row.className = "dropdown-item";
      row.textContent = name;
      terminalDropdown.appendChild(row);
    });

    requestAnimationFrame(updateOverflow);
  }

  function persistUsername(username) {
    currentUsername = username;
    try {
      const key = getBrowserStorageKey();
      localStorage.setItem(key, username);
    } catch (_error) {
      // Ignore localStorage errors.
    }
  }

  function submitRegister(username, isAuto = false) {
    if (!socket) {
      setLoginError(t("socketLoadFailed"));
      logError("submit blocked: socket is null");
      return;
    }

    if (!socket.connected) {
      setLoginError(t("connectionNotReady"));
      logError("submit blocked: socket not connected");
      return;
    }

    const normalized = (username || "").trim();
    if (!normalized) {
      setLoginError(t("enterTerminalName"));
      log("submit blocked: username empty");
      return;
    }

    if (registerInFlight) {
      log("register skipped: request already in flight", { isAuto });
      return;
    }

    registerInFlight = true;
    loginButton.disabled = true;
    setLoginError("");
    log("emit register", { username: normalized, isAuto });

    let ackDone = false;
    const ackTimer = setTimeout(() => {
      if (ackDone) {
        return;
      }
      ackDone = true;
      registerInFlight = false;
      loginButton.disabled = false;
      setLoginError(t("registerTimeout"));
      logError("register ack timeout", REGISTER_ACK_TIMEOUT_MS);
    }, REGISTER_ACK_TIMEOUT_MS);

    socket.emit("register", { username: normalized }, (response) => {
      if (ackDone) {
        return;
      }
      ackDone = true;
      clearTimeout(ackTimer);
      registerInFlight = false;
      loginButton.disabled = false;

      log("register ack", response);
      if (response && response.ok) {
        persistUsername(normalized);
        loginInput.value = normalized;
        loginMask.classList.add("hidden");
        messageInput.focus();
        return;
      }

      if (!isAuto) {
        setLoginError((response && response.error) || t("loginFailedRetry"));
      }
    });
  }

  terminalMore.addEventListener("click", () => {
    terminalDropdown.classList.toggle("hidden");
  });

  document.addEventListener("click", () => {
    hideFileContextMenu();
  });
  document.addEventListener("scroll", () => {
    hideFileContextMenu();
  }, true);
  window.addEventListener("resize", () => {
    hideFileContextMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideFileContextMenu();
    }
  });

  window.addEventListener("resize", updateOverflow);
  window.addEventListener("focus", () => {
    if (pickerPauseActive) {
      endPickerPause();
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (!isAndroid || !pauseSocketOnAndroidUpload) {
      return;
    }
    if (document.hidden) {
      if (Date.now() - pickerRequestedAt < 2000) {
        beginPickerPause();
      }
      return;
    }
    if (pickerPauseActive) {
      endPickerPause();
    }
  });

  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    log("login submit triggered", {
      valueLength: loginInput.value.length,
      connected: socket ? socket.connected : false,
    });

    try {
      submitRegister(loginInput.value, false);
    } catch (error) {
      loginButton.disabled = false;
      setLoginError(t("unexpectedLoginError"));
      logError("submit exception", error);
    }
  });

  messageForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!socket || !socket.connected) {
      logError("message submit blocked: socket unavailable");
      return;
    }
    const text = messageInput.value.trim();
    if (!text) {
      return;
    }
    socket.emit("message", { text });
    messageInput.value = "";
  });

  if (fileInput) {
    if (uploadLabelNode) {
      uploadLabelNode.addEventListener("click", () => {
        markPickerRequest();
      });
      uploadLabelNode.addEventListener("touchstart", () => {
        markPickerRequest();
      });
    }
    fileInput.addEventListener("click", () => {
      markPickerRequest();
    });
    fileInput.addEventListener("change", () => {
      const files = Array.from(fileInput.files || []);
      if (!files.length) {
        endPickerPause();
        return;
      }
      files.forEach((file) => uploadFile(file));
      fileInput.value = "";
      endPickerPause();
    });
  }

  function isFileDrag(event) {
    const types = event.dataTransfer ? Array.from(event.dataTransfer.types || []) : [];
    return types.includes("Files");
  }

  window.addEventListener("dragenter", (event) => {
    if (!isFileDrag(event)) {
      return;
    }
    event.preventDefault();
  });

  window.addEventListener("dragover", (event) => {
    if (!isFileDrag(event)) {
      return;
    }
    event.preventDefault();
  });

  window.addEventListener("dragleave", (event) => {
    if (!isFileDrag(event)) {
      return;
    }
    event.preventDefault();
  });

  window.addEventListener("drop", (event) => {
    if (!isFileDrag(event)) {
      return;
    }
    event.preventDefault();
    const files = Array.from(event.dataTransfer ? event.dataTransfer.files || [] : []);
    if (!files.length) {
      return;
    }
    files.forEach((file) => uploadFile(file));
  });

  if (socket) {
    socket.onAny((eventName, ...args) => {
      log("socket event", eventName, args);
    });

    socket.on("history", (history) => {
      messageList.innerHTML = "";
      renderedFileIds.clear();
      renderedClientMsgIds.clear();
      history.forEach(renderMessage);
    });

    socket.on("message", (message) => {
      renderMessage(message);
    });

    socket.on("clients", (clients) => {
      renderTerminals(clients);
    });

    socket.on("connect", () => {
      log("socket connected", socket.id);
      setLoginError("");
      if (currentUsername) {
        submitRegister(currentUsername, true);
      } else {
        loginMask.classList.remove("hidden");
        loginInput.focus();
      }
    });

    socket.on("disconnect", (reason) => {
      if (suppressDisconnectNotice || pauseRefCount > 0) {
        suppressDisconnectNotice = false;
        log("socket disconnect suppressed", reason);
        return;
      }
      logError("socket disconnected", reason);
      loginMask.classList.remove("hidden");
      setLoginError(t("connectionClosed"));
    });

    socket.on("connect_error", (error) => {
      logError("connect_error", error);
      setLoginError(t("cannotConnectServer"));
    });
  } else {
    setLoginError(t("socketScriptFailed"));
  }
}

(async () => {
  try {
    const loaded = await ensureSocketIoLoaded();
    const socket = loaded && typeof io === "function" ? io() : null;
    if (!socket) {
      logError("socket init failed: io unavailable");
    }
    initApp(socket);
  } catch (error) {
    logError("bootstrap failed", error);
  }
})();
