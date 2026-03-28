// Upload UI state and transport orchestration.
(function () {
  function formatBytes(size) {
    if (!Number.isFinite(size) || size <= 0) {
      return "0 B";
    }
    const units = ["B", "KB", "MB", "GB", "TB"];
    const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
    const value = size / Math.pow(1024, index);
    return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
  }
  function toMessageFile(fileEntry) {
    return {
      file_id: fileEntry.file_id,
      original_name: fileEntry.filename,
      size: fileEntry.size,
      mime: fileEntry.mime_type,
      url: fileEntry.inline_url || fileEntry.url,
      inline_url: fileEntry.inline_url || fileEntry.url,
      download_url: fileEntry.download_url || fileEntry.url,
      alias_url: fileEntry.alias_url || "",
    };
  }
  function createUploadFlow(deps) {
    const {
      messageList,
      getCurrentUsername,
      currentLocale,
      t,
      requestSocketPause,
      releaseSocketPause,
      renderMessage,
      logError,
    } = deps;
    function createUploadItem(file) {
      const item = document.createElement("div");
      item.className = "message-item";
      const meta = document.createElement("div");
      meta.className = "message-meta";
      const user = document.createElement("span");
      user.className = "message-user";
      user.textContent = getCurrentUsername() || t("selfName");
      const ts = document.createElement("span");
      ts.textContent = new Date().toLocaleTimeString(currentLocale, { hour12: false });
      meta.appendChild(user);
      meta.appendChild(ts);
      const body = document.createElement("div");
      body.className = "message-file";
      const name = document.createElement("div");
      name.className = "upload-name";
      name.textContent = file.name;
      const status = document.createElement("div");
      status.className = "upload-meta";
      status.textContent = t("waiting");
      const progress = document.createElement("div");
      progress.className = "upload-progress";
      const bar = document.createElement("span");
      progress.appendChild(bar);
      body.appendChild(name);
      body.appendChild(status);
      body.appendChild(progress);
      item.appendChild(meta);
      item.appendChild(body);
      messageList.appendChild(item);
      messageList.scrollTop = messageList.scrollHeight;
      return { item, status, bar };
    }
    async function uploadFile(file) {
      requestSocketPause("upload");
      const clientMsgId =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `cm_${Date.now()}_${Math.random().toString(16).slice(2)}`;
      const ui = createUploadItem(file);
      ui.status.textContent = t("initializing");
      const form = new FormData();
      form.append("file", file);
      form.append("client_msg_id", clientMsgId);
      form.append("chunked", "1");
      form.append("create_message", "1");
      form.append("mime_type", file.type || "");
      try {
        const result = await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", "/ui/upload");
          xhr.responseType = "json";
          xhr.upload.onprogress = (event) => {
            if (!event.lengthComputable) return;
            const percent = Math.min(100, Math.max(0, Math.round((event.loaded / event.total) * 100)));
            ui.bar.style.width = `${percent}%`;
            ui.status.textContent = `${t("uploading")} (${percent}%)`;
          };
          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(xhr.response);
            } else {
              reject(new Error(`upload failed: ${xhr.status}`));
            }
          };
          xhr.onerror = () => reject(new Error("upload network error"));
          xhr.onabort = () => reject(new Error("upload aborted"));
          xhr.send(form);
        });
        const ok = result && (result.ok === true || result.code === 0);
        if (!ok) {
          throw new Error((result && (result.error || result.message)) || "upload failed");
        }
        const data = result.data || result;
        const fileData = data.file;
        const messageData = data.message;
        const nowTs = new Date().toLocaleTimeString(currentLocale, { hour12: false });
        if (messageData) {
          const message = { ...messageData };
          if (!message.ts) message.ts = nowTs;
          if ((!message.file || !message.file.file_id) && fileData) {
            message.file = toMessageFile(fileData);
          }
          if (!message.kind) message.kind = message.file ? "file" : "text";
          renderMessage(message);
        } else if (fileData) {
          renderMessage({
            user: getCurrentUsername() || t("selfName"),
            ts: nowTs,
            kind: "file",
            text: fileData.filename || t("unnamedFile"),
            file: toMessageFile(fileData),
            client_msg_id: clientMsgId,
            created_at: new Date().toISOString(),
            _local_only: true,
          });
        }
        ui.status.textContent = t("done");
        ui.bar.style.width = "100%";
      } catch (error) {
        ui.status.textContent = t("failed");
        logError("upload failed", error);
      } finally {
        releaseSocketPause("upload");
      }
    }
    return {
      formatBytes,
      uploadFile,
    };
  }
  window.MyFileHelperUploadFlow = {
    createUploadFlow,
  };
})();
