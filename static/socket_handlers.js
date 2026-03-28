// Socket event handlers
function attachSocketEventListeners(socket, ui, t, loginManager, messageView, socketPause, renderTerminalsFunc) {
  if (!socket) {
    setLoginError(ui, t, t("socketScriptFailed"));
    return;
  }

  socket.onAny((eventName, ...args) => {
    log("socket event", eventName, args);
  });

  socket.on("history", (history) => {
    ui.messageList.innerHTML = "";
    window.renderedFileIds?.clear?.();
    window.renderedClientMsgIds?.clear?.();
    history.forEach((message) => messageView.renderMessage(message));
  });

  socket.on("message", (message) => {
    messageView.renderMessage(message);
  });

  socket.on("clients", (clients) => {
    renderTerminalsFunc(ui, clients);
  });

  socket.on("connect", () => {
    log("socket connected", socket.id);
    setLoginError(ui, t, "");
    const currentUsername = loginManager.getCurrentUsername();
    if (currentUsername) {
      loginManager.submitRegister(currentUsername, true);
    } else {
      ui.loginMask.classList.remove("hidden");
      ui.loginInput.focus();
    }
  });

  socket.on("disconnect", (reason) => {
    const suppressDisconnect = socketPause.getSuppressDisconnectNotice();
    if (suppressDisconnect || socketPause.getPauseRefCount() > 0) {
      socketPause.setSuppressDisconnectNotice(false);
      log("socket disconnect suppressed", reason);
      return;
    }
    logError("socket disconnected", reason);
    ui.loginMask.classList.remove("hidden");
    setLoginError(ui, t, t("connectionClosed"));
  });

  socket.on("connect_error", (error) => {
    logError("connect_error", error);
    setLoginError(ui, t, t("cannotConnectServer"));
  });
}

