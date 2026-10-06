import ClientErrorBoundary from '../../ClientErrorBoundary';
import PilotDashboard from '../../PilotDashboard';
export default function Page(){return <ClientErrorBoundary><PilotDashboard initialTab="markets"/></ClientErrorBoundary>;}
