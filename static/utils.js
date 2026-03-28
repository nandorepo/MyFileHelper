// Utility functions: logging, storage, serialization
const DEBUG = true;
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

function getI18nRuntime() {
  const provider = window.MyFileHelperI18n;
  if (provider && typeof provider.createI18n === "function") {
    return provider.createI18n();
  }

  const locale = "en-US";
  return {
    locale,
    t: (key) => key,
  };
}

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

async function ensureSocketIoLoaded() {
  const loader = window.MyFileHelperSocketLoader;
  if (!loader || typeof loader.ensureSocketIoLoaded !== "function") {
    logError("socket loader unavailable");
    return typeof io === "function";
  }
  return loader.ensureSocketIoLoaded({ log, logError });
}

