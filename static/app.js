const DEBUG = true;
const REGISTER_ACK_TIMEOUT_MS = 8000;
const CLIENT_LOG_ENDPOINT = "/api/client-log";
const TERMINAL_NAME_STORAGE_KEY = "mytransfer_terminal_name";
const UPLOAD_INIT_ENDPOINT = "/api/upload/init";
const UPLOAD_CHUNK_ENDPOINT = "/api/upload/chunk";
const UPLOAD_COMPLETE_ENDPOINT = "/api/upload/complete";

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
  const payload = {
    ts: new Date().toISOString(),
    level,
    page: window.location.href,
    args: args.map((item) => serializeLogValue(item)),
  };

  fetch(CLIENT_LOG_ENDPOINT, {
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

  let registerInFlight = false;
  let currentUsername = "";
  const pendingUploads = new Map();
  const renderedFileIds = new Set();
  const renderedClientMsgIds = new Set();

  try {
    const cached = (localStorage.getItem(TERMINAL_NAME_STORAGE_KEY) || "").trim();
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

  function buildFilePreview(file) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-file";

    const preview = document.createElement("div");
    preview.className = "file-preview";

    if (file.mime && file.mime.startsWith("image/")) {
      const img = document.createElement("img");
      img.src = file.url;
      img.alt = file.original_name;
      preview.appendChild(img);
    } else if (file.mime && file.mime.startsWith("audio/")) {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.src = file.url;
      preview.appendChild(audio);
    } else if (file.mime && file.mime.startsWith("video/")) {
      const video = document.createElement("video");
      video.controls = true;
      video.preload = "metadata";
      video.src = file.url;
      preview.appendChild(video);
    } else {
      preview.textContent = "未预览文件";
    }

    const name = document.createElement("div");
    name.className = "file-name";
    name.textContent = file.original_name || "未命名文件";

    const actions = document.createElement("div");
    actions.className = "file-actions";
    const sizeText = document.createElement("span");
    sizeText.textContent = formatBytes(file.size);
    const link = document.createElement("a");
    link.className = "download-link";
    link.href = `${file.url}?download=1`;
    link.textContent = "下载";
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
    const fileId = message && message.file ? message.file.file_id : null;
    const clientMsgId = message ? message.client_msg_id : null;
    if (clientMsgId && pendingUploads.has(clientMsgId)) {
      const existing = pendingUploads.get(clientMsgId);
      const replacement = buildMessageElement(message);
      existing.replaceWith(replacement);
      pendingUploads.delete(clientMsgId);
      if (fileId) {
        pendingUploads.delete(fileId);
      }
      if (fileId) {
        renderedFileIds.add(fileId);
      }
      renderedClientMsgIds.add(clientMsgId);
      messageList.scrollTop = messageList.scrollHeight;
      return;
    }

    if (fileId && pendingUploads.has(fileId)) {
      const existing = pendingUploads.get(fileId);
      const replacement = buildMessageElement(message);
      existing.replaceWith(replacement);
      pendingUploads.delete(fileId);
      if (clientMsgId) {
        pendingUploads.delete(clientMsgId);
      }
      renderedFileIds.add(fileId);
      if (clientMsgId) {
        renderedClientMsgIds.add(clientMsgId);
      }
      messageList.scrollTop = messageList.scrollHeight;
      return;
    }

    if (fileId && renderedFileIds.has(fileId)) {
      return;
    }
    if (clientMsgId && renderedClientMsgIds.has(clientMsgId)) {
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
    user.textContent = currentUsername || "我";
    const ts = document.createElement("span");
    ts.textContent = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    meta.appendChild(user);
    meta.appendChild(ts);

    const body = document.createElement("div");
    body.className = "message-file";
    const name = document.createElement("div");
    name.className = "upload-name";
    name.textContent = file.name;
    const status = document.createElement("div");
    status.className = "upload-meta";
    status.textContent = "等待中";
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
    const clientMsgId =
      typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `cm_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    const ui = createUploadItem(file);
    ui.status.textContent = "初始化中";

    let initData;
    try {
      const initResp = await fetch(UPLOAD_INIT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          size: file.size,
          mime: file.type,
          client_msg_id: clientMsgId,
        }),
      });
      initData = await initResp.json();
      if (!initResp.ok || !initData.ok) {
        throw new Error(initData.error || "初始化失败");
      }
    } catch (error) {
      ui.status.textContent = "初始化失败";
      logError("upload init failed", error);
      return;
    }

    const uploadId = initData.upload_id;
    ui.item.dataset.uploadId = uploadId;
    ui.item.dataset.clientMsgId = clientMsgId;
    pendingUploads.set(uploadId, ui.item);
    pendingUploads.set(clientMsgId, ui.item);
    const chunkSize = initData.chunk_size || 10 * 1024 * 1024;
    const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize));
    const concurrency = Math.min(initData.max_concurrency || 3, totalChunks);
    let completed = 0;

    async function uploadChunk(index) {
      const start = index * chunkSize;
      const end = Math.min(start + chunkSize, file.size);
      const form = new FormData();
      form.append("upload_id", uploadId);
      form.append("index", index);
      form.append("total_chunks", totalChunks);
      form.append("chunk", file.slice(start, end), file.name);
      const response = await fetch(UPLOAD_CHUNK_ENDPOINT, { method: "POST", body: form });
      if (!response.ok) {
        let message = `chunk ${index} failed`;
        try {
          const err = await response.json();
          message = err.error || message;
        } catch (_error) {
          // ignore json parse errors
        }
        throw new Error(message);
      }
    }

    const queue = Array.from({ length: totalChunks }, (_, index) => index);
    ui.status.textContent = "上传中";

    async function worker() {
      while (queue.length) {
        const index = queue.shift();
        if (index === undefined) {
          return;
        }
        await uploadChunk(index);
        completed += 1;
        const percent = Math.round((completed / totalChunks) * 100);
        ui.bar.style.width = `${percent}%`;
        ui.status.textContent = `${formatBytes(file.size)} · ${percent}%`;
      }
    }

    try {
      await Promise.all(Array.from({ length: concurrency }, () => worker()));
      const completeResp = await fetch(UPLOAD_COMPLETE_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upload_id: uploadId, total_chunks: totalChunks }),
      });
      const completeData = await completeResp.json();
      if (!completeResp.ok || !completeData.ok) {
        throw new Error(completeData.error || "合并失败");
      }
      ui.status.textContent = "完成";
      ui.bar.style.width = "100%";
    } catch (error) {
      ui.status.textContent = "失败";
      logError("upload failed", error);
    }
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
      localStorage.setItem(TERMINAL_NAME_STORAGE_KEY, username);
    } catch (_error) {
      // Ignore localStorage errors.
    }
  }

  function submitRegister(username, isAuto = false) {
    if (!socket) {
      setLoginError("Socket.IO 加载失败，请检查网络或刷新重试。");
      logError("submit blocked: socket is null");
      return;
    }

    if (!socket.connected) {
      setLoginError("连接未建立，请稍后再试。");
      logError("submit blocked: socket not connected");
      return;
    }

    const normalized = (username || "").trim();
    if (!normalized) {
      setLoginError("请输入终端名称。");
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
      setLoginError("注册超时，请查看 Console 日志并重试。");
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
        setLoginError((response && response.error) || "进入失败，请重试。");
      }
    });
  }

  terminalMore.addEventListener("click", () => {
    terminalDropdown.classList.toggle("hidden");
  });

  window.addEventListener("resize", updateOverflow);

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
      setLoginError("进入时发生异常，请查看 Console。");
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
    fileInput.addEventListener("change", () => {
      const files = Array.from(fileInput.files || []);
      if (!files.length) {
        return;
      }
      files.forEach((file) => uploadFile(file));
      fileInput.value = "";
    });
  }

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
      logError("socket disconnected", reason);
      loginMask.classList.remove("hidden");
      setLoginError("连接已断开，请稍后重试。");
    });

    socket.on("connect_error", (error) => {
      logError("connect_error", error);
      setLoginError("无法连接服务器，请检查后端是否启动。");
    });
  } else {
    setLoginError("Socket.IO 脚本加载失败，已尝试多个地址。请检查网络或代理设置。");
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
