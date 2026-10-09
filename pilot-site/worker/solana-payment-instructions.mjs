import {PublicKey,TransactionInstruction,SystemProgram} from '@solana/web3.js';
import {Buffer} from 'node:buffer';
// Narrow legacy SPL ABI: no approvals, delegates, swaps, Token-2022 or arbitrary programs.
// Matches @solana/spl-token 0.4.15 createAssociatedTokenAccountIdempotent and
// TransferChecked encodings. Native bigint-buffer is deliberately not a dependency.
export const TOKEN_PROGRAM_ID=new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA');
export const ASSOCIATED_TOKEN_PROGRAM_ID=new PublicKey('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL');
export function getAssociatedTokenAddressSync(mint,owner){return PublicKey.findProgramAddressSync([owner.toBuffer(),TOKEN_PROGRAM_ID.toBuffer(),mint.toBuffer()],ASSOCIATED_TOKEN_PROGRAM_ID)[0];}
const key=(pubkey,isSigner=false,isWritable=false)=>({pubkey,isSigner,isWritable});
export function createAssociatedTokenAccountIdempotentInstruction(payer,account,owner,mint){return new TransactionInstruction({programId:ASSOCIATED_TOKEN_PROGRAM_ID,keys:[key(payer,true,true),key(account,false,true),key(owner),key(mint),key(SystemProgram.programId),key(TOKEN_PROGRAM_ID)],data:Buffer.from([1])});}
export function createTransferCheckedInstruction(source,mint,destination,owner,amount,decimals){if(decimals!==6||amount<=0n||amount>0xffffffffffffffffn)throw Error('invalid_payment_amount');const data=Buffer.alloc(10);data[0]=12;data.writeBigUInt64LE(amount,1);data[9]=decimals;return new TransactionInstruction({programId:TOKEN_PROGRAM_ID,keys:[key(source,false,true),key(mint),key(destination,false,true),key(owner,true)],data});}
