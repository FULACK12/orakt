import PilotDashboard from '../../PilotDashboard';
import ClientErrorBoundary from '../../ClientErrorBoundary';
export const metadata={title:'ORAKT · Intelligence Market'};
export default function Page(){return <ClientErrorBoundary><PilotDashboard initialTab="intelligence"/></ClientErrorBoundary>;}
