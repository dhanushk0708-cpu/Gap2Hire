// ==========================================================================
// Gap2Hire Global Reactive State & Notification Center
// ==========================================================================

const appState = {
  user: null,
  activeJobId: null,
  activeCandidateId: null,
  activeApplicationId: null,
  activeSessionId: null,

  async init() {
    const token = api.getToken();
    if (!token) {
      this.user = null;
      this.updateNavbar();
      return false;
    }

    try {
      this.user = await api.auth.getMe();
      this.updateNavbar();
      return true;
    } catch (err) {
      console.warn("Failed to fetch current user profile:", err);
      api.setToken("");
      this.user = null;
      this.updateNavbar();
      return false;
    }
  },

  updateNavbar() {
    const navbar = document.getElementById("navbar");
    if (!navbar) return;

    if (this.user) {
      navbar.style.display = "flex";
      const nameEl = document.getElementById("user-display-name");
      const orgEl = document.getElementById("user-display-org");
      const avatarEl = document.getElementById("user-avatar");

      if (nameEl) nameEl.textContent = this.user.full_name || "HR Admin";
      if (orgEl) orgEl.textContent = this.user.role || "Company Admin";
      if (avatarEl) {
        const initials = (this.user.full_name || "HR")
          .split(" ")
          .map((n) => n[0])
          .join("")
          .substring(0, 2)
          .toUpperCase();
        avatarEl.textContent = initials;
      }
    } else {
      navbar.style.display = "none";
    }
  },

  logout() {
    api.setToken("");
    this.user = null;
    this.updateNavbar();
    toast.info("Logged out successfully");
    router.navigate("auth");
  },
};

// Notification Toast System
const toast = {
  show(message, type = "info", duration = 4000) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toastEl = document.createElement("div");
    toastEl.className = `toast toast-${type}`;

    let icon = "ℹ️";
    if (type === "success") icon = "✅";
    if (type === "error") icon = "⚠️";

    toastEl.innerHTML = `
      <span style="font-size: 1.2rem;">${icon}</span>
      <div style="flex: 1; font-size: 0.875rem; color: var(--text-primary); font-weight: 500;">
        ${message}
      </div>
    `;

    container.appendChild(toastEl);

    setTimeout(() => {
      toastEl.style.opacity = "0";
      toastEl.style.transform = "translateX(20px)";
      toastEl.style.transition = "all 0.3s ease";
      setTimeout(() => toastEl.remove(), 300);
    }, duration);
  },

  success(msg) {
    this.show(msg, "success");
  },
  error(msg) {
    this.show(msg, "error");
  },
  info(msg) {
    this.show(msg, "info");
  },
};

// Modal System
const modal = {
  open(contentHtml) {
    const container = document.getElementById("modal-container");
    if (!container) return;

    container.innerHTML = `
      <div class="modal-backdrop" onclick="modal.handleBackdropClick(event)">
        <div class="modal" id="active-modal">
          ${contentHtml}
        </div>
      </div>
    `;
  },

  close() {
    const container = document.getElementById("modal-container");
    if (container) {
      container.innerHTML = "";
    }
  },

  handleBackdropClick(event) {
    if (event.target.classList.contains("modal-backdrop")) {
      this.close();
    }
  },
};

window.appState = appState;
window.AppState = appState;
window.toast = toast;
window.modal = modal;

