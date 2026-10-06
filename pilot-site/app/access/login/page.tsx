import AccessScreen, {type AccessPageProps} from "../AccessScreen";
export const dynamic="force-dynamic";
export const metadata={title:"账号登录 · ORAKT"};
export default function Page(props:AccessPageProps){return <AccessScreen {...props} method="login"/>;}
