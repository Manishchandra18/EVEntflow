"use client";

import { useRouter } from "next/navigation";
import { PropsWithChildren, useEffect, useState } from "react";
import { getStoredUser } from "@/lib/api";
import type { User } from "@/lib/types";

export function AuthGate({ children }: PropsWithChildren) {
  const router = useRouter();
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    const stored = getStoredUser();
    setUser(stored);
    if (!stored) router.replace("/login");
  }, [router]);

  if (user === undefined) return <main className="shell">Loading...</main>;
  if (!user) return null;
  return children;
}
