/* Use case: Opens a private dashboard inside an approved host frame.
What it does: Passes validated host metadata to an isolated in-memory embed client. */

import { headers } from "next/headers";
import { EmbeddedBoard } from "./embedded-board";

export const dynamic = "force-dynamic";

export default async function EmbedPage({ params }: { params: Promise<{ grantId: string }> }) {
  const { grantId } = await params;
  const hostOrigin = (await headers()).get("x-execplus-embed-host") ?? "";
  return <EmbeddedBoard grantId={grantId} hostOrigin={hostOrigin} />;
}
