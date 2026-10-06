import MarketingPage from "../MarketingPage";
import {marketingPages} from "../marketing-pages";
const page=marketingPages.company;
export const metadata={title:page.en+" · ORAKT",description:page.description};
export default function Page(){return <MarketingPage page="company"/>;}
