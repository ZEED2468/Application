/**
 * @jd/shared-types
 * Shared API contract types for the Job Application & Outreach Engine.
 * Consumed by apps/web (and intended to mirror the FastAPI backend schemas).
 */

/* ----------------------------------------------------------------------------
 * Enums / unions
 * ------------------------------------------------------------------------- */

export type Track = "frontend" | "backend" | "general";

export type Origin = "auto" | "manual";

/** Application tracker status — the dashboard dropdown */
export type TrackerStatus =
  | "not_applied"
  | "applied"
  | "no_response"
  | "interviewed"
  | "offer"
  | "rejection";

export const TRACKER_STATUSES: TrackerStatus[] = [
  "not_applied",
  "applied",
  "no_response",
  "interviewed",
  "offer",
  "rejection",
];

/** Statuses selectable once an application record exists (post-submit). */
export const TRACKER_STATUSES_POST_SUBMIT: TrackerStatus[] = [
  "applied",
  "no_response",
  "interviewed",
  "offer",
  "rejection",
];

export const TRACKS: Track[] = ["frontend", "backend", "general"];

/** job.status — internal pipeline stage */
export type JobStatus =
  | "discovered"
  | "scored"
  | "ready"
  | "submitted";

/** outreach sequence step */
export type OutreachStep = "first" | "followup1" | "followup2" | "stopped";

/** Sending-domain warm-up lifecycle */
export type WarmupStage =
  | "cold"
  | "warming"
  | "ready"
  | "paused";

/* ----------------------------------------------------------------------------
 * Auth
 * ------------------------------------------------------------------------- */

/** auth principal kind, as returned by the backend `/me` (`type` field). */
export type PrincipalType = "user" | "va";

/** the `role` field on `/me`: hunters/admins are `user`s; VAs report `"va"`. */
export type Role = "hunter" | "admin" | "va";

export interface MeResponse {
  id: string;
  type: PrincipalType;
  email: string;
  name: string;
  role: Role;
  /** the platform an admin is attached to (label; admins are still global) */
  platform_id?: string | null;
  platform_name?: string | null;
  /** the hunter's currently-active track (drives the dashboard track switcher) */
  active_track?: Track | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

/* --- Invite-gated signup --- */

export type InviteKind = "hunter" | "va" | "admin";
export type InviteStatus = "pending" | "accepted" | "revoked";

export interface RegisterRequest {
  email: string;
  password: string;
  key: string;
}

export interface HunterInviteRequest {
  email: string;
}

export interface AdminInviteRequest {
  email: string;
  platform_id: string;
}

/* --- Admin platforms --- */

export interface Platform {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
}

export interface PlatformCreate {
  name: string;
}

export interface AdminOut {
  id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  platform_id?: string | null;
  platform_name?: string | null;
}

/* --- Job-board scrapers (Greenhouse/Lever/Ashby company tokens) --- */

export type BoardSource = "greenhouse" | "lever" | "ashby";

export const BOARD_SOURCES: BoardSource[] = ["greenhouse", "lever", "ashby"];

export interface SourceBoard {
  id: string;
  source: BoardSource;
  token: string;
  label?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface SourceBoardCreate {
  source: BoardSource;
  token: string;
  label?: string;
}

export interface VaInviteRequest {
  email: string;
  whatsapp: string;
  track?: Track | null;
}

export interface InviteOut {
  id: string;
  email: string;
  kind: InviteKind;
  status: InviteStatus;
  track?: Track | null;
  whatsapp?: string | null;
  platform_id?: string | null;
  expires_at: string;
  created_at: string;
}

/** Returned once at creation — carries the raw key + a ready-to-share link. */
export interface InviteCreatedResponse extends InviteOut {
  key: string;
  signup_link: string;
}

/* ----------------------------------------------------------------------------
 * ATS
 * ------------------------------------------------------------------------- */

export interface AtsBreakdown {
  matched_keywords: string[];
  missing_keywords: string[];
  /** Structural parseability of the rendered artifact. `unevaluated` when no artifact was
   *  inspected — absence of a measurement is never a pass. */
  gate?: { status: "pass" | "fail" | "unevaluated"; [k: string]: unknown };
  coverage?: number;
  supporting_coverage?: number;
  critical_keywords?: string[];
  matched_critical?: string[];
  missing_critical?: string[];
  criticals_total?: number;
  criticals_covered?: number;
  criticals_coverage?: number;
  /** Title/seniority fit — a reach signal, deliberately NOT folded into the score. */
  stretch?: { title_alignment: number; is_stretch: boolean };
  title_alignment?: number;
  false_positives?: string[];
  framing?: string;
  /** deprecated: the hardcoded format flags were removed; use `gate` */
  format_flags?: Record<string, boolean> | string[];
  /** set after optional AI vet pass */
  ai_vetted?: boolean;
  ai_removed?: string[];
  ai_notes?: string;
  track_match?: {
    track: Track;
    method: string;
    reason: string;
  };
}

export interface AtsAiGap {
  skill: string;
  severity: string;
  reason: string;
}

export interface AtsAiAnalysis {
  fit_score: number | null;
  fit_summary: string;
  strengths: string[];
  gaps: AtsAiGap[];
  recommendations: string[];
  false_positives: string[];
  verdict: string;
  ai_powered?: boolean;
}

export interface AtsProfileSource {
  track: Track;
  filename: string | null;
  word_count: number;
  confirmed: boolean;
}

export interface AtsSources {
  tracks: AtsProfileSource[];
  cover_letter_template: CoverLetterTemplate | null;
}

/** Global ATS checker: any CV vs any JD. */
export interface AtsCheckResult {
  role_title: string;
  track?: Track | null;
  cv_source?: "profile" | "upload" | "paste";
  cv_filename: string | null;
  cv_word_count: number;
  track_match?: {
    track: Track;
    method: string;
    reason: string;
  } | null;
  cover_letter_template?: CoverLetterTemplate | null;
  /** Whether the AI review layer was live for this run (capability, declared up front). */
  ai_live?: boolean;
  /** Id + version of the persisted `ats_analysis` row this result was recorded as. */
  analysis_id?: string | null;
  version?: number | null;
  rule_based: {
    /** null when the format gate failed — a fix-first state, never a fabricated number. */
    score: number | null;
    breakdown: AtsBreakdown;
    gaps: string[];
  };
  ai: AtsAiAnalysis | null;
  /** Resume Intelligence workspace (deterministic + advisory); optional/back-compat. */
  intelligence?: ResumeIntelligence | null;
}

/** The latest persisted ATS analysis for a job (or standalone) — GET /api/ats/analysis. */
export interface AtsLatestAnalysis {
  analysis_id: string;
  version: number;
  gate_status: "pass" | "fail" | "unevaluated";
  score: number | null;
  recs: RegenerateAtsRecs;
}

/* ---- Resume Intelligence (R5) ---- */

export interface AtsFlag {
  code: string;
  severity: string; // "warn" | "info"
  message: string;
}

export interface ToolAnalysis {
  required: string[];
  represented: string[];
  missing: string[];
  underutilized_verified: string[];
}

export interface StructureReview {
  word_count: number;
  est_pages: number;
  headings: string[];
  summary_present: boolean;
  uses_objective: boolean;
  contact: { email: boolean; phone: boolean; linkedin: boolean; github: boolean };
  bullet_count: number;
  first_person_count: number;
  ats_flags: AtsFlag[];
}

export interface WeakVerb {
  bullet: string;
  weak_verb: string;
  suggestions: string[];
}

export interface BulletCoaching {
  original: string;
  framework: string; // "PAR" | "XYZ" | "verb"
  suggestion: string;
}

export interface SkillsAlignment {
  strong: string[];
  weak: string[];
  missing: string[];
  omitted_for_truth: string[];
}

export interface ResumeAdvisory {
  bullet_coaching: BulletCoaching[];
  summary_review: { present: boolean; issues: string[]; suggestion: string | null };
  skills_alignment: SkillsAlignment;
  ai_powered: boolean;
}

export interface ResumeIntelligence {
  tools: ToolAnalysis;
  structure: StructureReview;
  verbs: WeakVerb[];
  lint: { findings: AtsFlag[]; count: number };
  advisory: ResumeAdvisory | null;
}

export interface GeneratedCv {
  pdf_url: string | null;
  /** auth-scoped download endpoint (presigned R2 redirect) */
  download_url?: string | null;
  ats_score: number | null;
  ats_breakdown: AtsBreakdown | null;
  /** the committed CV LaTeX — lets the editor open YOUR current résumé to tweak */
  latex_source?: string | null;
}

export interface CoverLetter {
  pdf_url: string | null;
  download_url?: string | null;
  /** the tailored 3-paragraph body text */
  body?: string | null;
  /** the committed cover LaTeX — lets the editor open YOUR current cover letter to tweak */
  latex_source?: string | null;
}

/* ----------------------------------------------------------------------------
 * Jobs / Applications
 * ------------------------------------------------------------------------- */

export interface JobOut {
  id: string;
  company: string;
  role: string;
  track: Track | string;
  origin: Origin;
  status: JobStatus;
  ats_score: number | null;
  /** application id, present once an application object exists */
  application_id: string | null;
  application_status: TrackerStatus | null;
  location?: string | null;
  url?: string | null;
  created_at?: string;
  /** Full job description text */
  description?: string | null;
  /** Truncated preview for table rows */
  jd_preview?: string | null;
  /** Google Docs viewer URL for tailored resume PDF */
  resume_doc_url?: string | null;
  /** Google Docs viewer URL for tailored cover letter PDF */
  cover_letter_doc_url?: string | null;
  experience_level?: string | null;
}

export interface SourceDiscoverResult {
  source: string;
  found: number;
  inserted: number;
  error?: string | null;
  /** why a source found nothing (e.g. "no SERPAPI_API_KEY in this environment") */
  note?: string | null;
}

export interface DiscoverReport {
  discovered: number;
  fake_mode: boolean;
  profiles: number;
  sources: SourceDiscoverResult[];
}

export interface ApplicationSummary {
  id: string;
  status: TrackerStatus;
  submitted_at?: string | null;
}

/** Generic paginated list wrapper returned by the list endpoints. */
export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** A tracker row with VA-credibility signals (in-app, read-only tracker). */
export interface TrackerApplication {
  id: string;
  job_id: string;
  company: string | null;
  role: string | null;
  track: Track | null;
  origin: Origin | null;
  status: string;
  tracker_status: TrackerStatus;
  submitted_at?: string | null;
  ats_score?: number | null;
  relevance_score?: number | null;
  va_name?: string | null;
  cv_url?: string | null;
  cover_url?: string | null;
  truthful?: boolean;
}

export interface OutreachSummary {
  step: OutreachStep;
  sent_count: number;
  contact_name?: string | null;
  contact_title?: string | null;
  company_hook?: string | null;
}

export interface ThreadMessage {
  id: string;
  direction: "outbound" | "inbound";
  from: string;
  to: string;
  subject?: string | null;
  body: string;
  sent_at: string;
}

export interface JobDetail {
  job: JobOut & { jd_text?: string | null; description?: string | null };
  generated_cv: GeneratedCv | null;
  cover_letter: CoverLetter | null;
  application: ApplicationSummary | null;
  outreach: OutreachSummary | null;
  thread: ThreadMessage[];
}

export interface AuditEvent {
  id: string;
  type: string;
  message: string;
  actor?: string | null;
  created_at: string;
}

/* ----------------------------------------------------------------------------
 * Onboarding / Profiles
 * ------------------------------------------------------------------------- */

export interface RoleCv {
  track: Track;
  filename: string;
  parsed: boolean;
  uploaded_at?: string;
}

export interface MasterProfile {
  track: Track;
  confirmed: boolean;
  headline?: string | null;
  summary?: string | null;
  skills: string[];
  target_roles?: string[];
  role_cv?: RoleCv | null;
  /** a CV LaTeX template is on file for this track */
  latex_cv?: boolean;
  /** a cover-letter LaTeX template is on file for this track */
  latex_cover?: boolean;
  /** structured, user-verified knowledge not on the CV (category -> terms) */
  verified_extras?: Record<string, string[]>;
  /** per-track skills to emphasize */
  preferred_skills?: string[];
  /** freeform per-track career preferences */
  career_preferences?: Record<string, unknown>;
  /** links (linkedin/github/portfolio) */
  links?: Record<string, string>;
  preferred_locations?: string[];
  preferred_job_types?: string[];
  salary_expectation?: Record<string, unknown>;
}

/* ---- Guided onboarding (R2) ---- */
export interface OnboardingStep {
  key: string;
  label: string;
  done: boolean;
  href: string;
}
export interface OnboardingStatus {
  tracks: {
    track: Track;
    has_cv: boolean;
    parsed: boolean;
    confirmed: boolean;
    has_target_roles: boolean;
  }[];
  steps: OnboardingStep[];
  next_action: OnboardingStep | null;
  complete: boolean;
}

export interface CoverLetterTemplate {
  body: string | null;
  filename?: string | null;
  name?: string | null;
}

/* ----------------------------------------------------------------------------
 * LaTeX templates / regeneration
 * ------------------------------------------------------------------------- */

/* ----------------------------------------------------------------------------
 * Tracks (first-class career tracks with readiness)
 * ------------------------------------------------------------------------- */

/* ----------------------------------------------------------------------------
 * AI Integrations (provider configuration)
 * ------------------------------------------------------------------------- */

export interface TemplateField {
  id: string;
  label: string;
  type: string; // password | url | text | …
  required: boolean;
  placeholder?: string;
  help?: string;
}

/** A built-in provider preset + its dynamic config-field schema. */
export interface IntegrationTemplate {
  id: string;
  name: string;
  provider: string;
  icon: string;
  description: string;
  fields: TemplateField[];
  default_model: string;
  discovery: boolean;
}

/** A user's configured AI provider connection. */
export interface Integration {
  id: string;
  name: string;
  provider: string;
  template?: string | null;
  base_url?: string | null;
  model?: string | null;
  masked_key?: string | null;
  has_key: boolean;
  models: string[];
  capabilities: Record<string, unknown>;
  status: string; // unknown | configured | invalid | unreachable | offline | rate_limited
  is_default: boolean;
  last_validated_at?: string | null;
}

export type TrackStatus = "setup_required" | "ready" | "archived";

/** A single onboarding/setup milestone from the readiness service. */
export interface ReadinessStep {
  id: string;
  label: string;
  completed: boolean;
  action: { label: string; route: string };
}

/** Centralized onboarding/setup readiness (GET /api/user/readiness). */
export interface UserReadiness {
  progress: number;
  complete: boolean;
  steps: ReadinessStep[];
  next_action: ReadinessStep | null;
  api_key_validated: boolean;
  tracks: {
    id: string | null;
    slug: string;
    name: string;
    status: TrackStatus;
    resume: boolean;
    cover_letter: boolean;
  }[];
}

/** A first-class career track. Incomplete until it has a resume (CV). */
export interface CareerTrack {
  id: string;
  slug: string;
  name: string;
  status: TrackStatus;
  resume: boolean;
  cover_letter: boolean;
  confirmed: boolean;
  target_roles: string[];
}

export type LatexKind = "cv" | "cover";

/** A per-track LaTeX skeleton the regeneration engine renders tailored content into. */
export interface LatexTemplate {
  track: Track;
  kind: LatexKind;
  filename?: string | null;
  has_source: boolean;
  source?: string | null;
  /** ATS format gate from a trial compile at save (status: pass | fail | unevaluated). */
  gate?: {
    status: "pass" | "fail" | "unevaluated";
    reasons?: string[];
    flags?: Record<string, boolean>;
  } | null;
}

/** ATS recommendations that drive a regeneration (subset of AtsCheckResult). */
export interface RegenerateAtsRecs {
  missing_critical?: string[];
  gaps?: string[];
  recommendations?: string[];
}

export interface RegenerateRequest {
  job_id?: string | null;
  track?: Track | null;
  jd_text?: string | null;
  role_title?: string | null;
  ats?: RegenerateAtsRecs;
  priority_techs?: string[];
}

/** Draft LaTeX produced by /api/latex/regenerate (not yet bound to a job). */
export interface RegenerateResult {
  cv_latex: string;
  cover_latex: string;
  cv_compiled: boolean;
  cover_compiled: boolean;
  cv_fell_back?: string | null;
  cover_fell_back?: string | null;
  cv_stderr?: string | null;
  cover_stderr?: string | null;
}

/** Thrown shape when /api/latex/preview cannot compile the LaTeX (HTTP 422). */
export interface LatexPreviewError {
  error: "compile_failed";
  stderr: string;
}

/* ----------------------------------------------------------------------------
 * User settings — per-user LLM provider keys (R1 BYO-key)
 * ------------------------------------------------------------------------- */

export type LlmKeyStatus = "configured" | "invalid" | "unreachable" | "unknown";

export interface LlmKey {
  provider: string; // anthropic | openai | google
  label?: string | null;
  masked_key?: string | null;
  has_key: boolean;
  base_url?: string | null;
  model?: string | null;
  is_active: boolean;
  is_preferred: boolean;
  status: LlmKeyStatus;
  last_validated_at?: string | null;
}

export interface LlmKeyInput {
  provider: string;
  api_key?: string;
  base_url?: string;
  model?: string;
  label?: string;
}

/* ----------------------------------------------------------------------------
 * Manual chatbot
 * ------------------------------------------------------------------------- */

export type PromptKind = "skill" | "reframe" | "detail";

export interface ChatPromptOption {
  id: string;
  label: string;
}

export interface ChatPrompt {
  id: string;
  question: string;
  options: ChatPromptOption[];
  kind: PromptKind;
  /** allow multiple selections */
  multi?: boolean;
  /** Options the user already confirmed — lets a reloaded session restore its answers. */
  selected?: string[];
  /** Free text the user added alongside the selection. */
  detail?: string | null;
  /** Whether this prompt has been confirmed. */
  resolved?: boolean;
}

export interface ChatSession {
  session_id: string;
  state?: string;
  /** The JD this session was started from — lets a resumed session refill its input. */
  jd_text?: string | null;
  company?: string | null;
  role_title?: string | null;
  track?: Track | null;
  /** How the backend CV was chosen for this JD */
  track_match?: {
    track: Track;
    method: string;
    reason: string;
  } | null;
  matched_cv: {
    track: Track;
    filename?: string | null;
  } | null;
  ats: {
    score: number;
    breakdown: AtsBreakdown;
  } | null;
  /** skills the VA has confirmed-true (from prompts or added manually) */
  confirmed_facts?: string[];
  prompts: ChatPrompt[];
  job_id?: string | null;
  answered_prompt_ids?: string[];
}

/** Correct the auto-extracted fields; changing `track` re-runs the analysis. */
export interface ChatSessionPatch {
  company?: string;
  role_title?: string;
  track?: Track;
}

export interface ChatAnswerRequest {
  prompt_id: string;
  selected: string[];
  detail?: string;
}

export interface ChatGenerateResult {
  job_id: string;
}

/** Response from POST /api/jobs/{id}/generate. status "rejected" (with no
 *  generated_cv_id) means the job scored below the relevance bar — retry with force. */
export interface GenerateResponse {
  job_id: string;
  status: string;
  generated_cv_id?: string | null;
  pdf_url?: string | null;
}

/** Result of the VA's Apply action on a job. */
export interface ApplyResult {
  application_id: string;
  apply_url?: string | null;
  cv_url?: string | null;
  cover_url?: string | null;
}

/* ----------------------------------------------------------------------------
 * VA queue
 * ------------------------------------------------------------------------- */

export type VaItemKind = "submit" | "outreach_review" | "reply";

export interface VaQueueItem {
  id: string;
  kind: VaItemKind;
  job_id: string;
  company: string;
  role: string;
  hunter_name: string;
  track: Track;
  preview?: string | null;
  created_at: string;
}

/* ----------------------------------------------------------------------------
 * Domains / Admin
 * ------------------------------------------------------------------------- */

export interface DomainHealth {
  id: string;
  domain: string;
  hunter_name: string;
  track: Track;
  warmup_stage: WarmupStage;
  bounce_rate: number;
  spam_rate: number;
  paused: boolean;
  daily_cap: number;
  sent_today: number;
}

export interface HunterQuota {
  hunter_id: string;
  hunter_name: string;
  weekly_cap: number;
  sent_this_week: number;
}

export interface QuotaResponse {
  hunters: HunterQuota[];
}

export interface DomainsResponse {
  domains: DomainHealth[];
}
