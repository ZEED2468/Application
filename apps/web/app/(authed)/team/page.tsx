"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, UserPlus, Users } from "lucide-react";
import type { InviteCreatedResponse, MeResponse, Track } from "@jd/shared-types";
import { authService, invitesService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
import { TRACK_LABELS } from "@/lib/status";
import { PageHeading, EmptyState, ErrorState } from "@/components/states";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { TRACKS } from "@jd/shared-types";

export const dynamic = "force-dynamic";

function fullLink(signupLink: string): string {
  if (typeof window === "undefined") return signupLink;
  return `${window.location.origin}${signupLink}`;
}

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success("Invite link copied");
  } catch {
    toast.error("Couldn't copy — select and copy manually");
  }
}

/** A one-time panel shown right after an invite is created (the key is never shown again). */
function CreatedInvite({ invite }: { invite: InviteCreatedResponse }) {
  const link = fullLink(invite.signup_link);
  return (
    <div className="space-y-2 rounded-md border border-coffee-500/40 bg-coffee-100/50 p-4">
      <p className="text-sm font-medium text-coffee-900">
        Invite ready for {invite.email}
      </p>
      <p className="text-xs text-coffee-500">
        Share this link — the key{" "}
        <span className="font-mono font-semibold tracking-widest text-coffee-900">
          {invite.key}
        </span>{" "}
        is shown only once.
      </p>
      <div className="flex items-center gap-2">
        <Input readOnly value={link} className="font-mono text-xs" />
        <Button type="button" variant="secondary" size="icon" onClick={() => copy(link)}>
          <Copy className="size-4" />
        </Button>
      </div>
    </div>
  );
}

const vaSchema = z.object({
  email: z.string().email("Enter a valid email"),
  va_name: z.string().min(1, "Name is required"),
  whatsapp: z.string().min(5, "Enter a WhatsApp number"),
  track: z.string(),
});
type VaForm = z.infer<typeof vaSchema>;

function InviteVaCard() {
  const queryClient = useQueryClient();
  const [created, setCreated] = React.useState<InviteCreatedResponse | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<VaForm>({
    resolver: zodResolver(vaSchema),
    defaultValues: { email: "", va_name: "", whatsapp: "", track: "" },
  });

  const invite = useMutation({
    mutationFn: (v: VaForm) =>
      invitesService.inviteVa({
        email: v.email,
        va_name: v.va_name,
        whatsapp: v.whatsapp,
        track: v.track ? (v.track as Track) : null,
      }),
    onSuccess: (res) => {
      setCreated(res);
      reset();
      queryClient.invalidateQueries({ queryKey: queryKeys.invites });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Invite a VA</CardTitle>
        <CardDescription>
          Your assistant gets your dashboard to help with applications — but
          can't edit your CV / cover letter or invite anyone.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          onSubmit={handleSubmit((v) => invite.mutate(v))}
          className="space-y-3"
          noValidate
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="va-email">Email</Label>
              <Input id="va-email" type="email" placeholder="va@email.com" {...register("email")} />
              {errors.email && (
                <p className="text-sm text-status-rejected">{errors.email.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="va-name">Name</Label>
              <Input id="va-name" placeholder="Vera Assistant" {...register("va_name")} />
              {errors.va_name && (
                <p className="text-sm text-status-rejected">{errors.va_name.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="va-wa">WhatsApp number</Label>
              <Input id="va-wa" placeholder="+234 801 234 5678" {...register("whatsapp")} />
              {errors.whatsapp && (
                <p className="text-sm text-status-rejected">{errors.whatsapp.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="va-track">Track scope</Label>
              <Select id="va-track" {...register("track")}>
                <option value="">All tracks</option>
                {TRACKS.map((t) => (
                  <option key={t} value={t}>
                    {TRACK_LABELS[t]}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <Button type="submit" disabled={invite.isPending}>
            <UserPlus className="size-4" />
            {invite.isPending ? "Generating…" : "Generate invite"}
          </Button>
        </form>
        {created && <CreatedInvite invite={created} />}
      </CardContent>
    </Card>
  );
}

const hunterSchema = z.object({ email: z.string().email("Enter a valid email") });
type HunterForm = z.infer<typeof hunterSchema>;

function InviteHunterCard() {
  const queryClient = useQueryClient();
  const [created, setCreated] = React.useState<InviteCreatedResponse | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<HunterForm>({
    resolver: zodResolver(hunterSchema),
    defaultValues: { email: "" },
  });

  const invite = useMutation({
    mutationFn: (v: HunterForm) => invitesService.inviteHunter(v),
    onSuccess: (res) => {
      setCreated(res);
      reset();
      queryClient.invalidateQueries({ queryKey: queryKeys.invites });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Invite a hunter</CardTitle>
        <CardDescription>
          Admin only. Creates a full hunter account from an invite key.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          onSubmit={handleSubmit((v) => invite.mutate(v))}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          noValidate
        >
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="hunter-email">Email</Label>
            <Input id="hunter-email" type="email" placeholder="hunter@email.com" {...register("email")} />
            {errors.email && (
              <p className="text-sm text-status-rejected">{errors.email.message}</p>
            )}
          </div>
          <Button type="submit" disabled={invite.isPending}>
            <UserPlus className="size-4" />
            {invite.isPending ? "Generating…" : "Generate invite"}
          </Button>
        </form>
        {created && <CreatedInvite invite={created} />}
      </CardContent>
    </Card>
  );
}

function InvitesList() {
  const invitesQuery = useQuery({
    queryKey: queryKeys.invites,
    queryFn: () => invitesService.list(),
  });
  const queryClient = useQueryClient();
  const revoke = useMutation({
    mutationFn: (id: string) => invitesService.revoke(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.invites }),
  });

  const statusVariant = (s: string) =>
    s === "accepted" ? "default" : s === "revoked" ? "muted" : "outline";

  if (invitesQuery.isError) {
    return (
      <ErrorState
        description="Couldn't load invites."
        retry={() => invitesQuery.refetch()}
      />
    );
  }
  if (invitesQuery.isLoading) return <Skeleton className="h-40 w-full" />;
  if ((invitesQuery.data?.length ?? 0) === 0) {
    return (
      <EmptyState
        icon={<Users className="size-8" />}
        title="No invites yet"
        description="Invites you create appear here with their status."
      />
    );
  }

  return (
    <Card>
      <CardContent className="divide-y divide-coffee-100 p-0">
        {invitesQuery.data!.map((inv) => (
          <div
            key={inv.id}
            className="flex items-center justify-between gap-3 px-5 py-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-coffee-900">
                {inv.email}
              </p>
              <p className="text-xs text-coffee-500">
                {inv.kind === "va" ? "VA" : "Hunter"}
                {inv.va_name ? ` · ${inv.va_name}` : ""}
                {inv.track ? ` · ${TRACK_LABELS[inv.track]}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant={statusVariant(inv.status)}>{inv.status}</Badge>
              {inv.status === "pending" && (
                <button
                  type="button"
                  onClick={() => revoke.mutate(inv.id)}
                  disabled={revoke.isPending}
                  className="text-sm text-coffee-500 underline underline-offset-4 hover:text-status-rejected disabled:opacity-60"
                >
                  Revoke
                </button>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function TeamPage() {
  const { data: me, isLoading } = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;

  // VAs can't manage a team. (The nav hides this; this guards a direct visit.)
  if (me?.type === "va") {
    return (
      <EmptyState
        icon={<Users className="size-8" />}
        title="Not available for assistants"
        description="Inviting and team management is handled by the hunter you assist."
      />
    );
  }

  const isAdmin = me?.role === "admin";

  return (
    <div className="space-y-8">
      <PageHeading
        title="Team"
        description="Invite a VA to help with your applications. Each invite is a one-time key tied to an email."
      />
      <div className="space-y-4">
        <InviteVaCard />
        {isAdmin && <InviteHunterCard />}
      </div>
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-coffee-900">Your invites</h2>
        <InvitesList />
      </section>
    </div>
  );
}
