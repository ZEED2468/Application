"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { authService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";

/**
 * Client-side auth gate for the (authed) group. Confirms the session by calling
 * GET /api/auth/me — which carries the auth cookie even cross-origin (direct
 * mode), where the middleware can't see it. On failure, redirect to /login.
 * Login's onSuccess pre-seeds the `me` cache, so this is a cache hit right after
 * signing in (no extra round-trip / flash).
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 60_000,
  });

  React.useEffect(() => {
    if (isError) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [isError, router, pathname]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream text-coffee-500">
        Loading…
      </div>
    );
  }
  if (isError || !data) return null; // redirecting to /login

  return <>{children}</>;
}
