import type { Metadata } from "next";
import ClientErrorBoundary from "../../ClientErrorBoundary";
import PilotDashboard from "../../PilotDashboard";

export const metadata: Metadata = {
  title: "ORAKT Filings · Source audit",
  description: "Review public filings and their use in published research.",
};

export default function FilingsPage() {
  return (
    <ClientErrorBoundary>
      <PilotDashboard initialTab="sec" />
    </ClientErrorBoundary>
  );
}
