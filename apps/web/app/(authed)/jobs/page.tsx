"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download, Briefcase, Search } from "lucide-react";
import type { JobOut, Origin, Paginated, TrackerStatus } from "@jd/shared-types";
import { TRACKER_STATUSES } from "@jd/shared-types";
import { jobsService, applicationsService, type JobsFilter } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
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
import { StatusCell } from "./status-cell";
import { JdCell } from "./jd-cell";
import { DocLinkCell } from "./doc-link-cell";

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

export default function JobsPage() {
  const router = useRouter();
  
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
  
  const [newTrackInput, setNewTrackInput] = React.useState("");
  const [selectedTracks, setSelectedTracks] = React.useState<string[]>([]);
  const [selectedExpLevels, setSelectedExpLevels] = React.useState<string[]>([]);

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

  const [filter, setFilter] = React.useState<JobsFilter>({
    status: "",
    track: "",
    tracks: [],
    experience_levels: [],
    origin: "",
  });
  const [preview, setPreview] = React.useState<{ url: string; title: string } | null>(
    null,
  );
  const [page, setPage] = React.useState(1);

  React.useEffect(() => {
    setFilter((f) => ({
      ...f,
      tracks: selectedTracks,
      experience_levels: selectedExpLevels,
    }));
    setPage(1);
  }, [selectedTracks, selectedExpLevels]);

  React.useEffect(() => {
    setPage(1);
  }, [filter.status, filter.track, filter.origin]);

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

  const discover = useMutation({
    mutationFn: () => jobsService.discover({
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
      refetch();
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
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
            <div className="truncate text-xs text-coffee-300" title={job.location}>
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
          <span className="text-coffee-300">—</span>
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
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight text-coffee-900">
            Jobs / Tracker
          </h1>
          <p className="text-sm text-coffee-500">
            Every discovered and manually-added application, tailored, scored,
            and tracked from first send to offer.
          </p>
        </div>
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

          <Button
            variant="primary"
            size="sm"
            onClick={() => discover.mutate()}
            disabled={discover.isPending}
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
      </div>

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
                            Add via Manual Apply
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
