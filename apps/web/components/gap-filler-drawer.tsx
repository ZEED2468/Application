"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { jobsService } from "@/lib/api/services";
import type { Gap } from "@/lib/api/services/jobs";
import { toastApiError } from "@/lib/toast-error";
import { queryKeys } from "@/lib/query-keys";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

/**
 * Claude-style gap-filler, rendered inside the workspace side-panel. Walks the JD's
 * missing skills one question at a time; a "Yes" adds the skill to the profile
 * (truth-bounded, per-track) and, at the end, regenerates the résumé so the confirmed
 * skills actually land in the document. Its actions live inline at the bottom.
 */
export function GapFiller({
  jobId,
  onRegenerated,
  onClose,
}: {
  jobId: string;
  onRegenerated?: () => void;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [index, setIndex] = React.useState(0);
  const [detail, setDetail] = React.useState("");
  const [confirmed, setConfirmed] = React.useState<string[]>([]);

  const { data: gaps, isLoading } = useQuery({
    queryKey: ["job-gaps", jobId],
    queryFn: () => jobsService.gaps(jobId),
    staleTime: 0,
  });

  const total = gaps?.length ?? 0;
  const current: Gap | undefined = gaps?.[index];
  const done = !isLoading && (total === 0 || index >= total);

  const advance = () => {
    setDetail("");
    setIndex((i) => i + 1);
  };

  const confirm = useMutation({
    mutationFn: (g: Gap) => jobsService.confirmSkill(jobId, g.skill, detail),
    onSuccess: (_d, g) => {
      const added = detail.trim() || g.skill;
      setConfirmed((c) => [...c, added]);
      toast.success(`Added "${added}" to your profile.`);
      advance();
    },
    onError: (err) => toastApiError(err, "Couldn't add that skill"),
  });

  const regen = useMutation({
    mutationFn: () => jobsService.generate(jobId, false, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) });
      toast.success("Résumé regenerated with your confirmed skills.");
      onRegenerated?.();
      onClose();
    },
    onError: (err) => toastApiError(err, "Couldn't regenerate"),
  });

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1">
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-coffee-500">
            <Loader2 className="size-4 animate-spin" /> Finding the gaps…
          </div>
        ) : !done && current ? (
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-coffee-500">
              Skill {index + 1} of {total}
            </p>
            <div className="rounded-lg border border-coffee-200 bg-coffee-50 p-4">
              <p className="text-base font-medium text-coffee-900">
                {current.question}
              </p>
              {current.reason && (
                <p className="mt-1.5 text-sm text-coffee-500">{current.reason}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gap-detail">Add a detail (optional)</Label>
              <Textarea
                id="gap-detail"
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                placeholder={`e.g. how you've used ${current.skill}`}
                className="min-h-[72px] text-sm"
              />
            </div>
            <p className="text-xs text-coffee-400">
              Only confirm skills you genuinely have — this adds them to your profile
              as true, available for every job on this track.
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <CheckCircle2 className="size-10 text-status-offer" />
            <p className="text-sm text-coffee-700">
              {confirmed.length > 0
                ? `Added ${confirmed.length} skill${confirmed.length > 1 ? "s" : ""} to your profile.`
                : total === 0
                  ? "No gaps to fill — your CV already covers the job's must-haves."
                  : "No new skills added."}
            </p>
            {confirmed.length > 0 && (
              <div className="flex flex-wrap justify-center gap-1.5">
                {confirmed.map((s) => (
                  <Badge key={s} variant="outline">
                    {s}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {!isLoading && (
        <div className="mt-4 border-t border-coffee-100 pt-4">
          {!done && current ? (
            <div className="flex gap-2">
              <Button
                variant="secondary"
                className="flex-1"
                onClick={advance}
                disabled={confirm.isPending}
              >
                Not really — skip
              </Button>
              <Button
                variant="primary"
                className="flex-1"
                onClick={() => confirm.mutate(current)}
                disabled={confirm.isPending}
              >
                {confirm.isPending ? "Adding…" : "Yes, I have it"}
              </Button>
            </div>
          ) : confirmed.length > 0 ? (
            <Button
              variant="primary"
              className="w-full"
              onClick={() => regen.mutate()}
              disabled={regen.isPending}
            >
              <Sparkles className="size-4" />
              {regen.isPending ? "Regenerating…" : "Regenerate résumé with these"}
            </Button>
          ) : (
            <Button variant="secondary" className="w-full" onClick={onClose}>
              Close
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
