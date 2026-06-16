"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Download, Briefcase } from "lucide-react";
import type { JobOut, Origin, Track, TrackerStatus } from "@jd/shared-types";
import { TRACKER_STATUSES, TRACKS } from "@jd/shared-types";
import { jobsService, applicationsService, type JobsFilter } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import {
  ORIGIN_LABELS,
  STATUS_LABELS,
  TRACK_LABELS,
} from "@/lib/status";
import { PageHeading, EmptyState, ErrorState } from "@/components/states";
import { DataTable, type Column } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { StatusCell } from "./status-cell";

export const dynamic = "force-dynamic";

export default function JobsPage() {
  const router = useRouter();
  const [filter, setFilter] = React.useState<JobsFilter>({
    status: "",
    track: "",
    origin: "",
  });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.jobs(filter),
    queryFn: () => jobsService.list(filter),
  });

  const columns: Column<JobOut>[] = [
    {
      key: "company",
      header: "Company",
      cell: (job) => (
        <div className="leading-tight">
          <div className="font-medium text-coffee-900">{job.company}</div>
          {job.location && (
            <div className="text-xs text-coffee-300">{job.location}</div>
          )}
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      cell: (job) => <span className="text-coffee-700">{job.role}</span>,
    },
    {
      key: "track",
      header: "Track",
      cell: (job) => (
        <Badge variant="outline">{TRACK_LABELS[job.track]}</Badge>
      ),
    },
    {
      key: "origin",
      header: "Origin",
      cell: (job) => (
        <Badge variant={job.origin === "manual" ? "default" : "muted"}>
          {ORIGIN_LABELS[job.origin]}
        </Badge>
      ),
    },
    {
      key: "ats",
      header: "ATS",
      headClassName: "text-right",
      className: "text-right tabular-nums",
      cell: (job) =>
        job.ats_score === null ? (
          <span className="text-coffee-300">—</span>
        ) : (
          <span className="font-medium text-coffee-900">{job.ats_score}</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      cell: (job) => <StatusCell job={job} filter={filter} />,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeading
        title="Jobs / Tracker"
        description="Every discovered and manually-added application — tailored, scored, and tracked from first send to offer."
        actions={
          <a
            href={applicationsService.exportUrl()}
            download
            className={buttonVariants({ variant: "secondary" })}
          >
            <Download className="size-4" />
            Export .xlsx
          </a>
        }
      />

      <Card className="px-4 py-4">
        <div className="flex flex-wrap items-end gap-4">
          <FilterSelect
            label="Track"
            value={filter.track ?? ""}
            onChange={(v) =>
              setFilter((f) => ({ ...f, track: v as Track | "" }))
            }
            options={TRACKS.map((t) => ({ value: t, label: TRACK_LABELS[t] }))}
          />
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
          {(filter.track || filter.status || filter.origin) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                setFilter({ track: "", status: "", origin: "" })
              }
            >
              Clear filters
            </Button>
          )}
        </div>
      </Card>

      <Card className="overflow-hidden">
        {isError ? (
          <div className="p-6">
            <ErrorState
              description="We couldn't load your jobs. The backend may be offline."
              retry={() => refetch()}
            />
          </div>
        ) : (
          <DataTable<JobOut>
            columns={columns}
            data={data}
            isLoading={isLoading}
            rowKey={(j) => j.id}
            onRowClick={(j) => router.push(`/jobs/${j.id}`)}
            emptyState={
              <EmptyState
                icon={<Briefcase className="size-8" />}
                title="No jobs yet"
                description="As the scheduler discovers and scores jobs, they'll appear here. You can also add one manually."
                action={
                  <Link href="/manual">
                    <Button size="sm" variant="secondary">
                      Add via Manual Apply
                    </Button>
                  </Link>
                }
              />
            }
          />
        )}
      </Card>
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
