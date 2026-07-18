"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, storeSession } from "@/lib/api";
import type { User } from "@/lib/types";

type RegisterResponse = {
  access_token: string;
  user: User;
};

type Flow = "student" | "admin";

export default function RegisterPage() {
  const router = useRouter();
  const [flow, setFlow] = useState<Flow>("student");

  // Shared fields
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");

  // Admin-only field
  const [superadminEmail, setSuperadminEmail] = useState("");

  const [showPassword, setShowPassword] = useState(false);

  const [otpMessage, setOtpMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function switchFlow(next: Flow) {
    setFlow(next);
    setOtp("");
    setOtpMessage("");
    setError("");
  }

  async function requestOtp() {
    setError("");
    if (flow === "student") {
      if (!email) { setError("Enter your email first"); return; }
      try {
        const data = await api<{ message: string }>("/auth/student-otp", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
        setOtpMessage(data.message);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to send OTP");
      }
    } else {
      if (!superadminEmail) { setError("Enter the super-admin email first"); return; }
      try {
        const data = await api<{ message: string }>("/auth/admin-otp", {
          method: "POST",
          body: JSON.stringify({ superadmin_email: superadminEmail }),
        });
        setOtpMessage(data.message);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to send admin OTP");
      }
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const body =
        flow === "student"
          ? { name, email, password, student_otp: otp }
          : { name, email, password, admin_otp: otp, superadmin_email: superadminEmail };

      const data = await api<RegisterResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
      });
      storeSession(data.access_token, data.user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="authShell">
      <h1>Create account</h1>

      {/* Flow toggle */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button
          type="button"
          className={flow === "student" ? "" : "ghost"}
          onClick={() => switchFlow("student")}
        >
          Student
        </button>
        <button
          type="button"
          className={flow === "admin" ? "" : "ghost"}
          onClick={() => switchFlow("admin")}
        >
          Admin
        </button>
      </div>

      <form className="panel grid" onSubmit={submit}>
        {flow === "admin" && (
          <label>
            Super-admin email
            <input
              type="email"
              value={superadminEmail}
              onChange={(e) => setSuperadminEmail(e.target.value)}
              placeholder="The super-admin who approves you"
              required
            />
          </label>
        )}

        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>

        <label>
          {flow === "student" ? "Your email" : "Your email (will be your admin login)"}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label>
          Password
          <div style={{ position: "relative" }}>
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
              style={{ paddingRight: "42px" }}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              style={{
                position: "absolute",
                right: "8px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "none",
                border: "none",
                padding: "4px",
                color: "var(--muted)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
              }}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>
        </label>

        <button type="button" className="ghost" onClick={requestOtp}>
          {flow === "student" ? "Send OTP to my email" : "Request OTP from super-admin"}
        </button>

        {otpMessage && <p>{otpMessage}</p>}

        <label>
          {flow === "student" ? "Email OTP" : "OTP from super-admin"}
          <input
            type="text"
            inputMode="numeric"
            maxLength={6}
            value={otp}
            onChange={(e) => setOtp(e.target.value)}
            placeholder="6-digit code"
            required
          />
        </label>

        {error && <p className="danger">{error}</p>}

        <button disabled={loading}>
          {loading ? "Creating..." : "Create account"}
        </button>

        <p className="muted">
          Already registered? <Link href="/login">Sign in</Link>
        </p>
      </form>
    </main>
  );
}
