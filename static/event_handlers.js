// Event listeners and handlers
function attachUIEventListeners(ui, loginManager, uploadFlow, messageView, socketPause, t) {
  // Terminal dropdown toggle
  ui.terminalMore.addEventListener("click", () => {
    ui.terminalDropdown.classList.toggle("hidden");
  });

  // Context menu hiding
  document.addEventListener("click", () => {
    messageView.hideFileContextMenu();
  });
  document.addEventListener("scroll", () => {
    messageView.hideFileContextMenu();
  }, true);
  window.addEventListener("resize", () => {
    messageView.hideFileContextMenu();
    updateOverflow(ui);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      messageView.hideFileContextMenu();
    }
  });

  // Window events
  window.addEventListener("focus", () => {
    if (socketPause.getPickerPauseActive()) {
      socketPause.endPickerPause();
    }
  });

  // Visibility change (Android support)
  document.addEventListener("visibilitychange", () => {
    if (!socketPause.isAndroid || !socketPause.pauseSocketOnAndroidUpload) {
      return;
    }
    if (document.hidden) {
      if (Date.now() - socketPause.getPickerRequestedAt() < 2000) {
        socketPause.beginPickerPause();
      }
      return;
    }
    if (socketPause.getPickerPauseActive()) {
      socketPause.endPickerPause();
    }
  });

  // Login form
  ui.loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    log("login submit triggered", {
      valueLength: ui.loginInput.value.length,
      connected: ui.socket ? ui.socket.connected : false,
    });

    try {
      loginManager.submitRegister(ui.loginInput.value, false);
    } catch (error) {
      ui.loginButton.disabled = false;
      setLoginError(ui, t, t("unexpectedLoginError"));
      logError("submit exception", error);
    }
  });

  // Message form
  ui.messageForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!ui.socket || !ui.socket.connected) {
      logError("message submit blocked: socket unavailable");
      return;
    }
    const text = ui.messageInput.value.trim();
    if (!text) {
      return;
    }
    ui.socket.emit("message", { text });
    ui.messageInput.value = "";
  });

  // File input and upload label
  if (ui.fileInput) {
    const uploadLabelNode = document.querySelector("label[for='file-input']");
    if (uploadLabelNode) {
      uploadLabelNode.addEventListener("click", () => {
        socketPause.markPickerRequest();
      });
      uploadLabelNode.addEventListener("touchstart", () => {
        socketPause.markPickerRequest();
      });
    }
    ui.fileInput.addEventListener("click", () => {
      socketPause.markPickerRequest();
    });
    ui.fileInput.addEventListener("change", () => {
      const files = Array.from(ui.fileInput.files || []);
      if (!files.length) {
        socketPause.endPickerPause();
        return;
      }
      files.forEach((file) => uploadFile(file));
      ui.fileInput.value = "";
      socketPause.endPickerPause();
    });
  }
}

function attachDragDropListeners(ui, uploadFlow) {
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
}

async function uploadFile(file) {
  if (window.uploadFlow && typeof window.uploadFlow.uploadFile === "function") {
    await window.uploadFlow.uploadFile(file);
    return;
  }
  logError("upload flow unavailable");
}

