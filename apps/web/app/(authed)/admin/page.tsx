"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy, Layers, ShieldPlus, UserPlus, Globe } from "lucide-react";
import type {
  BoardSource,
  InviteCreatedResponse,
  MeResponse,
  Platform,
  SourceBoard,
} from "@jd/shared-types";
import { BOARD_SOURCES } from "@jd/shared-types";
import {
  authService,
  invitesService,
  platformsService,
  sourceBoardsService,
} from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
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
    toast.error("Couldn't copy, select and copy manually");
  }
}

function CreatedInvite({ invite }: { invite: InviteCreatedResponse }) {
  const link = fullLink(invite.signup_link);
  return (
    <div className="space-y-2 rounded-md border border-coffee-500/40 bg-coffee-100/50 p-4">
      <p className="text-sm font-medium text-coffee-900">
        Invite ready for {invite.email}
      </p>
      <p className="text-xs text-coffee-500">
        Share this link, the key{" "}
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

const platformSchema = z.object({ name: z.string().min(1, "Name is required") });
type PlatformForm = z.infer<typeof platformSchema>;

function PlatformsCard({ platforms }: { platforms: Platform[] }) {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PlatformForm>({
    resolver: zodResolver(platformSchema),
    defaultValues: { name: "" },
  });

  const create = useMutation({
    mutationFn: (v: PlatformForm) => platformsService.create(v),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: queryKeys.platforms });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      platformsService.setActive(id, active),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.platforms }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Platforms</CardTitle>
        <CardDescription>
          A platform is a label you attach admins to. Create one, then attach an
          admin when you invite them.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          onSubmit={handleSubmit((v) => create.mutate(v))}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          noValidate
        >
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="platform-name">New platform name</Label>
            <Input id="platform-name" placeholder="Acme Co." {...register("name")} />
            {errors.name && (
              <p className="text-sm text-status-rejected">{errors.name.message}</p>
            )}
          </div>
          <Button type="submit" disabled={create.isPending}>
            <Layers className="size-4" />
            {create.isPending ? "Creating…" : "Create platform"}
          </Button>
        </form>

        {platforms.length === 0 ? (
          <p className="text-sm text-coffee-500">No platforms yet.</p>
        ) : (
          <div className="divide-y divide-coffee-100 rounded-md border border-coffee-300">
            {platforms.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between gap-3 px-4 py-2.5"
              >
                <div>
                  <p className="text-sm font-medium text-coffee-900">{p.name}</p>
                  <p className="text-xs text-coffee-500">{p.slug}</p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={p.is_active ? "default" : "muted"}>
                    {p.is_active ? "active" : "inactive"}
                  </Badge>
                  <button
                    type="button"
                    onClick={() => toggle.mutate({ id: p.id, active: !p.is_active })}
                    disabled={toggle.isPending}
                    className="text-sm text-coffee-500 underline underline-offset-4 hover:text-coffee-900 disabled:opacity-60"
                  >
                    {p.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const adminSchema = z.object({
  email: z.string().email("Enter a valid email"),
  platform_id: z.string().min(1, "Pick a platform"),
});
type AdminForm = z.infer<typeof adminSchema>;

function InviteAdminCard({ platforms }: { platforms: Platform[] }) {
  const queryClient = useQueryClient();
  const [created, setCreated] = React.useState<InviteCreatedResponse | null>(null);
  const active = platforms.filter((p) => p.is_active);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AdminForm>({
    resolver: zodResolver(adminSchema),
    defaultValues: { email: "", platform_id: "" },
  });

  const invite = useMutation({
    mutationFn: (v: AdminForm) => invitesService.inviteAdmin(v),
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
        <CardTitle className="text-base">Invite an admin</CardTitle>
        <CardDescription>
          Creates an admin account attached to a platform. Admins are global and
          the platform is a label.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {active.length === 0 ? (
          <p className="text-sm text-coffee-500">
            Create a platform first, then you can invite an admin to it.
          </p>
        ) : (
          <form
            onSubmit={handleSubmit((v) => invite.mutate(v))}
            className="flex flex-col gap-3 sm:flex-row sm:items-end"
            noValidate
          >
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="admin-email">Email</Label>
              <Input id="admin-email" type="email" placeholder="admin@email.com" {...register("email")} />
              {errors.email && (
                <p className="text-sm text-status-rejected">{errors.email.message}</p>
              )}
            </div>
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="admin-platform">Platform</Label>
              <Select id="admin-platform" defaultValue="" {...register("platform_id")}>
                <option value="" disabled>
                  Select…
                </option>
                {active.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
              {errors.platform_id && (
                <p className="text-sm text-status-rejected">{errors.platform_id.message}</p>
              )}
            </div>
            <Button type="submit" disabled={invite.isPending}>
              <ShieldPlus className="size-4" />
              {invite.isPending ? "Generating…" : "Invite admin"}
            </Button>
          </form>
        )}
        {created && <CreatedInvite invite={created} />}
      </CardContent>
    </Card>
  );
}

function AdminsList() {
  const adminsQuery = useQuery({
    queryKey: queryKeys.admins,
    queryFn: () => platformsService.listAdmins(),
  });

  if (adminsQuery.isError) {
    return (
      <ErrorState
        description="Couldn't load admins."
        retry={() => adminsQuery.refetch()}
      />
    );
  }
  if (adminsQuery.isLoading) return <Skeleton className="h-40 w-full" />;
  if ((adminsQuery.data?.length ?? 0) === 0) {
    return <EmptyState title="No admins" description="Invited admins appear here." />;
  }

  return (
    <Card>
      <CardContent className="divide-y divide-coffee-100 p-0">
        {adminsQuery.data!.map((a) => (
          <div key={a.id} className="flex items-center justify-between gap-3 px-5 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-coffee-900">{a.name}</p>
              <p className="truncate text-xs text-coffee-500">{a.email}</p>
            </div>
            <Badge variant={a.platform_name ? "default" : "muted"}>
              {a.platform_name ?? "global"}
            </Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

const boardSchema = z.object({
  source: z.enum(["greenhouse", "lever", "ashby"]),
  token: z.string().min(1, "Token is required"),
  label: z.string().optional(),
});
type BoardForm = z.infer<typeof boardSchema>;

function JobBoardsCard() {
  const queryClient = useQueryClient();
  const boardsQuery = useQuery({
    queryKey: queryKeys.sourceBoards,
    queryFn: () => sourceBoardsService.list(),
  });
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BoardForm>({
    resolver: zodResolver(boardSchema),
    defaultValues: { source: "greenhouse", token: "", label: "" },
  });

  const create = useMutation({
    mutationFn: (v: BoardForm) =>
      sourceBoardsService.create({
        source: v.source as BoardSource,
        token: v.token,
        label: v.label || undefined,
      }),
    onSuccess: () => {
      reset();
      queryClient.invalidateQueries({ queryKey: queryKeys.sourceBoards });
    },
    onError: async (err) => toast.error((await toApiError(err)).message),
  });

  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      sourceBoardsService.setActive(id, active),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.sourceBoards }),
  });

  const boards = boardsQuery.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Globe className="size-4 text-coffee-500" />
          Job boards
        </CardTitle>
        <CardDescription>
          Company tokens the Greenhouse / Lever / Ashby scrapers pull from (the
          board slug in the company&apos;s careers URL). Aggregators (Adzuna,
          SerpApi) search by keyword and don&apos;t need these.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          onSubmit={handleSubmit((v) => create.mutate(v))}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          noValidate
        >
          <div className="space-y-1.5">
            <Label htmlFor="board-source">Source</Label>
            <Select id="board-source" {...register("source")}>
              {BOARD_SOURCES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="board-token">Board token</Label>
            <Input id="board-token" placeholder="e.g. airbnb" {...register("token")} />
            {errors.token && (
              <p className="text-sm text-status-rejected">{errors.token.message}</p>
            )}
          </div>
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="board-label">Label (optional)</Label>
            <Input id="board-label" placeholder="Airbnb" {...register("label")} />
          </div>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Adding…" : "Add board"}
          </Button>
        </form>

        {boards.length === 0 ? (
          <p className="text-sm text-coffee-500">No board tokens yet.</p>
        ) : (
          <div className="divide-y divide-coffee-100 rounded-md border border-coffee-300">
            {boards.map((b: SourceBoard) => (
              <div key={b.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-coffee-900">
                    {b.label || b.token}
                  </p>
                  <p className="truncate text-xs text-coffee-500">
                    {b.source} · {b.token}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={b.is_active ? "default" : "muted"}>
                    {b.is_active ? "active" : "inactive"}
                  </Badge>
                  <button
                    type="button"
                    onClick={() => toggle.mutate({ id: b.id, active: !b.is_active })}
                    disabled={toggle.isPending}
                    className="text-sm text-coffee-500 underline underline-offset-4 hover:text-coffee-900 disabled:opacity-60"
                  >
                    {b.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminPage() {
  const { data: me, isLoading } = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
  const platformsQuery = useQuery({
    queryKey: queryKeys.platforms,
    queryFn: () => platformsService.list(),
    enabled: me?.role === "admin",
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (me?.role !== "admin") {
    return (
      <EmptyState
        title="Admins only"
        description="This console manages platforms and admin accounts."
      />
    );
  }

  const platforms = platformsQuery.data ?? [];

  return (
    <div className="space-y-8">
      <PageHeading
        title="Admin"
        description="Manage platforms and admin accounts. Attach each admin to a platform when you invite them."
      />
      <div className="space-y-4">
        <PlatformsCard platforms={platforms} />
        <InviteAdminCard platforms={platforms} />
      </div>
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-coffee-900">Job sources</h2>
        <JobBoardsCard />
      </section>
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-coffee-900">Admins</h2>
        <AdminsList />
      </section>
    </div>
  );
}
