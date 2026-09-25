// ==========================================================================
// Gap2Hire Client-Side Router
// ==========================================================================

const router = {
  routes: {
    auth: () => {
      const v = window.authView || window.AuthView || (typeof authView !== "undefined" ? authView : null);
      if (v && v.render) v.render();
    },
    dashboard: () => {
      const v = window.dashboardView || window.DashboardView || (typeof dashboardView !== "undefined" ? dashboardView : null);
      if (v && v.render) v.render();
    },
    jobs: () => {
      const v = window.jobsView || window.JobsView || (typeof jobsView !== "undefined" ? jobsView : null);
      if (v && v.renderList) v.renderList();
    },
    "job-detail": (params) => {
      const v = window.jobsView || window.JobsView || (typeof jobsView !== "undefined" ? jobsView : null);
      if (v && v.renderDetail) v.renderDetail(params.id || (window.appState && window.appState.activeJobId));
    },
    candidates: (params) => {
      const v = window.candidatesView || window.CandidatesView || (typeof candidatesView !== "undefined" ? candidatesView : null);
      if (v && v.render) v.render(params);
    },
    "candidate-detail": (params) => {
      const v = window.candidateDetailView || window.CandidateDetailView || (typeof candidateDetailView !== "undefined" ? candidateDetailView : null);
      if (v && v.render) v.render(params.id || (window.appState && window.appState.activeApplicationId));
    },
    "interview-setup": (params) => {
      const v = window.interviewSetupView || window.InterviewSetupView || (typeof interviewSetupView !== "undefined" ? interviewSetupView : null);
      if (v && v.render) v.render(document.getElementById("main-view"), params);
    },
    "interview-live": (params) => {
      const v = window.interviewLiveView || window.InterviewLiveView || (typeof interviewLiveView !== "undefined" ? interviewLiveView : null);
      if (v && v.render) v.render(document.getElementById("main-view"), params);
    },
    "interview-report": (params) => {
      const v = window.interviewReportView || window.InterviewReportView || (typeof interviewReportView !== "undefined" ? interviewReportView : null);
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
