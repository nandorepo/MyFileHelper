// Login and registration management
const REGISTER_ACK_TIMEOUT_MS = 8000;

function createLoginManager(socket, ui, t) {
  let registerInFlight = false;
  let currentUsername = "";

  function loadCachedUsername(ui) {
    try {
      const key = getBrowserStorageKey();
      const cached = (localStorage.getItem(key) || "").trim();
      if (cached) {
        currentUsername = cached;
        ui.loginInput.value = cached;
      }
    } catch (_error) {
      // Ignore localStorage errors.
    }
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
      setLoginError(ui, t, t("socketLoadFailed"));
      logError("submit blocked: socket is null");
      return;
    }

    if (!socket.connected) {
      setLoginError(ui, t, t("connectionNotReady"));
      logError("submit blocked: socket not connected");
      return;
    }

    const normalized = (username || "").trim();
    if (!normalized) {
      setLoginError(ui, t, t("enterTerminalName"));
      log("submit blocked: username empty");
      return;
    }

    if (registerInFlight) {
      log("register skipped: request already in flight", { isAuto });
      return;
    }

    registerInFlight = true;
    ui.loginButton.disabled = true;
    setLoginError(ui, t, "");
    log("emit register", { username: normalized, isAuto });

    let ackDone = false;
    const ackTimer = setTimeout(() => {
      if (ackDone) {
        return;
      }
      ackDone = true;
      registerInFlight = false;
      ui.loginButton.disabled = false;
      setLoginError(ui, t, t("registerTimeout"));
      logError("register ack timeout", REGISTER_ACK_TIMEOUT_MS);
    }, REGISTER_ACK_TIMEOUT_MS);

    socket.emit("register", { username: normalized }, (response) => {
      if (ackDone) {
        return;
      }
      ackDone = true;
      clearTimeout(ackTimer);
      registerInFlight = false;
      ui.loginButton.disabled = false;

      log("register ack", response);
      if (response && response.ok) {
        persistUsername(normalized);
        ui.loginInput.value = normalized;
        ui.loginMask.classList.add("hidden");
        ui.messageInput.focus();
        return;
      }

      if (!isAuto) {
        setLoginError(ui, t, (response && response.error) || t("loginFailedRetry"));
      }
    });
  }

  return {
    loadCachedUsername,
    persistUsername,
    submitRegister,
    getCurrentUsername: () => currentUsername,
    setCurrentUsername: (username) => {
      currentUsername = username;
    },
  };
}

