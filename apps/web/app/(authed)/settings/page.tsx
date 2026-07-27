"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Star,
  RefreshCw,
  Trash2,
  Wand2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Pencil,
} from "lucide-react";
import type { Integration, IntegrationTemplate } from "@jd/shared-types";
import { integrationsService, type IntegrationInput } from "@/lib/api/services";
import { toastApiError } from "@/lib/toast-error";
import { queryKeys } from "@/lib/query-keys";
import { useIntegrationsUi } from "@/lib/stores/integrations-ui";
import { PageHeading } from "@/components/states";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";

export const dynamic = "force-dynamic";

const STATUS: Record<
  string,
  { label: string; cls: string; icon: React.ComponentType<{ className?: string }> }
> = {
  configured: { label: "Healthy", cls: "text-status-offer", icon: CheckCircle2 },
  healthy: { label: "Healthy", cls: "text-status-offer", icon: CheckCircle2 },
  invalid: { label: "Invalid key", cls: "text-status-rejection", icon: XCircle },
  unreachable: { label: "Offline", cls: "text-status-interviewed", icon: AlertTriangle },
  offline: { label: "Offline", cls: "text-status-interviewed", icon: AlertTriangle },
  rate_limited: { label: "Rate limited", cls: "text-status-interviewed", icon: AlertTriangle },
  unknown: { label: "Not tested", cls: "text-coffee-400", icon: HelpCircle },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? STATUS.unknown;
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${s.cls}`}>
      <Icon className="size-3.5" />
      {s.label}
    </span>
  );
}

export default function IntegrationsPage() {
  const qc = useQueryClient();
  const ui = useIntegrationsUi();

  const templates = useQuery({
    queryKey: queryKeys.integrationTemplates,
    queryFn: () => integrationsService.templates(),
  });
  const integrations = useQuery({
    queryKey: queryKeys.integrations,
    queryFn: () => integrationsService.list(),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: queryKeys.integrations });
    qc.invalidateQueries({ queryKey: queryKeys.readiness });
  };

  const validate = useMutation({
    mutationFn: (id: string) => integrationsService.validate(id),
    onSuccess: () => invalidate(),
    onError: (e) => toastApiError(e),
  });
  const discover = useMutation({
    mutationFn: (id: string) => integrationsService.discoverModels(id),
    onSuccess: (it) => {
      invalidate();
      toast.success(`Found ${it.models.length} model${it.models.length === 1 ? "" : "s"}.`);
    },
    onError: (e) => toastApiError(e),
  });
  const setDefault = useMutation({
    mutationFn: (id: string) => integrationsService.setDefault(id),
    onSuccess: () => invalidate(),
    onError: (e) => toastApiError(e),
  });
  const remove = useMutation({
    mutationFn: (id: string) => integrationsService.remove(id),
    onSuccess: () => invalidate(),
    onError: (e) => toastApiError(e),
  });

  const tplFor = (it: Integration) =>
    (templates.data ?? []).find((t) => t.id === it.template) ??
    (templates.data ?? []).find((t) => t.provider === it.provider) ??
    null;

  return (
    <div className="space-y-6">
      <PageHeading
        title="AI Integrations"
        description="Configure the AI providers that power tailoring, ATS analysis, and generation. Keys are encrypted at rest and never shown again."
      />

      <Card>
        <CardHeader>
          <CardTitle>Quick setup</CardTitle>
          <CardDescription>Pick a provider to configure in under a minute.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(templates.data ?? []).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => ui.openCreate(t)}
                className="flex flex-col items-start gap-1 rounded-lg border border-coffee-300 p-4 text-left transition-colors hover:bg-coffee-100/50"
              >
                <span className="text-2xl leading-none">{t.icon}</span>
                <span className="mt-1 text-sm font-medium text-coffee-900">{t.name}</span>
                <span className="text-xs text-coffee-500">{t.description}</span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configured integrations</CardTitle>
          <CardDescription>The one marked Default powers your AI features.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {integrations.isLoading ? (
            <p className="text-sm text-coffee-400">Loading…</p>
          ) : (integrations.data ?? []).length === 0 ? (
            <p className="text-sm text-coffee-300">None yet — add one from Quick setup above.</p>
          ) : (
            integrations.data!.map((it) => (
              <IntegrationRow
                key={it.id}
                it={it}
                onValidate={() => validate.mutate(it.id)}
                validating={validate.isPending}
                onDiscover={() => discover.mutate(it.id)}
                discovering={discover.isPending}
                onDefault={() => setDefault.mutate(it.id)}
                onDelete={() => remove.mutate(it.id)}
                onEdit={() => ui.openEdit(tplFor(it), it.id)}
              />
            ))
          )}
        </CardContent>
      </Card>

      <IntegrationFormDialog />
    </div>
  );
}

function IntegrationRow({
  it,
  onValidate,
  validating,
  onDiscover,
  discovering,
  onDefault,
  onDelete,
  onEdit,
}: {
  it: Integration;
  onValidate: () => void;
  validating: boolean;
  onDiscover: () => void;
  discovering: boolean;
  onDefault: () => void;
  onDelete: () => void;
  onEdit: () => void;
}) {
  return (
    <div className="rounded-md border border-coffee-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-coffee-900">{it.name}</span>
            {it.is_default && <Badge variant="default">Default</Badge>}
            <StatusBadge status={it.status} />
          </div>
          <p className="mt-0.5 truncate text-xs text-coffee-500">
            {it.provider}
            {it.base_url ? ` · ${it.base_url}` : ""}
            {it.model ? ` · ${it.model}` : ""}
            {it.masked_key ? ` · ${it.masked_key}` : " · no key"}
          </p>
          {it.models.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {it.models.slice(0, 10).map((m) => (
                <span
                  key={m}
                  className="rounded border border-coffee-200 px-1.5 py-0.5 text-[0.65rem] text-coffee-600"
                >
                  {m}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button size="sm" variant="secondary" onClick={onValidate} disabled={validating}>
            <RefreshCw className="size-3.5" />
            Test
          </Button>
          <Button size="sm" variant="ghost" onClick={onDiscover} disabled={discovering}>
            <Wand2 className="size-3.5" />
            Models
          </Button>
          {!it.is_default && (
            <button
              type="button"
              onClick={onDefault}
              title="Set as default"
              className="rounded p-1.5 text-coffee-400 hover:text-coffee-900"
            >
              <Star className="size-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onEdit}
            title="Edit"
            className="rounded p-1.5 text-coffee-400 hover:text-coffee-900"
          >
            <Pencil className="size-4" />
          </button>
          <button
            type="button"
            onClick={onDelete}
            title="Delete"
            className="rounded p-1.5 text-coffee-400 hover:text-status-rejection"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function IntegrationFormDialog() {
  const ui = useIntegrationsUi();
  const qc = useQueryClient();
  const [values, setValues] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    setValues({});
  }, [ui.formOpen, ui.template?.id, ui.editingId]);

  const save = useMutation({
    mutationFn: () => {
      const body: IntegrationInput = { template: ui.template?.id ?? undefined, ...values };
      return ui.editingId
        ? integrationsService.update(ui.editingId, body)
        : integrationsService.create(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.integrations });
      qc.invalidateQueries({ queryKey: queryKeys.readiness });
      toast.success("Integration saved.");
      ui.close();
    },
    onError: (e) => toastApiError(e),
  });

  const t: IntegrationTemplate | null = ui.template;
  if (!t) return null;

  return (
    <Dialog
      open={ui.formOpen}
      onClose={ui.close}
      title={ui.editingId ? `Edit ${t.name}` : `Configure ${t.name}`}
      description={t.description}
      footer={
        <Button variant="primary" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save"}
        </Button>
      }
    >
      <div className="space-y-3">
        {t.fields.map((f) => (
          <div key={f.id} className="space-y-1">
            <Label htmlFor={`f-${f.id}`}>
              {f.label}
              {f.required && <span className="text-status-rejection"> *</span>}
            </Label>
            <Input
              id={`f-${f.id}`}
              type={f.type === "password" ? "password" : f.type === "url" ? "url" : "text"}
              placeholder={f.placeholder}
              value={values[f.id] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [f.id]: e.target.value }))}
            />
            {f.help && <p className="text-xs text-coffee-400">{f.help}</p>}
          </div>
        ))}
        {ui.editingId && (
          <p className="text-xs text-coffee-400">
            Leave the key blank to keep the existing one.
          </p>
        )}
      </div>
    </Dialog>
  );
}
