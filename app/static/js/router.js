// ==========================================================================
// Gap2Hire Client-Side Router
// ==========================================================================

const router = {
  routes: {
    auth: () => (window.authView || window.AuthView).render(),
    dashboard: () => (window.dashboardView || window.DashboardView).render(),
    jobs: () => (window.jobsView || window.JobsView).renderList(),
    "job-detail": (params) => (window.jobsView || window.JobsView).renderDetail(params.id || (window.appState && window.appState.activeJobId)),
    candidates: (params) => (window.candidatesView || window.CandidatesView).render(params),
    "candidate-detail": (params) => (window.candidateDetailView || window.CandidateDetailView).render(params.id || (window.appState && window.appState.activeApplicationId)),
    "interview-setup": (params) => {
      const v = window.interviewSetupView || window.InterviewSetupView;
      if (v && v.render) v.render(document.getElementById("main-view"), params);
    },
    "interview-live": (params) => {
      const v = window.interviewLiveView || window.InterviewLiveView;
      if (v && v.render) v.render(document.getElementById("main-view"), params);
    },
    "interview-report": (params) => {
      const v = window.interviewReportView || window.InterviewReportView;
      if (v && v.render) v.render(document.getElementById("main-view"), params);
    },
  },

  init() {
    window.addEventListener("hashchange", () => this.handleRoute());
    this.handleRoute();
  },

  navigate(routeName, params = {}) {
    const query = new URLSearchParams(params).toString();
    const hash = query ? `#${routeName}?${query}` : `#${routeName}`;
    if (window.location.hash === hash) {
      // If hash didn't change, trigger route directly
      this.handleRoute();
    } else {
      window.location.hash = hash;
    }
  },

  parseHash() {
    let rawHash = window.location.hash || "dashboard";
    if (rawHash.startsWith("#")) {
      rawHash = rawHash.slice(1);
    }
    if (!rawHash) {
      rawHash = "dashboard";
    }

    const [path, queryString] = rawHash.split("?");
    const params = {};

    if (queryString) {
      const searchParams = new URLSearchParams(queryString);
      for (const [key, value] of searchParams.entries()) {
        params[key] = value;
      }
    }

    return { path, params };
  },

  handleRoute() {
    const { path, params } = this.parseHash();

    // Enforce Authentication
    const isAuth = !!(window.api && window.api.getToken());
    if (!isAuth && path !== "auth") {
      this.navigate("auth");
      return;
    }

    if (isAuth && path === "auth") {
      this.navigate("dashboard");
      return;
    }

    this.updateActiveNav(path);

    const handler = this.routes[path];
    if (handler) {
      try {
        handler(params);
      } catch (err) {
        console.error(`Error rendering route '${path}':`, err);
      }
    } else {
      console.warn(`Route not found: '${path}'. Defaulting to dashboard.`);
      this.navigate("dashboard");
    }
  },

  updateActiveNav(path) {
    document.querySelectorAll(".nav-link").forEach((link) => link.classList.remove("active"));
    const activeLink = document.getElementById(`nav-${path}`);
    if (activeLink) activeLink.classList.add("active");
  },
};

// Global router exports
window.router = router;
window.Router = router;
