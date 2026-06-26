import { HTTPError } from "ky";
import type {
  LatexKind,
  LatexPreviewError,
  RegenerateRequest,
  RegenerateResult,
} from "@jd/shared-types";
import { api, path } from "../client";

/** Thrown by `latexService.preview` when the LaTeX is valid but does not compile
 *  (HTTP 422). Carries the tectonic stderr so the builder can show it. */
export class LatexCompileError extends Error {
  stderr: string;
  constructor(stderr: string) {
    super("LaTeX did not compile");
    this.name = "LatexCompileError";
    this.stderr = stderr;
  }
}

export const latexService = {
  /** Compile editor LaTeX to a PDF blob for the iframe. Throws LatexCompileError on 422. */
  async preview(latex: string, kind: LatexKind = "cv"): Promise<Blob> {
    try {
      const res = await api.post(path("/api/latex/preview"), {
        json: { latex, kind },
      });
      return await res.blob();
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 422) {
        const body = (await err.response
          .clone()
          .json()
          .catch(() => null)) as LatexPreviewError | null;
        throw new LatexCompileError(body?.stderr ?? "compile failed");
      }
      throw err;
    }
  },

  /** Draft tailored CV + cover LaTeX from the ATS recommendations (may call the LLM). */
  async regenerate(req: RegenerateRequest): Promise<RegenerateResult> {
    return api
      .post(path("/api/latex/regenerate"), { json: req, timeout: 120000 })
      .json<RegenerateResult>();
  },
};
