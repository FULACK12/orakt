import AccessScreen, {type AccessPageProps} from "../AccessScreen";
export const dynamic="force-dynamic";
export const metadata={title:"Google 登录 · ORAKT"};
export default function Page(props:AccessPageProps){return <AccessScreen {...props} method="google"/>;}
