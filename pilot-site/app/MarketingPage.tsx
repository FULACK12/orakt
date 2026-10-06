import OraktLanding from "./OraktLanding";
import type {MarketingPageKey} from "./marketing-pages";
import snapshot from "../snapshot/snapshot-manifest.json";
export default function MarketingPage({page}:{page:MarketingPageKey}){
 return <OraktLanding page={page} metrics={{
  events:snapshot.localTotals.geolocatedEvents,
  articles:snapshot.localTotals.substantiveArticles,
  reports:snapshot.remoteSnapshot.localResearchReports,
  companies:snapshot.remoteSnapshot.activeChinaSectorLeaders+snapshot.remoteSnapshot.activeUsSectorLeaders,
  generatedAt:snapshot.generatedAt,
 }}/>;
}
