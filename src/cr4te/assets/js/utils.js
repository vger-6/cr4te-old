window.utils = window.utils || {};

window.utils.parseCssLength = function (value, contextElement = document.documentElement) {
  if (typeof value !== 'string') return NaN;

  const trimmed = value.trim().toLowerCase();

  if (trimmed.endsWith('px')) {
    return parseFloat(trimmed);
  }

  if (trimmed.endsWith('rem')) {
    const rem = parseFloat(trimmed);
    const rootFontSize = parseFloat(getComputedStyle(document.documentElement).fontSize);
    return rem * rootFontSize;
  }

  if (trimmed.endsWith('em')) {
    const em = parseFloat(trimmed);
    const fontSize = parseFloat(getComputedStyle(contextElement).fontSize);
    return em * fontSize;
  }

  if (trimmed.endsWith('vw')) {
    const vw = parseFloat(trimmed);
    return (vw / 100) * window.innerWidth;
  }

  if (trimmed.endsWith('vh')) {
    const vh = parseFloat(trimmed);
    return (vh / 100) * window.innerHeight;
  }

  // Add more units here if needed: e.g., vmin, vmax, etc.

  // Attempt to parse as a raw number
  const numeric = parseFloat(trimmed);
  return isNaN(numeric) ? NaN : numeric;
};

window.utils.getBreakpointPx = function (varName = '--mobile-breakpoint') {
  const rootStyles = getComputedStyle(document.documentElement);
  const value = rootStyles.getPropertyValue(varName).trim();
  return window.utils.parseCssLength(value);
};

window.utils.getExplicitScrollableAncestor = function (el) {
  let parent = el.parentElement;
  while (parent) {
    const style = window.getComputedStyle(parent);
    const overflowY = style.getPropertyValue('overflow-y');
    const isScrollable = (overflowY === 'auto' || overflowY === 'scroll');
    const canScroll = parent.scrollHeight > parent.clientHeight;

    if (isScrollable && canScroll) {
      return parent;
    }

    parent = parent.parentElement;
  }
  return null;
}

window.utils.formatTime = function (sec) {
  return new Date(sec * 1000).toISOString().substr(11, 8);
}

window.utils.rangeFillFrameIds = window.utils.rangeFillFrameIds || new WeakMap();

window.utils.setRangeFillNow = function (input) {
  const min = Number(input.min || 0);
  const max = Number(input.max || 100);
  const value = Number(input.value || 0);
  const percent = max === min ? 0 : ((value - min) / (max - min)) * 100;

  // Keep this in sync with the `.media-slider` background gradient in base.css.
  input.style.backgroundSize = `${Math.max(0, Math.min(100, percent))}% 100%`;
};

window.utils.setRangeFill = function (input) {
  if (window.utils.rangeFillFrameIds.has(input)) {
    return;
  }

  const frameId = requestAnimationFrame(() => {
    window.utils.rangeFillFrameIds.delete(input);
    window.utils.setRangeFillNow(input);
  });

  window.utils.rangeFillFrameIds.set(input, frameId);
};

window.utils.MEDIA_VOLUME_KEY = 'cr4te_media_volume';

window.utils.normalizeVolume = function (value, fallback = 1) {
  const volume = Number(value);

  if (!Number.isFinite(volume)) {
    return fallback;
  }

  return Math.max(0, Math.min(1, volume));
};

window.utils.getMediaVolume = function () {
  try {
    const storedVolume = localStorage.getItem(window.utils.MEDIA_VOLUME_KEY);

    if (storedVolume !== null) {
      return window.utils.normalizeVolume(storedVolume);
    }
  } catch (err) {
    console.warn('Unable to read saved media volume:', err);
  }

  return 1;
};

window.utils.saveMediaVolume = function (value) {
  const volume = window.utils.normalizeVolume(value);

  try {
    localStorage.setItem(window.utils.MEDIA_VOLUME_KEY, String(volume));
  } catch (err) {
    console.warn('Unable to save media volume:', err);
  }

  return volume;
};

window.utils.applyMediaVolume = function (value = window.utils.getMediaVolume()) {
  const volume = window.utils.normalizeVolume(value);

  document.querySelectorAll('audio, video').forEach(media => {
    media.volume = volume;
  });

  document.querySelectorAll('.volume-slider').forEach(slider => {
    slider.value = volume;
    window.utils.setRangeFill(slider);
  });

  return volume;
};

if (!window.utils.mediaVolumeSyncInitialized) {
  window.addEventListener('pageshow', () => {
    window.utils.applyMediaVolume();
  });

  window.utils.mediaVolumeSyncInitialized = true;
}

window.utils.clearUrlParam = function (paramName) {
  const params = new URLSearchParams(window.location.search);
  params.delete(paramName);
  const newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
  window.history.replaceState({}, '', newUrl);
};

