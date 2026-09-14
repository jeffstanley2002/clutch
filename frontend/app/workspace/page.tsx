import type { Metadata } from "next";
import { Workspace } from "@/components/workspace";
export const metadata: Metadata = { title: "Workspace · Clutch" };
export default function WorkspacePage() {
  return <Workspace />;
}
