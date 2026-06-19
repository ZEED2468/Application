"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase,
  MessageSquareText,
  Inbox,
  Globe,
  UploadCloud,
  Users,
  ShieldCheck,
  LogOut,
} from "lucide-react";
import type { MeResponse } from "@jd/shared-types";
import { authService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

/** Nav is principal-aware: VAs assist but can't edit source content or manage a
 *  team; only admins see the (admin-only) Domains panel. */
function navFor(me?: MeResponse): NavItem[] {
  const items: NavItem[] = [
    { href: "/jobs", label: "Jobs / Tracker", icon: Briefcase },
    { href: "/manual", label: "Manual Apply", icon: MessageSquareText },
    { href: "/va", label: "VA Queue", icon: Inbox },
  ];
  if (me?.type !== "va") {
    items.push({ href: "/onboarding", label: "Onboarding", icon: UploadCloud });
    items.push({ href: "/team", label: "Team", icon: Users });
  }
  if (me?.role === "admin") {
    items.push({ href: "/admin", label: "Admin", icon: ShieldCheck });
    items.push({ href: "/domains", label: "Domains", icon: Globe });
  }
  return items;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: me, isLoading } = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const navItems = React.useMemo(() => navFor(me), [me]);

  const logout = useMutation({
    mutationFn: () => authService.logout(),
    onSettled: () => {
      queryClient.clear();
      router.push("/login");
    },
  });

  return (
    <div className="flex min-h-screen bg-cream">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-coffee-300 bg-white/70 px-4 py-6 md:flex">
        <div className="px-2">
          <Link href="/jobs" className="block">
            <p className="text-xl font-semibold tracking-tight text-coffee-900">
              The Outreach Desk
            </p>
            <p className="text-xs uppercase tracking-[0.18em] text-coffee-300">
              Application engine
            </p>
          </Link>
        </div>

        <nav className="mt-8 flex flex-1 flex-col gap-1">
          {navItems.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-[0.95rem] transition-colors",
                  active
                    ? "bg-coffee-100 font-medium text-coffee-900"
                    : "text-coffee-700 hover:bg-coffee-100/60",
                )}
              >
                <Icon className="size-4 text-coffee-500" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-coffee-300 bg-cream/90 px-6 backdrop-blur">
          <div className="flex items-center gap-2 md:hidden">
            <span className="text-lg font-semibold text-coffee-900">
              Outreach Desk
            </span>
          </div>
          <div className="ml-auto flex items-center gap-4">
            {isLoading ? (
              <Skeleton className="h-8 w-32" />
            ) : me ? (
              <div className="flex items-center gap-3">
                <div className="text-right leading-tight">
                  <p className="text-sm font-medium text-coffee-900">
                    {me.name}
                  </p>
                  <p className="text-xs capitalize text-coffee-500">
                    {me.role || me.type}
                  </p>
                </div>
                <div className="flex size-9 items-center justify-center rounded-full border border-coffee-300 bg-coffee-100 text-sm font-medium text-coffee-700">
                  {initials(me.name || me.email)}
                </div>
              </div>
            ) : (
              <span className="text-sm text-coffee-500">Signed out</span>
            )}
            <button
              type="button"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              className="inline-flex items-center gap-1.5 rounded-md border border-coffee-300 px-3 py-1.5 text-sm text-coffee-700 transition-colors hover:bg-coffee-100 disabled:opacity-60"
            >
              <LogOut className="size-4" />
              Sign out
            </button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
          {children}
        </main>
      </div>
    </div>
  );
}

function initials(value: string): string {
  const parts = value.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
