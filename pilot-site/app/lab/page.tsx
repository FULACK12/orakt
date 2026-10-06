import MarketingPage from "../MarketingPage";
import {marketingPages} from "../marketing-pages";
const page=marketingPages.lab;
export const metadata={title:page.en+" · ORAKT",description:page.description};
export default function Page(){return <MarketingPage page="lab"/>;}
