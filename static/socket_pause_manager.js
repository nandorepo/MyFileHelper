// Socket pause and picker management for Android uploads
function createSocketPauseManager(socket) {
  const isAndroid = /Android/i.test(navigator.userAgent || "");
  const pauseSocketOnAndroidUpload = true;

  let pauseRefCount = 0;
  let pickerPauseActive = false;
  let suppressDisconnectNotice = false;
  let pausedSocket = false;
  let pausedWasConnected = false;
  let pickerRequestedAt = 0;
  let pickerSafetyTimer = null;

  function requestSocketPause(reason) {
    if (!socket || !pauseSocketOnAndroidUpload || !isAndroid) {
      return;
    }
    pauseRefCount += 1;
    if (pauseRefCount !== 1) {
      return;
    }
    if (!socket.connected) {
      return;
    }
    pausedSocket = true;
    pausedWasConnected = true;
    suppressDisconnectNotice = true;
    log("pause socket", reason || "unknown");
    socket.disconnect();
  }

  function releaseSocketPause(reason) {
    if (!socket || !pauseSocketOnAndroidUpload || !isAndroid) {
      return;
    }
    pauseRefCount = Math.max(0, pauseRefCount - 1);
    if (pauseRefCount !== 0 || !pausedSocket) {
      return;
    }
    pausedSocket = false;
    if (pausedWasConnected) {
      pausedWasConnected = false;
      log("resume socket", reason || "unknown");
      socket.connect();
    }
  }

  function beginPickerPause() {
    if (pickerPauseActive) {
      return;
    }
    pickerPauseActive = true;
    if (pickerSafetyTimer) {
      clearTimeout(pickerSafetyTimer);
      pickerSafetyTimer = null;
    }
    requestSocketPause("picker");
    pickerSafetyTimer = setTimeout(() => {
      pickerSafetyTimer = null;
      endPickerPause();
    }, 30000);
  }

  function endPickerPause() {
    if (!pickerPauseActive) {
      return;
    }
    pickerPauseActive = false;
    if (pickerSafetyTimer) {
      clearTimeout(pickerSafetyTimer);
      pickerSafetyTimer = null;
    }
    releaseSocketPause("picker");
  }

  function markPickerRequest() {
    pickerRequestedAt = Date.now();
    beginPickerPause();
  }

  return {
    isAndroid,
    pauseSocketOnAndroidUpload,
    requestSocketPause,
    releaseSocketPause,
    beginPickerPause,
    endPickerPause,
    markPickerRequest,
    getPickerRequestedAt: () => pickerRequestedAt,
    getPickerPauseActive: () => pickerPauseActive,
    getPauseRefCount: () => pauseRefCount,
    getSuppressDisconnectNotice: () => suppressDisconnectNotice,
    setSuppressDisconnectNotice: (value) => {
      suppressDisconnectNotice = value;
    },
  };
}

