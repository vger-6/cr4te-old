(function () {
  const CONTROL_HIDE_DELAY = 2000;
  let isVideoSeeking = false;

  function toggleVideoPlay(btn) {
    const wrapper = btn.closest(".video-wrapper");
    const video = wrapper.querySelector("video");
    const svg = btn.querySelector("svg");
    const playIcon = svg.querySelector("[data-play]");
    const pauseIcon = svg.querySelector("[data-pause]");

    if (video.paused) {
      video.play();
      playIcon.style.display = "none";
      pauseIcon.style.display = "inline";
    } else {
      video.pause();
      playIcon.style.display = "inline";
      pauseIcon.style.display = "none";
    }
  }

  function seekVideo(input) {
    const video = input.closest(".video-wrapper").querySelector("video");
    video.currentTime = (input.value / 100) * video.duration;

    isVideoSeeking = false;
  }

  function setVideoVolume(input) {
    const volume = window.utils.saveMediaVolume(input.value);
    window.utils.applyMediaVolume(volume);
  }

  function toggleFullscreen(btn) {
    const wrapper = btn.closest(".video-wrapper");

    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      wrapper.requestFullscreen().catch(err => console.error("Fullscreen failed", err));
    }
  }

  function updateVideoProgress(video) {
    if (!video || isVideoSeeking) return;

    const wrapper = video.closest(".video-wrapper");
    const bar = wrapper.querySelector(".progress-bar");
    const display = wrapper.querySelector(".time-display");

    const percent = (video.currentTime / video.duration) * 100;
    if (bar) {
      bar.value = percent || 0;
      window.utils.setRangeFill(bar);
    }

    const format = sec => window.utils.formatTime(sec);
    if (display) {
      display.textContent = `${format(video.currentTime)} / ${format(video.duration || 0)}`;
    }
  }

  // Init
  document.querySelectorAll(".video-wrapper video").forEach(video => {
    const wrapper = video.closest(".video-wrapper");

    video.addEventListener("timeupdate", () => updateVideoProgress(video));
    video.addEventListener("loadedmetadata", () => {
      const wrapper = video.closest(".video-wrapper");
      const bar = wrapper.querySelector(".progress-bar");

      if (bar) {
        bar.disabled = false;
        const percent = (video.currentTime / video.duration) * 100;
        bar.value = percent || 0;
        window.utils.setRangeFill(bar);
      }

      const display = wrapper.querySelector(".time-display");
      if (display) {
        const format = sec => window.utils.formatTime(sec);
        display.textContent = `${format(video.currentTime)} / ${format(video.duration || 0)}`;
      }
    });
    video.addEventListener("pause", () => {
      const svg = wrapper.querySelector(".play-toggle-icon");
      if (svg) {
        svg.querySelector("[data-play]").style.display = "inline";
        svg.querySelector("[data-pause]").style.display = "none";
      }
    });
    video.addEventListener("play", () => {
      const svg = wrapper.querySelector(".play-toggle-icon");
      if (svg) {
        svg.querySelector("[data-play]").style.display = "none";
        svg.querySelector("[data-pause]").style.display = "inline";
      }
    });
    video.addEventListener("click", () => {
      const wrapper = video.closest(".video-wrapper");
      const svg = wrapper.querySelector(".play-toggle-icon");

      if (video.paused) {
        video.play();
        svg?.querySelector("[data-play]")?.style?.setProperty("display", "none");
        svg?.querySelector("[data-pause]")?.style?.setProperty("display", "inline");
      } else {
        video.pause();
        svg?.querySelector("[data-play]")?.style?.setProperty("display", "inline");
        svg?.querySelector("[data-pause]")?.style?.setProperty("display", "none");
      }
    });
  });

  window.utils.applyMediaVolume();

  document.querySelectorAll(".video-wrapper").forEach(wrapper => {
    let hideTimeout;

    const video = wrapper.querySelector("video");

    const showControls = () => {
      wrapper.classList.remove("hide-controls");
      wrapper.classList.remove("hide-cursor");

      clearTimeout(hideTimeout);

      if (!video.paused) {
        hideTimeout = setTimeout(() => {
          wrapper.classList.add("hide-controls");

          // Only hide cursor if in fullscreen
          if (document.fullscreenElement === wrapper) {
            wrapper.classList.add("hide-cursor");
          }
        }, CONTROL_HIDE_DELAY);
      }
    };

    wrapper.addEventListener("mousemove", showControls);
    wrapper.addEventListener("click", showControls);

    wrapper.addEventListener("mouseleave", () => {
      if (!video.paused) {
        wrapper.classList.add("hide-controls");
      }
    });

    video.addEventListener("play", showControls);
    video.addEventListener("pause", () => {
      clearTimeout(hideTimeout);
      wrapper.classList.remove("hide-controls");
      wrapper.classList.remove("hide-cursor");
    });

    // Reset cursor visibility when exiting fullscreen
    document.addEventListener("fullscreenchange", () => {
      if (document.fullscreenElement !== wrapper) {
        wrapper.classList.remove("hide-cursor");
      }
    });
  });

  document.addEventListener("DOMContentLoaded", () => {
      document.querySelectorAll(".video-wrapper .progress-bar").forEach(bar => {
      bar.addEventListener("mousedown", () => { isVideoSeeking = true; });
      bar.addEventListener("mouseup", () => { isVideoSeeking = false; });
      bar.addEventListener("touchstart", () => { isVideoSeeking = true; });
      bar.addEventListener("touchend", () => { isVideoSeeking = false; });
      bar.addEventListener("input", () => { window.utils.setRangeFill(bar); });
      bar.addEventListener("mouseleave", () => { isVideoSeeking = false; });
      bar.addEventListener("blur", () => { isVideoSeeking = false; });
      window.utils.setRangeFill(bar);
    });
  });

  window.toggleVideoPlay = toggleVideoPlay;
  window.seekVideo = seekVideo;
  window.setVideoVolume = setVideoVolume;
  window.toggleFullscreen = toggleFullscreen;
})();
