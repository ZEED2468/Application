import { redirect } from "next/navigation";

/** Legacy route — onboarding was renamed to Profile. */
export default function OnboardingRedirect() {
  redirect("/profile");
}
