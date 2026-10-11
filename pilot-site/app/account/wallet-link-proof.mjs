// Never signs a transaction: only the visible, account-bound ownership message.
export async function signWalletLink(provider,challenge,expected,origin,now=Date.now()){
 if(!provider?.isPhantom||provider.publicKey?.toString()!==expected.address)throw Error('account_changed');
 if(!['link','unlink'].includes(expected.action)||challenge.address!==expected.address||challenge.action!==expected.action||challenge.memberId!==expected.memberId||challenge.origin!==origin||!Number.isSafeInteger(challenge.expiresAt)||challenge.expiresAt<=now||challenge.expiresAt>now+300000||typeof challenge.message!=='string'||challenge.message.length>2000||!challenge.message.startsWith(`ORAKT wallet ownership proof\n\nAction: ${expected.action.toUpperCase()} wallet to account\nAccount: ${expected.memberId}\nWallet: ${expected.address}\nOrigin: ${origin}\n`)||!challenge.message.includes(`\nNonce: ${challenge.nonce}\n`))throw Error('invalid_challenge');
 const signed=await provider.signMessage(new TextEncoder().encode(challenge.message),'utf8');
 if(signed.publicKey?.toString()!==expected.address||provider.publicKey?.toString()!==expected.address||!(signed.signature instanceof Uint8Array)||signed.signature.length!==64)throw Error('account_changed');
 return btoa(String.fromCharCode(...signed.signature)).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
}
