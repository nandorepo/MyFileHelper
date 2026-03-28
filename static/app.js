// Main bootstrap entry point - loads modules and initializes app
(async () => {
  try {
    const loaded = await ensureSocketIoLoaded();
    const socket = loaded && typeof io === "function" ? io() : null;
    if (!socket) {
      logError("socket init failed: io unavailable");
    }
    initializeModules(socket);
  } catch (error) {
    logError("bootstrap failed", error);
  }
})();
