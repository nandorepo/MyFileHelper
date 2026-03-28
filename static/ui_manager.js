// UI initialization and management
function initializeUiElements() {
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

  return {
    loginMask,
    loginForm,
    loginInput,
    loginError,
    loginButton,
    messageForm,
    messageInput,
    messageList,
    terminalWrapper,
    terminalMore,
    terminalDropdown,
    fileInput,
  };
}

function applyI18nToUI(t, ui) {
  const terminalLabel = document.querySelector(".terminal-label");
  const brandTitle = document.querySelector(".brand-title");
  const uploadLabelNode = document.querySelector("label[for='file-input']");
  const sendButtonNode = ui.messageForm.querySelector(".send-button");
  const loginTitleNode = document.querySelector(".login-title");

  if (brandTitle) {
    brandTitle.textContent = t("appTitle");
  }
  if (terminalLabel) {
    terminalLabel.textContent = t("terminalLabel");
  }
  if (ui.terminalMore) {
    ui.terminalMore.textContent = t("more");
  }
  if (ui.messageInput) {
    ui.messageInput.placeholder = t("messagePlaceholder");
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
  if (ui.loginInput) {
    ui.loginInput.placeholder = t("loginPlaceholder");
  }
  if (ui.loginButton) {
    ui.loginButton.textContent = t("join");
  }

  return uploadLabelNode;
}

function setLoginError(ui, t, text) {
  log("setLoginError", text || "<empty>");
  if (!text) {
    ui.loginError.textContent = "";
    ui.loginError.classList.add("hidden");
    return;
  }
  ui.loginError.textContent = text;
  ui.loginError.classList.remove("hidden");
}

function updateOverflow(ui) {
  const isOverflowing = ui.terminalWrapper.scrollWidth > ui.terminalWrapper.clientWidth;
  if (isOverflowing) {
    ui.terminalMore.classList.remove("hidden");
  } else {
    ui.terminalMore.classList.add("hidden");
    ui.terminalDropdown.classList.add("hidden");
  }
}

function renderTerminals(ui, list) {
  ui.terminalWrapper.innerHTML = "";
  list.forEach((name) => {
    const pill = document.createElement("span");
    pill.className = "terminal-pill";
    pill.textContent = name;
    ui.terminalWrapper.appendChild(pill);
  });

  ui.terminalDropdown.innerHTML = "";
  list.forEach((name) => {
    const row = document.createElement("div");
    row.className = "dropdown-item";
    row.textContent = name;
    ui.terminalDropdown.appendChild(row);
  });

  requestAnimationFrame(() => updateOverflow(ui));
}

