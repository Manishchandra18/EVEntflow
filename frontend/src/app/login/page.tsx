"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, storeSession } from "@/lib/api";
import type { User } from "@/lib/types";

type LoginResponse = {
  access_token: string;
  user: User;
};

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const data = await api<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      storeSession(data.access_token, data.user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="authShell">
      <h1>Sign in</h1>
      <form className="panel grid" onSubmit={submit}>
        <label>Email<input name="email" type="email" required /></label>
        <label>Password<input name="password" type="password" required /></label>
        {error ? <p className="danger">{error}</p> : null}
        <button disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
        <p className="muted">New here? <Link href="/register">Create an account</Link></p>
      </form>
    </main>
  );
}
