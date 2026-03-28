// Socket.IO script loader with fallback candidates.
(function () {
  const DEFAULT_CANDIDATES = [
    "/static/vendor/socket.io.min.js",
    "/socket.io/socket.io.js",
    "https://cdn.socket.io/4.7.5/socket.io.min.js",
    "https://cdn.jsdelivr.net/npm/socket.io-client@4.7.5/dist/socket.io.min.js",
    "https://unpkg.com/socket.io-client@4.7.5/dist/socket.io.min.js",
    "https://cdn.bootcdn.net/ajax/libs/socket.io/4.7.5/socket.io.min.js",
  ];

  function noop() {}

  function loadScript(src, log, logError) {
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
        const error = new Error("load failed: " + src);
        logError(error.message);
        reject(error);
      };
      document.head.appendChild(script);
    });
  }

  async function ensureSocketIoLoaded(options) {
    const opts = options || {};
    const log = typeof opts.log === "function" ? opts.log : noop;
    const logError = typeof opts.logError === "function" ? opts.logError : noop;
    const candidates = Array.isArray(opts.candidates) && opts.candidates.length ? opts.candidates : DEFAULT_CANDIDATES;

    if (typeof io === "function") {
      log("io already available before dynamic load");
      return true;
    }

    for (const src of candidates) {
      try {
        await loadScript(src, log, logError);
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

  window.MyFileHelperSocketLoader = {
    ensureSocketIoLoaded,
  };
})();


