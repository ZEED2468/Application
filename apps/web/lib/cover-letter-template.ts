const DEFAULT_PREVIEW = {
  company: "Acme Corp",
  role: "Senior Engineer",
  name: "Jane Doe",
} as const;

/** Replace {company}, {role}, {name} placeholders for an in-app preview. */
export function previewCoverLetterTemplate(
  body: string,
  overrides?: Partial<Record<keyof typeof DEFAULT_PREVIEW, string>>,
): string {
  if (!body.trim()) return "";
  const vars = { ...DEFAULT_PREVIEW, ...overrides };
  return body
    .replaceAll("{company}", vars.company)
    .replaceAll("{role}", vars.role)
    .replaceAll("{name}", vars.name)
    .replaceAll("{candidate_name}", vars.name);
}
