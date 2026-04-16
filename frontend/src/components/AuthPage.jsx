import { useEffect, useRef, useState } from "react";

export default function AuthPage({ onAuth }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
  const googleBtnRef = useRef(null);

  const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const endpoint =
      mode === "login" ? "/api/auth/login" : "/api/auth/register";

    const body =
      mode === "login"
        ? { username, password }
        : { username, email, password };

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Authentication failed");
        return;
      }

      // Persist tokens
      localStorage.setItem("kinetix_access_token", data.access_token);
      localStorage.setItem("kinetix_refresh_token", data.refresh_token);
      localStorage.setItem("kinetix_user", JSON.stringify(data.user));

      onAuth(data);
    } catch (err) {
      setError(err.message || "Network error");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async (credential) => {
    if (!credential) {
      setError("Google sign-in failed. Please try again.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Google authentication failed");
        return;
      }

      localStorage.setItem("kinetix_access_token", data.access_token);
      localStorage.setItem("kinetix_refresh_token", data.refresh_token);
      localStorage.setItem("kinetix_user", JSON.stringify(data.user));

      onAuth(data);
    } catch (err) {
      setError(err.message || "Network error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!googleClientId) return;

    const initGoogle = () => {
      if (!googleBtnRef.current) return;
      const googleApi = window.google?.accounts?.id;
      if (!googleApi) return;
      if (googleBtnRef.current.childNodes.length > 0) return;

      googleApi.initialize({
        client_id: googleClientId,
        callback: (response) => handleGoogleLogin(response?.credential),
      });

      googleApi.renderButton(googleBtnRef.current, {
        theme: "outline",
        size: "large",
        text: "signin_with",
        shape: "pill",
        width: 320,
      });
    };

    initGoogle();
    const handler = () => initGoogle();
    window.addEventListener("google-auth-loaded", handler);
    return () => window.removeEventListener("google-auth-loaded", handler);
  }, [googleClientId]);

  return (
    <div className="auth-page">
      <div className="auth-ambient" />
      <div className="auth-card">
        <div className="auth-logo">
          <div className="logo-mark">K</div>
          <span className="logo-text">Kinetix</span>
        </div>

        <h2 className="auth-title">
          {mode === "login" ? "Welcome back" : "Create account"}
        </h2>
        <p className="auth-subtitle">
          {mode === "login"
            ? "Sign in to your workflow agent"
            : "Start automating with AI"}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="auth-username">Username</label>
            <input
              id="auth-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              autoComplete="username"
              required
            />
          </div>

          {mode === "register" && (
            <div className="auth-field">
              <label htmlFor="auth-email">Email</label>
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter email"
                autoComplete="email"
                required
              />
            </div>
          )}

          <div className="auth-field">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={6}
            />
          </div>

          {error && <p className="auth-error">{error}</p>}

          <button
            type="submit"
            className="auth-submit"
            disabled={loading}
          >
            {loading
              ? "Please wait…"
              : mode === "login"
              ? "Sign In"
              : "Create Account"}
          </button>
        </form>

        <div className="auth-divider">
          <span>or continue with</span>
        </div>

        <div className="auth-google">
          <div className="google-btn" ref={googleBtnRef} />
          {!googleClientId && (
            <p className="auth-hint">
              Set VITE_GOOGLE_CLIENT_ID to enable Google sign-in.
            </p>
          )}
        </div>

        <div className="auth-switch">
          {mode === "login" ? (
            <p>
              Don't have an account?{" "}
              <button type="button" onClick={() => { setMode("register"); setError(""); }}>
                Sign up
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{" "}
              <button type="button" onClick={() => { setMode("login"); setError(""); }}>
                Sign in
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
