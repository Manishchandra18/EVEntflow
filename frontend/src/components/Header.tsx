"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession, getStoredUser } from "@/lib/api";

export function Header() {
  const router = useRouter();
  const user = getStoredUser();

  function signOut() {
    clearSession();
    router.replace("/login");
  }

  return (
    <header className="topbar">
      <Link href="/" className="brand">EventFlow</Link>
      <div className="topbarRight">
        {user ? <span>{user.name} · {user.role}</span> : null}
        {user ? <button className="ghost" onClick={signOut}>Sign out</button> : null}
      </div>
    </header>
  );
}
