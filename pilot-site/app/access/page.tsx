import type {Metadata} from "next";
import AccessScreen, {type AccessPageProps} from "./AccessScreen";
export const dynamic="force-dynamic";
export const metadata:Metadata={title:"Access · ORAKT 观因",description:"使用 ChatGPT、Google、Phantom 或 ORAKT 账号登录。"};
export default function AccessPage(props:AccessPageProps){return <AccessScreen {...props}/>;}
