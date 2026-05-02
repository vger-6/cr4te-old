(function () {
  let isSeeking = false;

  function setGalleryState(gallery, list, index) {
    gallery._currentList = list;
    gallery.dataset.currentIndex = index;
  }

  function getGalleryState(gallery) {
    return {
      list: gallery._currentList || [],
      index: parseInt(gallery.dataset.currentIndex || "-1", 10),
    };
  }

  function playTrack(audio, liElement) {
    const gallery = audio.closest(".audio-gallery");
    const listItems = [...liElement.parentElement.querySelectorAll("li")];

    const currentIndex = listItems.indexOf(liElement);
    setGalleryState(gallery, listItems, currentIndex);

    audio.src = liElement.dataset.src;
    audio.play();

    highlightCurrent(gallery, liElement);
    updateUIOnPlay(gallery);
  }

  function playNextTrack(audio) {
    const gallery = audio.closest(".audio-gallery");
    const { list, index } = getGalleryState(gallery);

    if (!list || index + 1 >= list.length) return;

    const nextIndex = index + 1;
    const nextLi = list[nextIndex];
    setGalleryState(gallery, list, nextIndex);
    playTrack(audio, nextLi);
  }

  function prevTrack(btn) {
    const gallery = btn.closest(".audio-gallery");
    const audio = gallery.querySelector("audio");
    const { list, index } = getGalleryState(gallery);

    if (!list || index <= 0) return;

    const prevIndex = index - 1;
    const prevLi = list[prevIndex];
    setGalleryState(gallery, list, prevIndex);
    playTrack(audio, prevLi);
  }

  function nextTrack(btn) {
    const audio = btn.closest(".audio-gallery").querySelector("audio");
    playNextTrack(audio);
  }

  function playSelectedTrack(liElement) {
    const gallery = liElement.closest(".audio-gallery");
    const audio = gallery.querySelector("audio");
    playTrack(audio, liElement);
  }

  function togglePlay(btn) {
    const gallery = btn.closest(".audio-gallery");
    const audio = gallery.querySelector("audio");
    if (!audio) return;

    if (audio.paused) {
      audio.play().then(() => updateUIOnPlay(gallery))
        .catch(err => console.error("Playback error:", err));
    } else {
      audio.pause();
      updatePlayPauseIcon(gallery, false);
    }
  }
  
  function stopAudioControls(gallery, audio) {
    if (!gallery || !audio) return;

    audio.pause();
    audio.currentTime = 0;
    audio.removeAttribute("src");
    audio.load();

    setGalleryState(gallery, null, -1);

    gallery.querySelectorAll(".track-title").forEach(el => el.classList.remove("playing"));
    updatePlayPauseIcon(gallery, false);
    resetProgressUI(gallery);
    updateButtonStates(gallery, false);
  }

  function stopAudio(btn) {
    const gallery = btn.closest(".audio-gallery");
    const audio = gallery?.querySelector("audio");
    stopAudioControls(gallery, audio);
  }

  function stopAudioFromAudioElement(audio) {
    const gallery = audio.closest(".audio-gallery");
    stopAudioControls(gallery, audio);
  }

  function highlightCurrent(gallery, liElement) {
    gallery.querySelectorAll(".track-title").forEach(el => el.classList.remove("playing"));
    liElement.classList.add("playing");
  }

  function seekAudio(input) {
    if (input.disabled) return;
    const audio = input.closest(".audio-gallery").querySelector("audio");
    const percent = input.value / 100;
    audio.currentTime = percent * audio.duration;
  }

  function setVolume(input) {
    const volume = window.utils.saveMediaVolume(input.value);
    window.utils.applyMediaVolume(volume);
  }

  function updateProgress(audio) {
    if (!audio || isSeeking) return;

    const gallery = audio.closest(".audio-gallery");
    const bar = gallery.querySelector(".progress-bar");
    const timeDisplay = gallery.querySelector(".time-display");

    const percent = (audio.currentTime / audio.duration) * 100;
    if (bar) {
      bar.value = percent || 0;
      window.utils.setRangeFill(bar);
    }

    if (timeDisplay) {
      const format = sec => window.utils.formatTime(sec);
      timeDisplay.textContent = `${format(audio.currentTime)} / ${format(audio.duration || 0)}`;
    }
  }

  function updatePlayPauseIcon(gallery, isPlaying) {
    const svg = gallery.querySelector(".play-toggle-icon");
    if (!svg) return;

    const playIcon = svg.querySelector("[data-play]");
    const pauseIcon = svg.querySelector("[data-pause]");

    playIcon.style.display = isPlaying ? "none" : "inline";
    pauseIcon.style.display = isPlaying ? "inline" : "none";
  }

  function setProgressBarEnabled(gallery, isEnabled) {
    const bar = gallery.querySelector(".progress-bar");

    if (bar) {
      bar.disabled = !isEnabled;
      if (!isEnabled) {
        bar.value = 0;
        window.utils.setRangeFill(bar);
      }
    }
  }

  function updateButtonStates(gallery, isPlaying) {
    const nextBtn = gallery.querySelector(".control-btn[onclick*='nextTrack']");
    const prevBtn = gallery.querySelector(".control-btn[onclick*='prevTrack']");
    const stopBtn = gallery.querySelector(".control-btn[onclick*='stopAudio']");

    [nextBtn, prevBtn, stopBtn].forEach(btn => {
      if (btn) {
        btn.classList.toggle("disabled", !isPlaying);
      }
    });
  }

  function resetProgressUI(gallery) {
    setProgressBarEnabled(gallery, false);
    const timeDisplay = gallery.querySelector(".time-display");
    if (timeDisplay) {
      timeDisplay.textContent = "00:00:00 / 00:00:00";
    }
  }

  function updateUIOnPlay(gallery) {
    updatePlayPauseIcon(gallery, true);
    setProgressBarEnabled(gallery, true);
    updateButtonStates(gallery, true);
  }

  document.querySelectorAll(".audio-gallery audio").forEach(audio => {
    const gallery = audio.closest(".audio-gallery");

    audio.addEventListener("timeupdate", () => updateProgress(audio));

    audio.addEventListener("play", () => {
      updateUIOnPlay(gallery);
      const { index } = getGalleryState(gallery);
      if (index === -1) {
        const li = gallery.querySelector("li");
        if (li) playSelectedTrack(li);
      }
    });

    audio.addEventListener("pause", () => {
      updatePlayPauseIcon(gallery, false);
    });

    audio.addEventListener("ended", () => {
      const { list, index } = getGalleryState(gallery);
      if (!list || index + 1 >= list.length) {
        stopAudioFromAudioElement(audio);
      } else {
        playNextTrack(audio);
      }
    });
  });

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".audio-gallery").forEach(gallery => {
      updateButtonStates(gallery, false);
    });

    document.querySelectorAll(".audio-gallery .progress-bar").forEach(bar => {
      bar.disabled = true;
      bar.value = 0;

      bar.addEventListener("mousedown", () => { isSeeking = true; });
      bar.addEventListener("touchstart", () => { isSeeking = true; });
      bar.addEventListener("input", () => { window.utils.setRangeFill(bar); });
      bar.addEventListener("mouseup", () => { isSeeking = false; });
      bar.addEventListener("touchend", () => { isSeeking = false; });
      bar.addEventListener("mouseleave", () => { isSeeking = false; });
      bar.addEventListener("blur", () => { isSeeking = false; });
      window.utils.setRangeFill(bar);
    });

    window.utils.applyMediaVolume();

    const audioSections = document.querySelectorAll('.section-box.audio-gallery-section');
    const threshold = 100;
    let currentScrollContainer = null;

    audioSections.forEach(section => {
      const controls = section.querySelector('.audio-controls-wrapper');
      if (controls) {
        controls.style.opacity = '0';
        controls.style.pointerEvents = 'none';
      }
    });

    function getScrollContainer() {
      const firstGallery = document.querySelector('.audio-gallery');
      return firstGallery ? window.utils.getExplicitScrollableAncestor(firstGallery) || window : window;
    }

    function updateAudioControlsVisibility() {
      audioSections.forEach(section => {
        const controls = section.querySelector('.audio-controls-wrapper');
        if (!controls) return;

        const sectionRect = section.getBoundingClientRect();
        const controlsRect = controls.getBoundingClientRect();
        const verticalDistance = controlsRect.top - sectionRect.top;

        if (verticalDistance >= threshold) {
          controls.style.opacity = '1';
          controls.style.pointerEvents = 'auto';
        } else {
          controls.style.opacity = '0';
          controls.style.pointerEvents = 'none';
        }
      });
    }

    function setupScrollListener() {
      const newScrollContainer = getScrollContainer();

      if (newScrollContainer !== currentScrollContainer) {
        if (currentScrollContainer) {
          currentScrollContainer.removeEventListener('scroll', updateAudioControlsVisibility);
        }
        newScrollContainer.addEventListener('scroll', updateAudioControlsVisibility);
        currentScrollContainer = newScrollContainer;
      }
    }

    let resizeTimeout;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        setupScrollListener();
        updateAudioControlsVisibility();
      }, 150);
    });

    setupScrollListener();
    updateAudioControlsVisibility();
  });

  window.playSelectedTrack = playSelectedTrack;
  window.togglePlay = togglePlay;
  window.stopAudio = stopAudio;
  window.prevTrack = prevTrack;
  window.nextTrack = nextTrack;
  window.seekAudio = seekAudio;
  window.setVolume = setVolume;
  window.playNextTrack = playNextTrack;
})();

