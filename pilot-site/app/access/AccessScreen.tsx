import AccessPortal, {type AccessMethod} from "./AccessPortal";
import {chatGPTSignInPath} from "../chatgpt-auth";
import {safeAccessReturnTo} from "./access-navigation.mjs";

export type AccessPageProps = {searchParams?: Promise<Record<string, string | string[] | undefined>>};

export default async function AccessScreen({searchParams, method}: AccessPageProps & {method?: AccessMethod}) {
  const query = await searchParams;
  const returnTo = safeAccessReturnTo(query?.return_to);
  return <AccessPortal method={method} returnTo={returnTo} chatHref={chatGPTSignInPath(returnTo)}/>;
}
