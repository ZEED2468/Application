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

/** application.status — the tracker status surfaced in the UI */
export type TrackerStatus =
  | "applied"
  | "interviewed"
  | "rejected"
  | "no_response"
  | "accepted";

export const TRACKER_STATUSES: TrackerStatus[] = [
  "applied",
  "interviewed",
  "rejected",
  "no_response",
  "accepted",
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
}

export interface LoginRequest {
  email: string;
  password: string;
}

/* --- Invite-gated signup --- */

export type InviteKind = "hunter" | "va";
export type InviteStatus = "pending" | "accepted" | "revoked";

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  key: string;
}

export interface HunterInviteRequest {
  email: string;
}

export interface VaInviteRequest {
  email: string;
  va_name: string;
  whatsapp: string;
  track?: Track | null;
}

export interface InviteOut {
  id: string;
  email: string;
  kind: InviteKind;
  status: InviteStatus;
  track?: Track | null;
  va_name?: string | null;
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
  format_flags: string[];
  /** optional sub-scores 0..100 keyed by category */
  sections?: Record<string, number>;
}

export interface GeneratedCv {
  pdf_url: string | null;
  ats_score: number | null;
  ats_breakdown: AtsBreakdown | null;
}

export interface CoverLetter {
  pdf_url: string | null;
}

/* ----------------------------------------------------------------------------
 * Jobs / Applications
 * ------------------------------------------------------------------------- */

export interface JobOut {
  id: string;
  company: string;
  role: string;
  track: Track;
  origin: Origin;
  status: JobStatus;
  ats_score: number | null;
  /** application id, present once an application object exists */
  application_id: string | null;
  application_status: TrackerStatus | null;
  location?: string | null;
  url?: string | null;
  created_at?: string;
}

export interface ApplicationSummary {
  id: string;
  status: TrackerStatus;
  submitted_at?: string | null;
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
  role_cv?: RoleCv | null;
}

export interface CoverLetterTemplate {
  body: string;
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
}

export interface ChatSession {
  session_id: string;
  matched_cv: {
    track: Track;
    filename?: string | null;
  } | null;
  ats: {
    score: number;
    breakdown: AtsBreakdown;
  } | null;
  prompts: ChatPrompt[];
  answered_prompt_ids?: string[];
}

export interface ChatAnswerRequest {
  prompt_id: string;
  selected: string[];
  detail?: string;
}

export interface ChatGenerateResult {
  job_id: string;
  application_id: string;
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
