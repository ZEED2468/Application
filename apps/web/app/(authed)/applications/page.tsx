"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, ShieldCheck, Eye } from "lucide-react";
import type { TrackerApplication } from "@jd/shared-types";
import { applicationsService } from "@/lib/api/services";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS, STATUS_LABELS } from "@/lib/status";
import { formatDateTime } from "@/lib/utils";
import { PageHeading, ErrorState, EmptyState } from "@/components/states";
import { DataTable, type Column } from "@/components/data-table";
import { Pagination } from "@/components/pagination";
import { PdfPreviewModal } from "@/components/pdf-preview-modal";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";

export const dynamic = "force-dynamic";

export default function TrackerPage() {
  const [page, setPage] = React.useState(1);
  const [preview, setPreview] = React.useState<{ url: string; title: string } | null>(
    null,
  );
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [...queryKeys.applications, page],
    queryFn: () => applicationsService.list(page),
  });

  const columns: Column<TrackerApplication>[] = [
    {
      key: "company",
      header: "Company / Role",
      cell: (a) => (
        <div className="leading-tight">
          <div className="font-medium text-coffee-900">{a.company ?? "—"}</div>
          <div className="text-xs text-coffee-400">{a.role ?? ""}</div>
        </div>
      ),
    },
    {
      key: "track",
      header: "Track",
      cell: (a) =>
        a.track ? <Badge variant="outline">{TRACK_LABELS[a.track]}</Badge> : null,
    },
    {
      key: "ats",
      header: "ATS",
      headClassName: "text-right",
      className: "text-right tabular-nums",
      cell: (a) =>
        a.ats_score == null ? (
          <span className="text-coffee-300">—</span>
        ) : (
          <span className="font-medium text-coffee-900">
            {Math.round(a.ats_score)}
          </span>
        ),
    },
    {
      key: "relevance",
      header: "Relevance",
      headClassName: "text-right",
      className: "text-right tabular-nums",
      cell: (a) =>
        a.relevance_score == null ? (
          <span className="text-coffee-300">—</span>
        ) : (
          <span>{Math.round(a.relevance_score * 100)}%</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      cell: (a) => (
        <Badge>{STATUS_LABELS[a.tracker_status] ?? a.tracker_status}</Badge>
      ),
    },
    {
      key: "va",
      header: "Submitted by",
      cell: (a) => (
        <div className="text-sm text-coffee-700">
          {a.va_name ?? "—"}
          <div className="text-xs text-coffee-300">
            {a.submitted_at ? formatDateTime(a.submitted_at) : ""}
          </div>
        </div>
      ),
    },
    {
      key: "truthful",
      header: "Truthful",
      cell: (a) =>
        a.truthful ? (
          <span className="inline-flex items-center gap-1 text-xs text-status-offer">
            <ShieldCheck className="size-3.5" /> Verified
          </span>
        ) : (
          <span className="text-xs text-coffee-300">Unconfirmed</span>
        ),
    },
    {
      key: "docs",
      header: "Docs",
      cell: (a) => (
        <div className="flex items-center gap-3 text-xs">
          {a.cv_url && (
            <button
              type="button"
              onClick={() =>
                setPreview({ url: a.cv_url!, title: `CV — ${a.company}` })
              }
              className="inline-flex items-center gap-1 text-coffee-700 underline underline-offset-2 hover:text-coffee-900"
            >
              <Eye className="size-3.5" />
              CV
            </button>
          )}
          {a.cover_url && (
            <button
              type="button"
              onClick={() =>
                setPreview({ url: a.cover_url!, title: `Cover — ${a.company}` })
              }
              className="text-coffee-700 underline underline-offset-2 hover:text-coffee-900"
            >
              Cover
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <PageHeading
        title="Tracker"
        description="Every application, live and read-only — the in-app source of truth (the .xlsx is just an export)."
        actions={
          <a
            href={applicationsService.exportUrl()}
            download
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            <Download className="size-4" />
            Export .xlsx
          </a>
        }
      />

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-coffee-300 bg-white">
        {isError ? (
          <div className="flex flex-1 items-center justify-center p-8">
            <ErrorState
              description="Couldn't load the tracker. The backend may be offline."
              retry={() => refetch()}
            />
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-auto">
            <DataTable<TrackerApplication>
              columns={columns}
              data={data?.items}
              isLoading={isLoading}
              rowKey={(a) => a.id}
              skeletonRows={12}
              stickyHeader
              columnBorders
              tableClassName="min-w-[60rem]"
              emptyState={
                <EmptyState
                  title="No applications yet"
                  description="Applications appear here once a VA applies to a job."
                />
              }
            />
          </div>
        )}
        {!isError && (
          <Pagination
            page={data?.page ?? page}
            pageSize={data?.page_size ?? 25}
            total={data?.total ?? 0}
            onPage={setPage}
            isLoading={isLoading}
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
