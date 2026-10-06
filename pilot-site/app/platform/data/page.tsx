import type { Metadata } from "next";
import ClientErrorBoundary from "../../ClientErrorBoundary";
import PilotDashboard from "../../PilotDashboard";

export const metadata: Metadata = {
  title: "ORAKT Lab · Data and validation",
  description: "Inspect dataset coverage, validation status and backtest boundaries.",
};

export default function DataPage() {
  return (
    <ClientErrorBoundary>
      <PilotDashboard initialTab="data" />
    </ClientErrorBoundary>
  );
}
