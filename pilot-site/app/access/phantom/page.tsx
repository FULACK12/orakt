import AccessScreen, {type AccessPageProps} from "../AccessScreen";
export const dynamic="force-dynamic";
export const metadata={title:"Phantom 登录 · ORAKT"};
export default function Page(props:AccessPageProps){return <AccessScreen {...props} method="phantom"/>;}
