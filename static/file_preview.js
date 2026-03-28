// File preview and context-menu UI helpers.
(function () {
  const OFFICE_EXTENSIONS = new Set([
    "doc",
    "docx",
    "xls",
    "xlsx",
    "xlsm",
    "xlsb",
    "ppt",
    "pptx",
    "pps",
    "ppsx",
  ]);

  /**
   * Dependency contract:
   * - deps.t(key): i18n lookup function
   * - deps.logError(...args): error logger
   * Returns: { buildFilePreview(file), hideFileContextMenu() }
   */
  function createFilePreviewHelpers(deps) {
    const { t, logError } = deps;
    let fileContextMenu = null;

    function formatBytes(size) {
      if (!Number.isFinite(size) || size <= 0) {
        return "0 B";
      }
      const units = ["B", "KB", "MB", "GB", "TB"];
      const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
      const value = size / Math.pow(1024, index);
      return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
    }

    function getFileName(file) {
      return file.original_name || file.filename || t("unnamedFile");
    }

    function getFileMime(file) {
      return (file.mime || file.mime_type || "").toLowerCase();
    }

    function getFileExt(file) {
      const name = getFileName(file);
      const idx = name.lastIndexOf(".");
      if (idx < 0 || idx === name.length - 1) {
        return "";
      }
      return name.slice(idx + 1).toLowerCase();
    }

    function getInlineFileUrl(file) {
      return file.inline_url || file.url || file.alias_url || file.download_url || "";
    }

    function appendQueryParam(url, key, value) {
      if (!url) {
        return "";
      }
      const hasQuery = url.includes("?");
      const connector = hasQuery ? "&" : "?";
      return `${url}${connector}${encodeURIComponent(key)}=${encodeURIComponent(value)}`;
    }

    function getDownloadFileUrl(file) {
      if (file.alias_url) {
        return file.alias_url;
      }
      if (file.download_url) {
        return file.download_url;
      }
      if (file.file_id) {
        return `/media/${file.file_id}?download=1`;
      }
      return appendQueryParam(getInlineFileUrl(file), "download", "1");
    }

    function getAbsoluteFileUrl(file) {
      const url = getDownloadFileUrl(file) || getInlineFileUrl(file);
      if (!url) {
        return "";
      }
      return new URL(url, window.location.href).toString();
    }

    function triggerBrowserDownload(file) {
      const href = getDownloadFileUrl(file);
      if (!href) {
        return;
      }
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = getFileName(file);
      anchor.rel = "noopener noreferrer";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    }

    async function saveFileAs(file) {
      if (typeof window.showSaveFilePicker !== "function") {
        triggerBrowserDownload(file);
        return;
      }

      const downloadUrl = getAbsoluteFileUrl(file);
      if (!downloadUrl) {
        return;
      }

      const handle = await window.showSaveFilePicker({
        suggestedName: getFileName(file),
      });
      if (!handle) {
        return;
      }

      const response = await fetch(downloadUrl, { credentials: "same-origin" });
      if (!response.ok) {
        throw new Error(`download failed: ${response.status}`);
      }

      const writable = await handle.createWritable();
      try {
        await writable.write(await response.blob());
        await writable.close();
      } catch (error) {
        await writable.abort();
        throw error;
      }
    }

    function hideFileContextMenu() {
      if (!fileContextMenu) {
        return;
      }
      fileContextMenu.classList.add("hidden");
      fileContextMenu.style.left = "";
      fileContextMenu.style.top = "";
      fileContextMenu._file = null;
    }

    function ensureFileContextMenu() {
      if (fileContextMenu) {
        return fileContextMenu;
      }
      const menu = document.createElement("div");
      menu.className = "file-context-menu hidden";
      menu.innerHTML = `
        <button type="button" class="file-context-action" data-action="download"></button>
        <button type="button" class="file-context-action" data-action="saveAs"></button>
        <button type="button" class="file-context-action" data-action="copyLink"></button>
      `;

      menu.addEventListener("click", async (event) => {
        const action = event.target && event.target.dataset ? event.target.dataset.action : "";
        const file = menu._file;
        hideFileContextMenu();
        if (!file || !action) {
          return;
        }

        try {
          if (action === "download") {
            triggerBrowserDownload(file);
            return;
          }
          if (action === "saveAs") {
            await saveFileAs(file);
            return;
          }
          if (action === "copyLink") {
            await navigator.clipboard.writeText(getAbsoluteFileUrl(file));
          }
        } catch (error) {
          const messageKey = action === "copyLink" ? "copyLinkFailed" : "saveAsFailed";
          logError(messageKey, error);
          window.alert(t(messageKey));
        }
      });

      document.body.appendChild(menu);
      fileContextMenu = menu;
      return menu;
    }

    function showFileContextMenu(event, file) {
      const menu = ensureFileContextMenu();
      menu._file = file;
      const labels = {
        download: t("download"),
        saveAs: t("saveAs"),
        copyLink: t("copyLink"),
      };

      menu.querySelectorAll(".file-context-action").forEach((button) => {
        const action = button.dataset.action;
        button.textContent = labels[action] || action;
      });

      menu.classList.remove("hidden");
      menu.style.left = "0px";
      menu.style.top = "0px";

      const menuWidth = menu.offsetWidth;
      const menuHeight = menu.offsetHeight;
      const left = Math.min(event.clientX, window.innerWidth - menuWidth - 8);
      const top = Math.min(event.clientY, window.innerHeight - menuHeight - 8);
      menu.style.left = `${Math.max(8, left)}px`;
      menu.style.top = `${Math.max(8, top)}px`;
    }

    function isImageFile(file) {
      return getFileMime(file).startsWith("image/");
    }

    function isAudioFile(file) {
      return getFileMime(file).startsWith("audio/");
    }

    function isVideoFile(file) {
      return getFileMime(file).startsWith("video/");
    }

    function isPdfFile(file) {
      return getFileMime(file) === "application/pdf" || getFileExt(file) === "pdf";
    }

    function isOfficeFile(file) {
      const mime = getFileMime(file);
      const ext = getFileExt(file);
      return (
        OFFICE_EXTENSIONS.has(ext) ||
        mime === "application/msword" ||
        mime === "application/vnd.ms-excel" ||
        mime === "application/vnd.ms-powerpoint" ||
        mime === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
        mime === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
        mime === "application/vnd.openxmlformats-officedocument.presentationml.presentation"
      );
    }

    function isPreviewInNewTabFile(file) {
      return isPdfFile(file) || isOfficeFile(file);
    }

    function buildFilePreview(file) {
      const wrapper = document.createElement("div");
      wrapper.className = "message-file";

      const preview = document.createElement("div");
      preview.className = "file-preview";
      const inlineUrl = getInlineFileUrl(file);
      const fileName = getFileName(file);
      const clickablePreview = isPreviewInNewTabFile(file) && Boolean(inlineUrl);

      if (isImageFile(file) && inlineUrl) {
        const img = document.createElement("img");
        img.src = inlineUrl;
        img.alt = fileName;
        preview.appendChild(img);
      } else if (isAudioFile(file) && inlineUrl) {
        const audio = document.createElement("audio");
        audio.controls = true;
        audio.src = inlineUrl;
        preview.appendChild(audio);
      } else if (isVideoFile(file) && inlineUrl) {
        const video = document.createElement("video");
        video.controls = true;
        video.preload = "metadata";
        video.src = inlineUrl;
        preview.appendChild(video);
      } else if (clickablePreview) {
        preview.textContent = t("clickToPreview");
      } else {
        preview.textContent = t("unsupportedPreview");
      }

      const name = document.createElement(clickablePreview ? "a" : "div");
      name.className = "file-name";
      name.textContent = fileName;
      name.title = t("saveAs");
      name.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        showFileContextMenu(event, file);
      });
      if (clickablePreview) {
        name.classList.add("preview-link");
        name.href = inlineUrl;
        name.target = "_blank";
        name.rel = "noopener noreferrer";

        wrapper.classList.add("preview-clickable");
        wrapper.addEventListener("click", (event) => {
          if (event.target && event.target.closest && event.target.closest(".download-link")) {
            return;
          }
          if (event.target && event.target.closest && event.target.closest(".preview-link")) {
            return;
          }
          window.open(inlineUrl, "_blank", "noopener,noreferrer");
        });
      }

      const actions = document.createElement("div");
      actions.className = "file-actions";
      const sizeText = document.createElement("span");
      sizeText.textContent = formatBytes(file.size);
      const link = document.createElement("a");
      link.className = "download-link";
      link.textContent = t("download");
      link.href = getDownloadFileUrl(file);
      link.rel = "noopener noreferrer";
      actions.appendChild(sizeText);
      actions.appendChild(link);

      wrapper.appendChild(preview);
      wrapper.appendChild(name);
      wrapper.appendChild(actions);
      return wrapper;
    }

    return {
      buildFilePreview,
      hideFileContextMenu,
    };
  }

  window.MyFileHelperFilePreview = {
    createFilePreviewHelpers,
  };
})();


