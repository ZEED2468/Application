"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, Briefcase, Search } from "lucide-react";
import type {
  JobOut,
  MeResponse,
  Origin,
  Paginated,
  TrackerStatus,
} from "@jd/shared-types";
import { TRACKER_STATUSES } from "@jd/shared-types";
import {
  jobsService,
  applicationsService,
  authService,
  onboardingService,
  type JobsFilter,
} from "@/lib/api/services";
import { toastApiError } from "@/lib/toast-error";
import { queryKeys } from "@/lib/query-keys";
import {
  ORIGIN_LABELS,
  STATUS_LABELS,
  TRACK_LABELS,
} from "@/lib/status";
import { EmptyState, ErrorState } from "@/components/states";
import { SetupProgress } from "@/components/setup-progress";
import { TrackReminder } from "@/components/track-reminder";
import { PdfPreviewModal } from "@/components/pdf-preview-modal";
import { Pagination } from "@/components/pagination";
import { DataTable, type Column } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { MultiSelect } from "@/components/ui/multi-select";
import { SubmittedApplications } from "@/components/submitted-applications";
import { StatusCell } from "./status-cell";
import { JdCell } from "./jd-cell";
import { DocLinkCell } from "./doc-link-cell";

type JobsView = "pipeline" | "submitted";

export const dynamic = "force-dynamic";

// Fetch the whole list once, cache it (react-query + localStorage), and do all
// filtering + pagination client-side — so filter/page changes never re-hit the server.
const JOBS_CACHE_KEY = "jd_jobs_cache_v2";
const PAGE_SIZE = 25;
const MAX_FETCH = 500;

interface CachedJobs {
  data: Paginated<JobOut>;
  savedAt: number;
}

function readCachedJobs(): CachedJobs | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    const c = localStorage.getItem(JOBS_CACHE_KEY);
    if (!c) return undefined;
    const parsed = JSON.parse(c) as CachedJobs;
    return parsed?.data && typeof parsed.savedAt === "number" ? parsed : undefined;
  } catch {
    return undefined;
  }
}

/** The screen's whole position — segment, filters, page — lives in the URL, so
 *  reload, Back and a pasted link all land on the same view the user was looking
 *  at. Read once on mount; written on every change. */
function readParams() {
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
}

function readList(sp: URLSearchParams, key: string): string[] {
  const raw = sp.get(key);
  return raw ? raw.split(",").filter(Boolean) : [];
}

export default function JobsPage() {
  const router = useRouter();
  const [initialParams] = React.useState(readParams);

  // Custom tracks from localStorage
  const [customTracks, setCustomTracks] = React.useState<string[]>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("jd_custom_tracks");
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch {
          // ignore
        }
      }
    }
    return [];
  });
  
  // Pipeline (discover/tailor) vs Submitted (the former Tracker) — one screen, two
  // segments. Deep links from /applications arrive as ?view=submitted.
  const [view, setView] = React.useState<JobsView>(() =>
    initialParams.get("view") === "submitted" ? "submitted" : "pipeline",
  );

  const [newTrackInput, setNewTrackInput] = React.useState("");
  const [selectedTracks, setSelectedTracks] = React.useState<string[]>(() =>
    readList(initialParams, "tracks"),
  );
  const [selectedExpLevels, setSelectedExpLevels] = React.useState<string[]>(() =>
    readList(initialParams, "levels"),
  );
  // The role(s) the user is searching for — comma-separated. Required to run a search
  // (an empty search is blocked so no provider API tokens are wasted).
  const [searchRoles, setSearchRoles] = React.useState(
    () => initialParams.get("roles") ?? "",
  );

  const addCustomTrack = () => {
    const trimmed = newTrackInput.trim();
    if (!trimmed) return;
    const defaults = ["frontend", "backend", "general"];
    if (defaults.includes(trimmed.toLowerCase()) || customTracks.includes(trimmed)) {
      setNewTrackInput("");
      return;
    }
    const updated = [...customTracks, trimmed];
    setCustomTracks(updated);
    localStorage.setItem("jd_custom_tracks", JSON.stringify(updated));
    setNewTrackInput("");
    setSelectedTracks((prev) => [...prev, trimmed]);
  };

  const [filter, setFilter] = React.useState<JobsFilter>(() => ({
    status: (initialParams.get("status") ?? "") as TrackerStatus | "",
    track: "",
    tracks: readList(initialParams, "tracks"),
    experience_levels: readList(initialParams, "levels"),
    origin: (initialParams.get("origin") ?? "") as Origin | "",
  }));
  const [preview, setPreview] = React.useState<{ url: string; title: string } | null>(
    null,
  );
  const [page, setPage] = React.useState(() =>
    Math.max(1, Number(initialParams.get("page")) || 1),
  );

  // The roles the user already told us they're targeting, during profile setup. Both
  // queries are already cached by the shell / profile page, so this costs nothing.
  const { data: me } = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
  const { data: profiles } = useQuery({
    queryKey: queryKeys.profiles,
    queryFn: () => onboardingService.profiles(),
    staleTime: 5 * 60 * 1000,
  });

  // Prefer the active track's targets; fall back to every track's, deduped.
  const profileRoles = React.useMemo(() => {
    const all = profiles ?? [];
    const active = me?.active_track
      ? all.find((p) => p.track === me.active_track)
      : undefined;
    const source = active?.target_roles?.length
      ? active.target_roles
      : all.flatMap((p) => p.target_roles ?? []);
    return Array.from(new Set(source.map((r) => r.trim()).filter(Boolean)));
  }, [profiles, me?.active_track]);

  // Seed the search box once, and only when the user hasn't already put something
  // there (typed, or restored from the URL) — never overwrite their own words.
  const seeded = React.useRef(false);
  React.useEffect(() => {
    if (seeded.current || searchRoles.trim() || profileRoles.length === 0) return;
    seeded.current = true;
    setSearchRoles(profileRoles.join(", "));
  }, [profileRoles, searchRoles]);

  // Mirror the view state into the URL. `replace` (not `push`) keeps a filter tweak
  // out of the history stack — Back should leave the screen, not undo a checkbox —
  // while still making reload and link-sharing restore the exact view.
  React.useEffect(() => {
    const sp = new URLSearchParams();
    if (view !== "pipeline") sp.set("view", view);
    if (filter.status) sp.set("status", filter.status);
    if (filter.origin) sp.set("origin", filter.origin);
    if (selectedTracks.length) sp.set("tracks", selectedTracks.join(","));
    if (selectedExpLevels.length) sp.set("levels", selectedExpLevels.join(","));
    // Only the user's own wording is worth a URL — the profile seed is re-derived
    // on every load, so echoing it back would just make landing on /jobs noisy.
    const roles = searchRoles.trim();
    if (roles && roles !== profileRoles.join(", ")) sp.set("roles", roles);
    if (page > 1) sp.set("page", String(page));
    const next = sp.toString();
    if (next === window.location.search.replace(/^\?/, "")) return;
    router.replace(next ? `/jobs?${next}` : "/jobs", { scroll: false });
  }, [
    router,
    view,
    filter.status,
    filter.origin,
    selectedTracks,
    selectedExpLevels,
    searchRoles,
    profileRoles,
    page,
  ]);

  // Changing a filter should send the user back to page 1 — but the *first* run of
  // these effects is mount, where the page number came from the URL and must survive.
  // The marker effect is declared last on purpose: effects fire in declaration order,
  // so on mount both guards below still see `false`.
  const mounted = React.useRef(false);

  React.useEffect(() => {
    setFilter((f) => ({
      ...f,
      tracks: selectedTracks,
      experience_levels: selectedExpLevels,
    }));
    if (mounted.current) setPage(1);
  }, [selectedTracks, selectedExpLevels]);

  React.useEffect(() => {
    if (mounted.current) setPage(1);
  }, [filter.status, filter.track, filter.origin]);

  React.useEffect(() => {
    mounted.current = true;
  }, []);

  // Snapshot the persisted cache once on mount so initialData and its age come from
  // the same read (and localStorage is only touched once).
  const [cachedOnMount] = React.useState(readCachedJobs);

  // One broad fetch of all jobs, cached in memory (5 min) + persisted to localStorage
  // so reloads/navigation don't refetch. Filtering + pagination happen client-side.
  // Seeding initialDataUpdatedAt with the real save time means a *stale* persisted
  // cache (older than staleTime) still triggers a background refresh on mount, while
  // a fresh one is served instantly with no refetch.
  const { data: all, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: queryKeys.jobs({}),
    queryFn: async () => {
      const res = await jobsService.list({}, 1, MAX_FETCH);
      try {
        const entry: CachedJobs = { data: res, savedAt: Date.now() };
        localStorage.setItem(JOBS_CACHE_KEY, JSON.stringify(entry));
      } catch {
        /* ignore quota */
      }
      return res;
    },
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    initialData: cachedOnMount?.data,
    initialDataUpdatedAt: cachedOnMount?.savedAt,
  });

  // Client-side filtering (no server round-trip when filters change).
  const filtered = React.useMemo(() => {
    const items = all?.items ?? [];
    return items.filter((j) => {
      if (filter.status && j.application_status !== filter.status) return false;
      if (filter.origin && j.origin !== filter.origin) return false;
      if (selectedTracks.length && !selectedTracks.includes(j.track as string)) return false;
      if (
        selectedExpLevels.length &&
        !(j.experience_level && selectedExpLevels.includes(j.experience_level))
      )
        return false;
      return true;
    });
  }, [all, filter.status, filter.origin, selectedTracks, selectedExpLevels]);

  const total = filtered.length;
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const hasActiveFilter = Boolean(
    filter.status || filter.origin || selectedTracks.length || selectedExpLevels.length,
  );
  const clearFilters = () => {
    setFilter({ status: "", track: "", origin: "", tracks: [], experience_levels: [] });
    setSelectedTracks([]);
    setSelectedExpLevels([]);
  };

  // The broad fetch is capped at MAX_FETCH newest rows; if the server holds more,
  // tell the user so an "older job I can't see" reads as a cap, not a missing record.
  const capped = Boolean(all && all.total > all.items.length);

  const roleList = searchRoles.split(",").map((r) => r.trim()).filter(Boolean);

  const discover = useMutation({
    mutationFn: () => jobsService.discover({
      roles: roleList,
      tracks: selectedTracks,
      experience_levels: selectedExpLevels,
      force: true, // explicit user refresh bypasses the server cooldown
    }),
    onSuccess: (rep) => {
      const summary = rep.sources
        .map((s) => (s.error ? `${s.source}: error` : `${s.source}: ${s.inserted}`))
        .join(", ");
      toast.success(
        `${rep.discovered} new job${rep.discovered === 1 ? "" : "s"}` +
          (summary ? ` — ${summary}` : ""),
      );
      if (rep.fake_mode) {
        toast.message(
          "Running in fake mode — set USE_FAKE_INTEGRATIONS=false (+ source keys) for real jobs.",
        );
      }
      const firstErr = rep.sources.find((s) => s.error);
      if (firstErr) toast.error(`${firstErr.source}: ${firstErr.error}`);
      // surface config gaps (no key / no board tokens) for sources that found nothing
      const noteGroups: { [key: string]: string[] } = {};
      rep.sources
        .filter((s) => s.note && s.inserted === 0)
        .forEach((s) => {
          if (s.note) {
            if (!noteGroups[s.note]) {
              noteGroups[s.note] = [];
            }
            noteGroups[s.note].push(s.source);
          }
        });
      Object.entries(noteGroups).forEach(([note, sources]) => {
        toast.message(`${sources.join(", ")}: ${note}`);
      });
      if (rep.profiles === 0) {
        toast.error("No profile yet — finish Onboarding so discovery has skills to search.");
      }
      // Show the results the user just searched for: pull the fresh list, reset to the
      // newest page, and clear the client-side filters so a leftover Track/Level/Status
      // selection can't silently hide brand-new rows (the searched roles stay in the box).
      refetch();
      clearFilters();
      setPage(1);
    },
    onError: (err) => toastApiError(err, "Couldn't search for jobs"),
  });

  const columns: Column<JobOut>[] = [
    {
      key: "company",
      header: "Company",
      headClassName: "w-[14%] min-w-[9rem]",
      className: "align-top",
      cell: (job) => (
        <div className="leading-tight">
          <div className="line-clamp-2 font-medium text-coffee-900" title={job.company}>
            {job.company}
          </div>
          {job.location && (
            <div className="truncate text-xs text-coffee-400" title={job.location}>
              {job.location}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      headClassName: "w-[17%] min-w-[11rem]",
      className: "align-top",
      cell: (job) => (
        <div className="space-y-1">
          <div className="line-clamp-2 text-coffee-700 font-medium" title={job.role}>
            {job.role}
          </div>
          {job.experience_level && (
            <Badge variant="muted" className="text-[10px] py-0 px-1.5 uppercase font-semibold">
              {job.experience_level}
            </Badge>
          )}
        </div>
      ),
    },
    {
      key: "track",
      header: "Track",
      headClassName: "w-[7%] min-w-[5rem]",
      className: "align-top",
      cell: (job) => (
        <Badge variant="outline">
          {TRACK_LABELS[job.track as keyof typeof TRACK_LABELS] || job.track || "—"}
        </Badge>
      ),
    },
    {
      key: "origin",
      header: "Origin",
      headClassName: "w-[7%] min-w-[5rem]",
      className: "align-top",
      cell: (job) => (
        <Badge variant={job.origin === "manual" ? "default" : "muted"}>
          {ORIGIN_LABELS[job.origin]}
        </Badge>
      ),
    },
    {
      key: "ats",
      header: "ATS",
      headClassName: "w-[5%] min-w-[3.5rem] text-right",
      className: "align-top text-right tabular-nums",
      cell: (job) =>
        job.ats_score === null ? (
          <span className="text-coffee-400">—</span>
        ) : (
          <span className="font-medium text-coffee-900">{job.ats_score}</span>
        ),
    },
    {
      key: "jd",
      header: "JD",
      headClassName: "w-[22%] min-w-[16rem]",
      className: "min-w-[16rem] align-top",
      cell: (job) => <JdCell job={job} />,
    },
    {
      key: "resume",
      header: "Resume",
      headClassName: "w-[8%] min-w-[6rem]",
      className: "align-top",
      cell: (job) => (
        <DocLinkCell
          url={job.resume_doc_url}
          label="tailored CV"
          onPreview={(u) =>
            setPreview({ url: u, title: `Tailored CV — ${job.company}` })
          }
        />
      ),
    },
    {
      key: "cover_letter",
      header: "Cover letter",
      headClassName: "w-[9%] min-w-[6.5rem]",
      className: "align-top",
      cell: (job) => (
        <DocLinkCell
          url={job.cover_letter_doc_url}
          label="cover letter"
          onPreview={(u) =>
            setPreview({ url: u, title: `Cover letter — ${job.company}` })
          }
        />
      ),
    },
    {
      key: "status",
      header: "Status",
      headClassName: "w-[11%] min-w-[10rem]",
      className: "align-top min-w-[10rem]",
      cell: (job) => <StatusCell job={job} filter={filter} />,
    },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <SetupProgress />
      <TrackReminder />
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-4 border-b border-coffee-200 pb-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight text-coffee-900">Jobs</h1>
          <div className="inline-flex rounded-md border border-coffee-300 bg-white p-0.5 text-sm">
            {([["pipeline", "Pipeline"], ["submitted", "Submitted"]] as const).map(
              ([v, label]) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  className={`rounded px-3 py-1 transition-colors ${
                    view === v
                      ? "bg-coffee-700 font-medium text-cream"
                      : "text-coffee-600 hover:bg-coffee-100"
                  }`}
                >
                  {label}
                </button>
              ),
            )}
          </div>
        </div>
        {view === "pipeline" ? (
        <div className="flex flex-wrap items-center gap-3">
          {/* Custom Track Input */}
          <div className="flex items-center gap-1.5">
            <Input
              placeholder="New track name"
              value={newTrackInput}
              onChange={(e) => setNewTrackInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  addCustomTrack();
                }
              }}
              className="h-8 w-36 text-sm"
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={addCustomTrack}
              className="h-8 px-2"
            >
              +
            </Button>
          </div>

          {/* Track Multi-Select */}
          <MultiSelect
            placeholder="All Tracks"
            selected={selectedTracks}
            options={[
              { value: "frontend", label: "Frontend" },
              { value: "backend", label: "Backend" },
              { value: "general", label: "General" },
              ...customTracks.map((ct) => ({ value: ct, label: ct })),
            ]}
            onChange={setSelectedTracks}
          />

          {/* Level of Experience Multi-Select */}
          <MultiSelect
            placeholder="All Levels"
            selected={selectedExpLevels}
            options={[
              { value: "junior", label: "Junior" },
              { value: "mid", label: "Mid" },
              { value: "senior", label: "Senior" },
              { value: "lead", label: "Lead" },
            ]}
            onChange={setSelectedExpLevels}
          />

          {/* Search roles — prefilled from the target roles on the profile, so the
              common case is press-and-go rather than retype-what-we-already-know. */}
          <div className="flex flex-col gap-0.5">
            <Input
              aria-label="Roles to search for"
              placeholder="Search roles, e.g. Frontend Engineer, React Developer"
              value={searchRoles}
              onChange={(e) => setSearchRoles(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && roleList.length > 0 && !discover.isPending) {
                  discover.mutate();
                }
              }}
              className="h-8 w-64 text-sm"
            />
            {profileRoles.length > 0 ? (
              <span className="text-xs text-coffee-400">
                From your target roles ·{" "}
                <Link href="/profile" className="underline underline-offset-2">
                  edit
                </Link>
              </span>
            ) : (
              <span className="text-xs text-coffee-400">
                <Link href="/profile" className="underline underline-offset-2">
                  Add target roles
                </Link>{" "}
                to prefill this
              </span>
            )}
          </div>

          <Button
            variant="primary"
            size="sm"
            onClick={() => discover.mutate()}
            disabled={discover.isPending || roleList.length === 0}
            title={roleList.length === 0 ? "Enter a role to search" : undefined}
            className="h-8"
          >
            <Search className="size-4" />
            {discover.isPending ? "Finding…" : "Find jobs now"}
          </Button>
          <a
            href={applicationsService.exportUrl()}
            download
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            <Download className="size-4" />
            Export .xlsx
          </a>
        </div>
        ) : (
          <a
            href={applicationsService.exportUrl()}
            download
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            <Download className="size-4" />
            Export .xlsx
          </a>
        )}
      </div>

      {view === "submitted" ? (
        <SubmittedApplications />
      ) : (
      <>
      <div className="flex shrink-0 flex-wrap items-end gap-4 rounded-lg border border-coffee-300 bg-white px-4 py-3">
        <FilterSelect
          label="Status"
          value={filter.status ?? ""}
          onChange={(v) =>
            setFilter((f) => ({ ...f, status: v as TrackerStatus | "" }))
          }
          options={TRACKER_STATUSES.map((s) => ({
            value: s,
            label: STATUS_LABELS[s],
          }))}
        />
        <FilterSelect
          label="Origin"
          value={filter.origin ?? ""}
          onChange={(v) =>
            setFilter((f) => ({ ...f, origin: v as Origin | "" }))
          }
          options={[
            { value: "auto", label: "Auto" },
            { value: "manual", label: "Manual" },
          ]}
        />
        {hasActiveFilter && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-coffee-300 bg-white">
        {isError ? (
          <div className="flex flex-1 items-center justify-center p-8">
            <ErrorState
              description="We couldn't load your jobs. The backend may be offline."
              retry={() => refetch()}
            />
          </div>
        ) : (
          <>
            {capped && (
              <div className="shrink-0 border-b border-coffee-200 bg-coffee-50 px-4 py-2 text-xs text-coffee-500">
                Showing the {all!.items.length.toLocaleString()} most recent of{" "}
                {all!.total.toLocaleString()} jobs — narrow with filters to reach older ones.
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-auto">
              <DataTable<JobOut>
                columns={columns}
                data={pageItems}
                isLoading={isLoading}
                rowKey={(j) => j.id}
                onRowClick={(j) => router.push(`/jobs/${j.id}`)}
                rowLabel={(j) => `Open ${j.role} at ${j.company}`}
                skeletonRows={12}
                stickyHeader
                columnBorders
                tableClassName="table-fixed min-w-[70rem]"
                emptyState={
                  hasActiveFilter ? (
                    <EmptyState
                      icon={<Search className="size-8" />}
                      title="No jobs match your filters"
                      description="Nothing here matches the current filters. Try clearing or widening them."
                      className="min-h-[50vh] border-0 bg-transparent"
                      action={
                        <Button size="sm" variant="secondary" onClick={clearFilters}>
                          Clear filters
                        </Button>
                      }
                    />
                  ) : (
                    <EmptyState
                      icon={<Briefcase className="size-8" />}
                      title="No jobs yet"
                      description="As the scheduler discovers and scores jobs, they'll appear here. You can also add one manually."
                      className="min-h-[50vh] border-0 bg-transparent"
                      action={
                        <Link href="/manual">
                          <Button size="sm" variant="secondary">
                            Add a job manually
                          </Button>
                        </Link>
                      }
                    />
                  )
                }
              />
            </div>
          </>
        )}
        {!isError && (
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPage={setPage}
            isLoading={isLoading || isFetching}
          />
        )}
      </div>

      <PdfPreviewModal
        open={preview !== null}
        onClose={() => setPreview(null)}
        title={preview?.title ?? ""}
        url={preview?.url}
      />
      </>
      )}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select
        selectSize="sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-40"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </Select>
    </div>
  );
}
