// Module initialization and composition
function initializeModules(socket) {
  const i18n = getI18nRuntime();
  window.i18n = i18n; // Make available globally for other modules
  const t = i18n.t;

  document.documentElement.lang = i18n.locale;

  // Initialize UI elements
  const ui = initializeUiElements();
  ui.socket = socket; // Attach socket to ui object
  const uploadLabelNode = applyI18nToUI(t, ui);

  log("initApp", {
    hasSocket: Boolean(socket),
    hasLoginForm: Boolean(ui.loginForm),
    hasLoginInput: Boolean(ui.loginInput),
    hasMessageForm: Boolean(ui.messageForm),
  });

  // Initialize message view
  let messageView = {
    renderMessage: (_message) => {
      logError("message view unavailable");
    },
    hideFileContextMenu: () => {},
  };

  const messageViewModule = window.MyFileHelperMessageView;
  if (messageViewModule && typeof messageViewModule.createMessageView === "function") {
    try {
      const pendingUploads = new Map();
      window.renderedFileIds = new Set();
      window.renderedClientMsgIds = new Set();
      let latestServerCreatedAt = "";

      messageView = messageViewModule.createMessageView({
        messageList: ui.messageList,
        loginMask: ui.loginMask,
        t,
        logError,
        sendClientLog,
        serializeLogValue,
        pendingUploads,
        renderedFileIds: window.renderedFileIds,
        renderedClientMsgIds: window.renderedClientMsgIds,
        getLatestServerCreatedAt: () => latestServerCreatedAt,
        setLatestServerCreatedAt: (value) => {
          latestServerCreatedAt = value;
        },
      });
    } catch (error) {
      logError("message view init failed", error);
    }
  }

  // Initialize socket pause manager (needed by uploadFlow)
  const socketPause = createSocketPauseManager(socket);

  // Initialize login manager (needed by uploadFlow)
  const loginManager = createLoginManager(socket, ui, t);
  loginManager.loadCachedUsername(ui);

  // Initialize upload flow
  const uploadModule = window.MyFileHelperUploadFlow;
  const uploadFlow =
    uploadModule && typeof uploadModule.createUploadFlow === "function"
      ? uploadModule.createUploadFlow({
          messageList: ui.messageList,
          getCurrentUsername: () => loginManager.getCurrentUsername(),
          currentLocale: i18n.locale,
          t,
          requestSocketPause: () => socketPause.requestSocketPause("upload"),
          releaseSocketPause: () => socketPause.releaseSocketPause("upload"),
          renderMessage: (message) => messageView.renderMessage(message),
          logError,
        })
      : null;
  window.uploadFlow = uploadFlow; // Make available globally

  // Attach event listeners
  attachUIEventListeners(ui, loginManager, uploadFlow, messageView, socketPause, t);
  attachDragDropListeners(ui, uploadFlow);
  attachSocketEventListeners(socket, ui, t, loginManager, messageView, socketPause, renderTerminals);

  return { ui, messageView, uploadFlow, loginManager, socketPause };
}



