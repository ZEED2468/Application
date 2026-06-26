"use client";

import * as React from "react";
import { FileWarning, Loader2, Play } from "lucide-react";
import type { LatexKind } from "@jd/shared-types";
import { latexService, LatexCompileError } from "@/lib/api/services";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/**
 * Side-by-side LaTeX editor (left) + compiled PDF preview (right). The preview
 * recompiles on an explicit "Compile preview" click (tectonic ~2–5s) — the editor
 * is the human fix-up before "Use this template" commits the LaTeX to the job.
 */
export function LatexBuilder({
  kind,
  value,
  onChange,
  onUse,
  useLabel = "Use this template",
  busy = false,
  disabled = false,
}: {
  kind: LatexKind;
  value: string;
  onChange: (next: string) => void;
  onUse?: (latex: string) => void;
  useLabel?: string;
  busy?: boolean;
  disabled?: boolean;
}) {
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [compiling, setCompiling] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const urlRef = React.useRef<string | null>(null);

  const setUrl = React.useCallback((next: string | null) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = next;
    setPreviewUrl(next);
  }, []);

  // Revoke the last object URL on unmount.
  React.useEffect(() => () => setUrl(null), [setUrl]);

  async function compile() {
    if (!value.trim()) return;
    setCompiling(true);
    setError(null);
    try {
      const blob = await latexService.preview(value, kind);
      setUrl(URL.createObjectURL(blob));
    } catch (err) {
      if (err instanceof LatexCompileError) {
        setError(err.stderr || "The LaTeX did not compile.");
      } else {
        setError("Couldn't compile — check the LaTeX and try again.");
      }
    } finally {
      setCompiling(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <Label htmlFor={`latex-${kind}`}>LaTeX source</Label>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={compile}
              disabled={compiling || disabled || !value.trim()}
            >
              {compiling ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              {compiling ? "Compiling…" : "Compile preview"}
            </Button>
            {onUse && (
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => onUse(value)}
                disabled={busy || disabled || !value.trim()}
              >
                {busy ? "Saving…" : useLabel}
              </Button>
            )}
          </div>
        </div>
        <Textarea
          id={`latex-${kind}`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
          disabled={disabled}
          className="h-[68vh] resize-none font-mono text-xs leading-relaxed"
          placeholder="Your tailored LaTeX appears here after regenerating, or paste your own."
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label>Preview</Label>
        <div className="h-[68vh] overflow-hidden rounded-md border border-coffee-300 bg-coffee-50">
          {error ? (
            <div className="flex h-full flex-col gap-2 overflow-auto p-4">
              <p className="flex items-center gap-2 text-sm font-medium text-status-rejected">
                <FileWarning className="size-4" />
                Compile error
              </p>
              <pre className="whitespace-pre-wrap text-xs leading-relaxed text-coffee-700">
                {error}
              </pre>
            </div>
          ) : previewUrl ? (
            <iframe src={previewUrl} title={`${kind} preview`} className="h-full w-full" />
          ) : (
            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-coffee-400">
              Click “Compile preview” to render the PDF.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
