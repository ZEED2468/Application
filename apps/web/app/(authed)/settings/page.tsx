"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { KeyRound, Lock, CheckCircle2, XCircle, PlugZap } from "lucide-react";
import type { LlmKey, MeResponse } from "@jd/shared-types";
import { authService, settingsService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
import { PageHeading, EmptyState } from "@/components/states";
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
import { Skeleton } from "@/components/ui/skeleton";

export const dynamic = "force-dynamic";

const PROVIDERS: {
  id: string;
  label: string;
  needsBaseUrl: boolean;
  hint: string;
}[] = [
  { id: "anthropic", label: "Anthropic (Claude)", needsBaseUrl: false, hint: "sk-ant-…" },
  {
    id: "openai",
    label: "OpenAI-compatible",
    needsBaseUrl: true,
    hint: "OpenAI, Groq, Together, OpenRouter, or a local Ollama/LM Studio — set the base URL",
  },
  { id: "google", label: "Google (Gemini)", needsBaseUrl: false, hint: "AIza…" },
];

const STATUS: Record<string, { label: string; variant: "default" | "outline" | "muted" }> = {
  configured: { label: "Configured", variant: "default" },
  invalid: { label: "Invalid key", variant: "outline" },
  unreachable: { label: "Unreachable", variant: "outline" },
  unknown: { label: "Not validated", variant: "muted" },
};

export default function SettingsPage() {
  const { data: me } = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => authService.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const keysQuery = useQuery({
    queryKey: queryKeys.llmKeys,
    queryFn: () => settingsService.listLlmKeys(),
    enabled: me?.type !== "va",
  });

  if (me?.type === "va") {
    return (
      <EmptyState
        icon={<Lock className="size-8" />}
        title="Settings are hunter-only"
        description="AI provider keys are managed by the hunter you assist."
      />
    );
  }

  const byProvider = new Map<string, LlmKey>();
  (keysQuery.data ?? []).forEach((k) => byProvider.set(k.provider, k));

  return (
    <div className="space-y-6">
      <PageHeading
        title="Settings"
        description="Bring your own AI provider key. Your key is encrypted at rest and used for your own generations — CVs, cover letters, and ATS analysis."
      />

      <Card>
        <CardContent className="flex items-start gap-3 pt-6 text-sm text-coffee-600">
          <PlugZap className="mt-0.5 size-4 shrink-0 text-coffee-500" />
          <p>
            Add a key for any provider below and mark one “preferred” — it overrides the
            server default for your account. OpenAI-compatible hosts (Groq, Together,
            OpenRouter, Ollama…) use the <strong>OpenAI-compatible</strong> card with a base URL.
          </p>
        </CardContent>
      </Card>

      {keysQuery.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        PROVIDERS.map((p) => (
          <ProviderCard key={p.id} provider={p} existing={byProvider.get(p.id)} />
        ))
      )}
    </div>
  );
}

function ProviderCard({
  provider,
  existing,
}: {
  provider: { id: string; label: string; needsBaseUrl: boolean; hint: string };
  existing?: LlmKey;
}) {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = React.useState("");
  const [baseUrl, setBaseUrl] = React.useState(existing?.base_url ?? "");
  const [model, setModel] = React.useState(existing?.model ?? "");

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.llmKeys });
  const onErr = async (err: unknown) => {
    const e = await toApiError(err);
    toast.error(e.remediation ? `${e.message} — ${e.remediation}` : e.message);
  };

  const save = useMutation({
    mutationFn: () =>
      settingsService.upsertLlmKey({
        provider: provider.id,
        api_key: apiKey.trim() || undefined,
        base_url: baseUrl.trim() || undefined,
        model: model.trim() || undefined,
      }),
    onSuccess: () => {
      toast.success(`${provider.label} saved`);
      setApiKey("");
      invalidate();
    },
    onError: onErr,
  });

  const validate = useMutation({
    mutationFn: () => settingsService.validateLlmKey(provider.id),
    onSuccess: (k) => {
      toast[k.status === "configured" ? "success" : "error"](
        `${provider.label}: ${STATUS[k.status]?.label ?? k.status}`,
      );
      invalidate();
    },
    onError: onErr,
  });

  const prefer = useMutation({
    mutationFn: () => settingsService.setPreferred(provider.id),
    onSuccess: () => {
      toast.success(`${provider.label} is now preferred`);
      invalidate();
    },
    onError: onErr,
  });

  const remove = useMutation({
    mutationFn: () => settingsService.deleteLlmKey(provider.id),
    onSuccess: () => {
      toast.success(`${provider.label} removed`);
      invalidate();
    },
    onError: onErr,
  });

  const status = existing ? STATUS[existing.status] ?? STATUS.unknown : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-coffee-500" />
          {provider.label}
          {existing?.is_preferred && <Badge variant="default">Preferred</Badge>}
          {status && (
            <Badge variant={status.variant} className="ml-auto">
              {existing?.status === "configured" ? (
                <CheckCircle2 className="mr-1 size-3" />
              ) : existing?.status === "invalid" ? (
                <XCircle className="mr-1 size-3" />
              ) : null}
              {status.label}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          {existing?.has_key ? (
            <>
              Key on file: <span className="font-mono">{existing.masked_key}</span>
            </>
          ) : (
            provider.hint
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={`key-${provider.id}`}>
              {existing?.has_key ? "Replace API key" : "API key"}
            </Label>
            <Input
              id={`key-${provider.id}`}
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={provider.hint}
              autoComplete="off"
            />
          </div>
          {provider.needsBaseUrl && (
            <div className="space-y-1.5">
              <Label htmlFor={`base-${provider.id}`}>Base URL</Label>
              <Input
                id={`base-${provider.id}`}
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.groq.com/openai/v1"
              />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor={`model-${provider.id}`}>Model (optional)</Label>
            <Input
              id={`model-${provider.id}`}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="leave blank for the provider default"
            />
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            size="sm"
            disabled={save.isPending || (!existing?.has_key && !apiKey.trim())}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : "Save"}
          </Button>
          {existing?.has_key && (
            <>
              <Button
                variant="secondary"
                size="sm"
                disabled={validate.isPending}
                onClick={() => validate.mutate()}
              >
                {validate.isPending ? "Testing…" : "Test connection"}
              </Button>
              {!existing.is_preferred && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={prefer.isPending}
                  onClick={() => prefer.mutate()}
                >
                  Set preferred
                </Button>
              )}
              <Button
                variant="danger"
                size="sm"
                disabled={remove.isPending}
                onClick={() => remove.mutate()}
              >
                Remove
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
