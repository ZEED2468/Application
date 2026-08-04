"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Briefcase,
  ClipboardList,
  MessageSquareText,
  ScanSearch,
  Inbox,
  Globe,
  UploadCloud,
  Users,
  ShieldCheck,
  Settings,
  LifeBuoy,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import type { MeResponse } from "@jd/shared-types";
import { authService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { OnboardingLauncher } from "@/components/onboarding-launcher";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}
interface NavGroup {
  label?: string;
  items: NavItem[];
}

/** Nav is principal-aware AND grouped by intent, so each persona sees only what it
 *  needs: a solo hunter never sees the VA worklist, a VA never sees hunter setup,
 *  and only admins see the platform panels. Help stays pinned to the footer. */
function navFor(me?: MeResponse): NavGroup[] {
  const isVa = me?.type === "va";
  const isAdmin = me?.role === "admin";

  const groups: NavGroup[] = [
    {
      label: "Workspace",
      items: [
        { href: "/jobs", label: "Jobs", icon: Briefcase },
        { href: "/applications", label: "Tracker", icon: ClipboardList },
        { href: "/ats-checker", label: "ATS Checker", icon: ScanSearch },
        { href: "/manual", label: "Manual Apply", icon: MessageSquareText },
      ],
    },
  ];

  // The VA queue is a VA's worklist — hunters monitor progress on the Tracker instead.
  if (isVa) {
    groups.push({
      label: "Assist",
      items: [{ href: "/va", label: "VA Queue", icon: Inbox }],
    });
  }

  if (!isVa) {
    groups.push({
      label: "Setup",
      items: [
        { href: "/profile", label: "Profile", icon: UploadCloud },
        { href: "/settings", label: "Settings", icon: Settings },
        { href: "/team", label: "Team", icon: Users },
      ],
    });
  }

  if (isAdmin) {
    groups.push({
      label: "Admin",
      items: [
        { href: "/admin", label: "Admin", icon: ShieldCheck },
        { href: "/domains", label: "Domains", icon: Globe },
      ],
    });
  }

  groups.push({ items: [{ href: "/help", label: "Help", icon: LifeBuoy }] });
  return groups;
}

function BrandLink() {
  return (
    <Link href="/jobs" className="block px-2">
      <p className="text-xl font-semibold tracking-tight text-coffee-900">
        The Outreach Desk
      </p>
      <p className="text-xs uppercase tracking-[0.18em] text-coffee-300">
        Application engine
      </p>
    </Link>
  );
}

/** Grouped nav list, shared by the desktop sidebar and the mobile drawer. */
function SidebarNav({
  groups,
  pathname,
  onNavigate,
}: {
  groups: NavGroup[];
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <nav className="flex flex-1 flex-col gap-4">
      {groups.map((group, gi) => (
        <div
          key={group.label ?? `group-${gi}`}
          className={cn("flex flex-col gap-1", !group.label && "mt-auto")}
        >
          {group.label && (
            <p className="px-3 pb-1 text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-coffee-300">
              {group.label}
            </p>
          )}
          {group.items.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                data-tour={item.href}
                onClick={onNavigate}
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
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const { data: me, isLoading } = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const groups = React.useMemo(() => navFor(me), [me]);
  const isJobsTracker = pathname === "/jobs";

  // Close the mobile drawer whenever the route changes.
  React.useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const logout = useMutation({
    mutationFn: () => authService.logout(),
    onSettled: () => {
      queryClient.clear();
      router.push("/login");
    },
  });

  return (
    <div className="flex min-h-screen bg-white">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-coffee-300 bg-white px-4 py-6 md:flex">
        <BrandLink />
        <div className="mt-8 flex min-h-0 flex-1 flex-col overflow-y-auto">
          <SidebarNav groups={groups} pathname={pathname} />
        </div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-coffee-900/40"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r border-coffee-300 bg-white px-4 py-6 shadow-xl">
            <div className="flex items-start justify-between">
              <BrandLink />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="rounded-md p-1 text-coffee-500 hover:bg-coffee-100"
              >
                <X className="size-5" />
              </button>
            </div>
            <div className="mt-8 flex min-h-0 flex-1 flex-col overflow-y-auto">
              <SidebarNav
                groups={groups}
                pathname={pathname}
                onNavigate={() => setMobileOpen(false)}
              />
            </div>
          </aside>
        </div>
      )}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center justify-between border-b border-coffee-300 bg-white px-6">
          <div className="flex items-center gap-2 md:hidden">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              className="-ml-2 rounded-md p-2 text-coffee-700 hover:bg-coffee-100"
            >
              <Menu className="size-5" />
            </button>
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

        <main
          className={cn(
            "mx-auto flex min-h-0 w-full flex-1 flex-col overflow-hidden",
            isJobsTracker ? "max-w-none px-4 py-4" : "max-w-6xl overflow-auto px-6 py-8",
          )}
        >
          {children}
        </main>
      </div>
      <OnboardingLauncher />
    </div>
  );
}

function initials(value: string): string {
  const parts = value.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
