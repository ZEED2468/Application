"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Archive, RotateCcw, AlertTriangle } from "lucide-react";
import type { CareerTrack } from "@jd/shared-types";
import { tracksService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Dialog } from "@/components/ui/dialog";

function StatusPill({ status }: { status: CareerTrack["status"] }) {
  const map = {
    ready: { dot: "bg-status-offer", label: "Ready", text: "text-status-offer" },
    setup_required: { dot: "bg-status-interviewed", label: "Resume required", text: "text-status-interviewed" },
    archived: { dot: "bg-coffee-300", label: "Archived", text: "text-coffee-400" },
  } as const;
  const s = map[status];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${s.text}`}>
      <span className={`size-2 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

export function TracksManager() {
  const qc = useQueryClient();
  const [name, setName] = React.useState("");
  const [pendingTrack, setPendingTrack] = React.useState<CareerTrack | null>(null);
  const [copyFrom, setCopyFrom] = React.useState("");

  const tracksQuery = useQuery({
    queryKey: queryKeys.tracks,
    queryFn: () => tracksService.list(),
  });
  const tracks = tracksQuery.data ?? [];
  const active = tracks.filter((t) => t.status !== "archived");
  const readyTracks = tracks.filter((t) => t.status === "ready");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: queryKeys.tracks });
    qc.invalidateQueries({ queryKey: queryKeys.onboardingStatus });
  };

  const create = useMutation({
    mutationFn: () => tracksService.create(name.trim()),
    onSuccess: (track) => {
      setName("");
      invalidate();
      if (track.status !== "ready") {
        setCopyFrom("");
        setPendingTrack(track); // trigger the Resume Required modal
      }
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const archive = useMutation({
    mutationFn: (id: string) => tracksService.archive(id),
    onSuccess: () => invalidate(),
    onError: async (err) => toast.error((await toApiError(err)).message),
  });
  const unarchive = useMutation({
    mutationFn: (id: string) => tracksService.unarchive(id),
    onSuccess: () => invalidate(),
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const duplicate = useMutation({
    mutationFn: ({ id, sourceId }: { id: string; sourceId: string }) =>
      tracksService.duplicateResume(id, sourceId),
    onSuccess: () => {
      toast.success("Resume assigned to the track.");
      setPendingTrack(null);
      invalidate();
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your tracks</CardTitle>
        <CardDescription>
          Each career track needs its own resume before it can be used for tailoring, ATS
          analysis, or applications. A track stays <strong>Resume required</strong> until you
          add one.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {tracksQuery.isLoading ? (
          <p className="text-sm text-coffee-400">Loading tracks…</p>
        ) : active.length === 0 ? (
          <p className="text-sm text-coffee-300">
            No tracks yet — create one below to get started.
          </p>
        ) : (
          <ul className="divide-y divide-coffee-100 rounded-md border border-coffee-100">
            {active.map((t) => (
              <li key={t.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-coffee-900">{t.name}</p>
                  <div className="mt-0.5 flex items-center gap-2">
                    <StatusPill status={t.status} />
                    {t.status === "setup_required" && (
                      <span className="text-xs text-coffee-400">· resume not uploaded</span>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {t.status === "setup_required" && readyTracks.length > 0 && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setCopyFrom("");
                        setPendingTrack(t);
                      }}
                    >
                      Add resume
                    </Button>
                  )}
                  <button
                    type="button"
                    onClick={() => archive.mutate(t.id)}
                    aria-label={`Archive ${t.name}`}
                    className="text-coffee-400 hover:text-coffee-700"
                  >
                    <Archive className="size-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {/* Archived */}
        {tracks.some((t) => t.status === "archived") && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wider text-coffee-400">
              Archived
            </p>
            {tracks
              .filter((t) => t.status === "archived")
              .map((t) => (
                <div key={t.id} className="flex items-center justify-between text-sm">
                  <span className="text-coffee-400">{t.name}</span>
                  <button
                    type="button"
                    onClick={() => unarchive.mutate(t.id)}
                    className="inline-flex items-center gap-1 text-xs text-coffee-500 hover:text-coffee-900"
                  >
                    <RotateCcw className="size-3.5" />
                    Restore
                  </button>
                </div>
              ))}
          </div>
        )}

        {/* Create */}
        <div className="flex gap-2 border-t border-coffee-100 pt-4">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && name.trim()) create.mutate();
            }}
            placeholder="New track name, e.g. Data Engineering"
          />
          <Button
            variant="secondary"
            disabled={create.isPending || name.trim().length === 0}
            onClick={() => create.mutate()}
          >
            <Plus className="size-4" />
            Create
          </Button>
        </div>
      </CardContent>

      {/* Resume Required modal (after track creation / "Add resume") */}
      <Dialog
        open={pendingTrack !== null}
        onClose={() => setPendingTrack(null)}
        title="Your new track is almost ready"
        description={`Each track needs its own resume before "${pendingTrack?.name ?? ""}" can be used for tailoring, ATS analysis, and applications.`}
        footer={
          <>
            {readyTracks.length > 0 ? (
              <div className="flex gap-2">
                <Select value={copyFrom} onChange={(e) => setCopyFrom(e.target.value)}>
                  <option value="">Choose an existing resume…</option>
                  {readyTracks
                    .filter((t) => t.id !== pendingTrack?.id)
                    .map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                </Select>
                <Button
                  variant="primary"
                  disabled={!copyFrom || duplicate.isPending}
                  onClick={() =>
                    pendingTrack &&
                    duplicate.mutate({ id: pendingTrack.id, sourceId: copyFrom })
                  }
                >
                  Use it
                </Button>
              </div>
            ) : null}
            <Button variant="ghost" onClick={() => setPendingTrack(null)}>
              I&apos;ll do this later
            </Button>
          </>
        }
      >
        <ul className="space-y-1.5 text-sm text-coffee-700">
          <li>• Resume Tailoring</li>
          <li>• ATS Analysis</li>
          <li>• Resume Intelligence</li>
          <li>• Job Applications</li>
        </ul>
        <p className="mt-3 flex items-start gap-2 text-sm text-coffee-500">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-status-interviewed" />
          Upload a source CV for this track in the section below, or copy an existing
          resume above.
        </p>
      </Dialog>
    </Card>
  );
}
