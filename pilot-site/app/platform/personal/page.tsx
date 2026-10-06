import PilotDashboard from '../../PilotDashboard';
import ClientErrorBoundary from '../../ClientErrorBoundary';
export default function Page(){return <ClientErrorBoundary><PilotDashboard initialTab="personal"/></ClientErrorBoundary>;}
