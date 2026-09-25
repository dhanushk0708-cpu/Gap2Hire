// ==========================================================================
// Authentication View (Company Registration & Login)
// ==========================================================================

const authView = {
  isRegisterMode: false,

  render() {
    const container = document.getElementById("main-view");
    if (!container) return;

    container.innerHTML = `
      <div style="max-width: 460px; margin: 3rem auto; padding: 2.5rem; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-xl); box-shadow: var(--shadow-lg);">
        <div style="text-align: center; margin-bottom: 2rem;">
          <div style="width: 48px; height: 48px; margin: 0 auto 1rem; background: linear-gradient(135deg, var(--primary), var(--accent-indigo)); border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; font-family: var(--font-heading); font-weight: 800; font-size: 1.4rem; color: #fff;">
            G2H
          </div>
          <h2 style="font-size: 1.6rem; margin-bottom: 0.35rem;" id="auth-title">
            ${this.isRegisterMode ? "Create Company Account" : "Sign in to Gap2Hire"}
          </h2>
          <p style="font-size: 0.875rem; color: var(--text-secondary);" id="auth-subtitle">
            ${this.isRegisterMode ? "Start your evidence-driven hiring pipeline" : "Access your candidate screening & interview intelligence"}
          </p>
        </div>

        <form id="auth-form" onsubmit="authView.handleSubmit(event)">
          ${
            this.isRegisterMode
              ? `
              <div class="form-group">
                <label class="form-label" for="auth-org-name">Company Name</label>
                <input class="form-input" type="text" id="auth-org-name" placeholder="Acme Engineering" required />
              </div>
              <div class="form-group">
                <label class="form-label" for="auth-full-name">Your Full Name (HR / Admin)</label>
                <input class="form-input" type="text" id="auth-full-name" placeholder="Jane Doe" required />
              </div>
            `
              : ""
          }

          <div class="form-group">
            <label class="form-label" for="auth-email">Company Email</label>
            <input class="form-input" type="email" id="auth-email" placeholder="jane@acme.com" required />
          </div>

          <div class="form-group">
            <label class="form-label" for="auth-password">Password</label>
            <input class="form-input" type="password" id="auth-password" placeholder="••••••••••••" minlength="8" required />
          </div>

          <button class="btn btn-primary" type="submit" style="width: 100%; margin-top: 1rem;" id="auth-submit-btn">
            ${this.isRegisterMode ? "Register & Enter Hub" : "Sign In"}
          </button>
        </form>

        <div style="margin-top: 1.75rem; text-align: center; font-size: 0.875rem; color: var(--text-secondary); border-top: 1px solid var(--border-subtle); padding-top: 1.25rem;">
          ${
            this.isRegisterMode
              ? `Already have an account? <a href="javascript:void(0)" onclick="authView.toggleMode(false)" style="font-weight: 600; color: var(--primary-light);">Sign In</a>`
              : `Don't have a company account? <a href="javascript:void(0)" onclick="authView.toggleMode(true)" style="font-weight: 600; color: var(--primary-light);">Register Company</a>`
          }
        </div>
      </div>
    `;
  },

  toggleMode(register) {
    this.isRegisterMode = register;
    this.render();
  },

  async handleSubmit(event) {
    event.preventDefault();
    const submitBtn = document.getElementById("auth-submit-btn");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Authenticating...";
    }

    const email = document.getElementById("auth-email").value.trim();
    const password = document.getElementById("auth-password").value;

    try {
      if (this.isRegisterMode) {
        const orgName = document.getElementById("auth-org-name").value.trim();
        const fullName = document.getElementById("auth-full-name").value.trim();
        const res = await api.auth.register(fullName, orgName, email, password);
        api.setToken(res.access_token);
        toast.success("Registration successful! Welcome to Gap2Hire.");
      } else {
        const res = await api.auth.login(email, password);
        api.setToken(res.access_token);
        toast.success("Signed in successfully.");
      }

      await appState.init();
      router.navigate("dashboard");
    } catch (err) {
      toast.error(err.message || "Authentication failed.");
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = this.isRegisterMode ? "Register & Enter Hub" : "Sign In";
      }
    }
  },
};

window.authView = authView;
window.AuthView = authView;
