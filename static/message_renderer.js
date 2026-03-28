// Message normalization, de-dup and DOM render flow.
(function () {
  /**
   * Dependency contract:
   * - deps.messageList/loginMask: DOM anchors
   * - deps.t/logError/sendClientLog/serializeLogValue: UI + logging hooks
   * - deps.pendingUploads/renderedFileIds/renderedClientMsgIds: de-dup state
   * - deps.getLatestServerCreatedAt/setLatestServerCreatedAt: timeline state access
   * - deps.buildFilePreview(file): preview builder
   * Returns: { renderMessage(message) }
   */
  function createMessageRenderer(deps) {
    const {
      messageList,
      loginMask,
      t,
      logError,
      sendClientLog,
      serializeLogValue,
      pendingUploads,
      renderedFileIds,
      renderedClientMsgIds,
      getLatestServerCreatedAt,
      setLatestServerCreatedAt,
      buildFilePreview,
    } = deps;

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

    function normalizeFileMessage(message) {
      if (!message || message.kind !== "file" || message.file || !Array.isArray(message.attachments)) {
        return;
      }
      const first = message.attachments[0];
      if (!first) {
        return;
      }
      message.file = {
        file_id: first.file_id,
        original_name: first.filename,
        size: first.size,
        mime: first.mime_type,
        url: first.inline_url || first.url,
        inline_url: first.inline_url || first.url,
        download_url: first.download_url || first.url,
        alias_url: first.alias_url || "",
      };
      if (!message.text) {
        message.text = first.filename || t("unnamedFile");
      }
    }

    function trackLatestCreatedAt(message) {
      if (!message || !message.created_at || message._local_only) {
        return;
      }
      const latestServerCreatedAt = getLatestServerCreatedAt();
      if (!latestServerCreatedAt) {
        setLatestServerCreatedAt(message.created_at);
        return;
      }

      const nextTime = Date.parse(message.created_at);
      const prevTime = Date.parse(latestServerCreatedAt);
      if (!Number.isNaN(nextTime) && !Number.isNaN(prevTime) && nextTime > prevTime) {
        setLatestServerCreatedAt(message.created_at);
      }
    }

    function renderMessage(message) {
      try {
        normalizeFileMessage(message);
        trackLatestCreatedAt(message);

        const fileId = message && message.file ? message.file.file_id : null;
        const clientMsgId = message ? message.client_msg_id : null;
        sendClientLog("info", [
          "renderMessage",
          {
            fileId,
            clientMsgId,
            listExists: Boolean(messageList),
            listCount: messageList ? messageList.children.length : 0,
            loginHidden: loginMask ? loginMask.classList.contains("hidden") : null,
            pendingByClient: clientMsgId ? pendingUploads.has(clientMsgId) : false,
            pendingByFile: fileId ? pendingUploads.has(fileId) : false,
          },
        ]);

        if (clientMsgId && pendingUploads.has(clientMsgId)) {
          const existing = pendingUploads.get(clientMsgId);
          const replacement = buildMessageElement(message);
          if (existing && existing.isConnected) {
            existing.replaceWith(replacement);
          } else {
            messageList.appendChild(replacement);
          }
          pendingUploads.delete(clientMsgId);
          if (fileId) {
            pendingUploads.delete(fileId);
          }
          if (fileId) {
            renderedFileIds.add(fileId);
          }
          renderedClientMsgIds.add(clientMsgId);
          messageList.scrollTop = messageList.scrollHeight;
          sendClientLog("info", ["renderMessage_done", "pending_client"]);
          return;
        }

        if (fileId && pendingUploads.has(fileId)) {
          const existing = pendingUploads.get(fileId);
          const replacement = buildMessageElement(message);
          if (existing && existing.isConnected) {
            existing.replaceWith(replacement);
          } else {
            messageList.appendChild(replacement);
          }
          pendingUploads.delete(fileId);
          if (clientMsgId) {
            pendingUploads.delete(clientMsgId);
          }
          renderedFileIds.add(fileId);
          if (clientMsgId) {
            renderedClientMsgIds.add(clientMsgId);
          }
          messageList.scrollTop = messageList.scrollHeight;
          sendClientLog("info", ["renderMessage_done", "pending_file"]);
          return;
        }

        if (fileId && renderedFileIds.has(fileId)) {
          sendClientLog("info", ["renderMessage_skip", "file_dup"]);
          return;
        }
        if (clientMsgId && renderedClientMsgIds.has(clientMsgId)) {
          sendClientLog("info", ["renderMessage_skip", "client_dup"]);
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
        sendClientLog("info", ["renderMessage_done", "append"]);
      } catch (error) {
        logError("renderMessage failed", error);
        sendClientLog("error", ["renderMessage_failed", serializeLogValue(error)]);
      }
    }

    return {
      renderMessage,
    };
  }

  window.MyFileHelperMessageRenderer = {
    createMessageRenderer,
  };
})();


