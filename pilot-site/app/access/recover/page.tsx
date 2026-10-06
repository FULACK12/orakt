import AccessScreen, {type AccessPageProps} from "../AccessScreen";
export const dynamic="force-dynamic";
export const metadata={title:"找回密码 · ORAKT"};
export default function Page(props:AccessPageProps){return <AccessScreen {...props} method="recover"/>;}
