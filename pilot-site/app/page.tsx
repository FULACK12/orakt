import type { Metadata } from "next";
import OraktLanding from "./OraktLanding";
import snapshotManifest from "../snapshot/snapshot-manifest.json";

export const metadata: Metadata = {
  title: "ORAKT · 观因 by INSOLVE TECH | See what moves the world",
  description:
    "INSOLVE TECH 打造的全球因果与市场情报系统：把世界事件、Alpha 因子、公司与市场数据连接成可审计、可回测的证据网络。",
};

export default function Home() {
  return (
    <OraktLanding
      metrics={{
        events: snapshotManifest.localTotals.geolocatedEvents,
        articles: snapshotManifest.localTotals.substantiveArticles,
        reports: snapshotManifest.remoteSnapshot.localResearchReports,
        companies:
          snapshotManifest.remoteSnapshot.activeChinaSectorLeaders +
          snapshotManifest.remoteSnapshot.activeUsSectorLeaders,
        generatedAt: snapshotManifest.generatedAt,
      }}
    />
  );
}
