// Message-view composition layer for renderer and preview modules.
(function () {
  /**
   * Dependency contract:
   * - deps must satisfy both preview and renderer factories.
   * - window.MyFileHelperFilePreview and window.MyFileHelperMessageRenderer must be loaded first.
   * Returns: { renderMessage(message), hideFileContextMenu() }
   */
  function createMessageView(deps) {
    const previewModule = window.MyFileHelperFilePreview;
    const rendererModule = window.MyFileHelperMessageRenderer;

    if (!previewModule || typeof previewModule.createFilePreviewHelpers !== "function") {
      throw new Error("file preview module unavailable");
    }
    if (!rendererModule || typeof rendererModule.createMessageRenderer !== "function") {
      throw new Error("message renderer module unavailable");
    }

    const previewHelpers = previewModule.createFilePreviewHelpers({
      t: deps.t,
      logError: deps.logError,
    });
    const renderer = rendererModule.createMessageRenderer({
      ...deps,
      buildFilePreview: previewHelpers.buildFilePreview,
    });

    return {
      renderMessage: renderer.renderMessage,
      hideFileContextMenu: previewHelpers.hideFileContextMenu,
    };
  }

  window.MyFileHelperMessageView = {
    createMessageView,
  };
})();



