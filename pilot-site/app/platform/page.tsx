import type { Metadata } from "next";
import ClientErrorBoundary from "../ClientErrorBoundary";
import PilotDashboard from "../PilotDashboard";

export const metadata: Metadata = {
  title: "ORAKT World · Event map",
  description: "Explore published event, conflict, economic and supply-chain layers.",
};

export default function PlatformPage() {
  return (
    <ClientErrorBoundary>
      <PilotDashboard initialTab="map" />
    </ClientErrorBoundary>
  );
}
