import { redirect } from "next/navigation";

/** The résumé editor now lives inline in the job workspace. Keep this route as a
 *  redirect so existing links + the ATS "Regenerate CV" handoff open the editor
 *  (?edit=1 puts the workspace's résumé hero straight into edit mode). */
export default async function JobBuilderRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/jobs/${id}?edit=1`);
}
