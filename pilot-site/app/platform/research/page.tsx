import type { Metadata } from "next";
import ClientErrorBoundary from "../../ClientErrorBoundary";
import PilotDashboard from "../../PilotDashboard";

export const metadata: Metadata = {
  title: "ORAKT Chains · Evidence reports",
  description: "Audit causal chains, evidence coverage and research conclusions.",
};

export default function ResearchPage() {
  return (
    <ClientErrorBoundary>
      <PilotDashboard initialTab="evidence" />
    </ClientErrorBoundary>
  );
}
