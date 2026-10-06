import type {Metadata} from "next";
import AccountCenter from "./AccountCenter";
export const dynamic="force-dynamic";
export const metadata:Metadata={title:"Account · ORAKT",description:"ORAKT 账号、已发布数据概览与安全退出。"};
export default function AccountPage(){return <AccountCenter/>;}
