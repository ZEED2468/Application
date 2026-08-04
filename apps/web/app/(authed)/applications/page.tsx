import { redirect } from "next/navigation";

/** The Tracker is now the "Submitted" segment of the Jobs screen. Keep this route as
 *  a permanent redirect so existing links / bookmarks land on the right place. */
export default function ApplicationsRedirect() {
  redirect("/jobs?view=submitted");
}
