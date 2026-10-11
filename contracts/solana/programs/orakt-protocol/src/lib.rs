#![allow(unexpected_cfgs)]
//! Experimental source only. No live deployment, security audit or automatic trading.
use anchor_lang::prelude::*;
use anchor_lang::solana_program::pubkey;
use anchor_lang::solana_program::hash::hashv;
use anchor_spl::token::{self, Mint, Token, TokenAccount, TransferChecked};
mod calendar;

// Compilation fixture, NOT a live address; replace with operator-owned program ID.
declare_id!("BaAX5nB9yxMh5K1tdEserFDq7MMcisVGVNshrVNLqDyn");
pub const USDC: Pubkey = pubkey!("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v");
pub const USDT: Pubkey = pubkey!("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB");
pub const MERCHANT: Pubkey = pubkey!("9WLRmvq8a86A6q9JwrzKqyVoUXDJoXC14SKNix3xZ79Z");
pub const SIGNAL_UNITS:u64=19_000_000;
pub const RESEARCH_UNITS:u64=79_000_000;
fn nonzero(hash:&[u8;32])->bool {hash.iter().any(|b|*b!=0)}
fn price(plan:u8,months:u8)->Option<u64>{if !(1..=12).contains(&months){return None;}match plan{1=>SIGNAL_UNITS.checked_mul(months as u64),2=>RESEARCH_UNITS.checked_mul(months as u64),_=>None}}
fn roles_valid(roles:u8)->bool{roles & !3 == 0}
// Domain-separated sorted-pair Merkle proof, version 1. Proves inclusion, not truth.
fn evidence_root(leaf:&[u8;32],proof:&[[u8;32]])->Option<[u8;32]>{
    if !nonzero(leaf)||proof.len()>16{return None;}
    let mut node=hashv(&[b"orakt-evidence-leaf-v1",leaf]).to_bytes();
    for sibling in proof{let (left,right)=if node<=*sibling{(&node,sibling)}else{(sibling,&node)};node=hashv(&[b"orakt-evidence-node-v1",left,right]).to_bytes();}
    Some(node)
}

#[program]
pub mod orakt_protocol {
    use super::*;
    /// Permissionless inclusion check; no membership or truth attestation.
    pub fn verify_evidence(ctx:Context<VerifyEvidence>,leaf_hash:[u8;32],proof:Vec<[u8;32]>)->Result<()> {
        require!(evidence_root(&leaf_hash,&proof)==Some(ctx.accounts.record.evidence_root),ProtocolError::InvalidEvidenceProof);
        emit!(EvidenceVerified{record:ctx.accounts.record.key(),leaf_hash,evidence_root:ctx.accounts.record.evidence_root});Ok(())
    }
    pub fn initialize(ctx:Context<Initialize>)->Result<()> {
        ctx.accounts.config.set_inner(Config{authority:ctx.accounts.authority.key(),paused:false,bump:ctx.bumps.config});
        Ok(())
    }
    pub fn set_paused(ctx:Context<Admin>,paused:bool)->Result<()> {ctx.accounts.config.paused=paused;Ok(())}
    /// Bit 1: publish; bit 2: attest. Zero revokes future writes, never past records.
    pub fn set_roles(ctx:Context<SetRoles>,roles:u8)->Result<()> {
        require!(roles_valid(roles),ProtocolError::InvalidInput);
        ctx.accounts.permit.set_inner(Permit{config:ctx.accounts.config.key(),wallet:ctx.accounts.wallet.key(),roles,bump:ctx.bumps.permit});
        emit!(RoleChanged{config:ctx.accounts.config.key(),wallet:ctx.accounts.wallet.key(),roles});Ok(())
    }
    /// Kinds: report, intelligence, evidence-chain, factor, portfolio, AI draft.
    pub fn open_series(ctx:Context<OpenSeries>,item:[u8;32],kind:u8)->Result<()> {
        require!(nonzero(&item)&&kind<=5,ProtocolError::InvalidInput);
        ctx.accounts.series.set_inner(Series{config:ctx.accounts.config.key(),author:ctx.accounts.author.key(),item,kind,next_version:1,last_hash:[0;32],bump:ctx.bumps.series});Ok(())
    }
    pub fn publish_version(ctx:Context<PublishVersion>,version:u32,content_hash:[u8;32],evidence_root:[u8;32],expected_parent:[u8;32])->Result<()> {
        let series=&mut ctx.accounts.series;
        require!(nonzero(&content_hash)&&nonzero(&evidence_root),ProtocolError::InvalidInput);
        require!(version==series.next_version&&expected_parent==series.last_hash,ProtocolError::VersionConflict);
        let now=Clock::get()?.unix_timestamp;
        ctx.accounts.record.set_inner(Record{config:ctx.accounts.config.key(),series:series.key(),author:ctx.accounts.author.key(),version,kind:series.kind,content_hash,evidence_root,parent_hash:series.last_hash,recorded_at:now,bump:ctx.bumps.record});
        series.next_version=version.checked_add(1).ok_or(ProtocolError::Overflow)?;series.last_hash=content_hash;
        emit!(VersionPublished{record:ctx.accounts.record.key(),author:ctx.accounts.author.key(),content_hash,version,recorded_at:now});Ok(())
    }
    /// Immutable reviewer statement, never a proof of truth or guaranteed return.
    pub fn attest(ctx:Context<Attest>,verdict:u8,reason_hash:[u8;32])->Result<()> {
        require!(verdict<=2&&nonzero(&reason_hash),ProtocolError::InvalidInput);
        require_keys_neq!(ctx.accounts.reviewer.key(),ctx.accounts.record.author,ProtocolError::SelfReview);
        ctx.accounts.attestation.set_inner(Attestation{record:ctx.accounts.record.key(),reviewer:ctx.accounts.reviewer.key(),verdict,reason_hash,recorded_at:Clock::get()?.unix_timestamp,bump:ctx.bumps.attestation});Ok(())
    }
    /// Retraction adds an immutable record; it cannot erase published bytes/hashes.
    pub fn retract(ctx:Context<Retract>,reason_hash:[u8;32])->Result<()> {
        require!(nonzero(&reason_hash),ProtocolError::InvalidInput);
        ctx.accounts.retraction.set_inner(Retraction{record:ctx.accounts.record.key(),author:ctx.accounts.author.key(),reason_hash,recorded_at:Clock::get()?.unix_timestamp,bump:ctx.bumps.retraction});Ok(())
    }
    /// Atomic SPL transfer + immutable receipt. No custody, auto-renewal or delegate.
    pub fn purchase(ctx:Context<Purchase>,plan:u8,invoice:[u8;32],months:u8,expected_amount:u64,deadline:i64)->Result<()> {
        let now=Clock::get()?.unix_timestamp;
        require!(nonzero(&invoice)&&deadline>=now&&deadline<=now.checked_add(600).ok_or(ProtocolError::Overflow)?,ProtocolError::ExpiredQuote);
        let amount=price(plan,months).ok_or(ProtocolError::InvalidInput)?;
        require!(amount==expected_amount,ProtocolError::PriceMismatch);
        let sub=&mut ctx.accounts.subscription;
        if sub.wallet!=Pubkey::default(){require_keys_eq!(sub.wallet,ctx.accounts.buyer.key(),ProtocolError::Unauthorized);require_keys_eq!(sub.config,ctx.accounts.config.key(),ProtocolError::Unauthorized);require!(sub.plan==plan,ProtocolError::InvalidInput);}
        let until=calendar::extend(sub.expires_at,now,months).ok_or(ProtocolError::Overflow)?;
        token::transfer_checked(CpiContext::new(ctx.accounts.token_program.to_account_info(),TransferChecked{from:ctx.accounts.source.to_account_info(),mint:ctx.accounts.mint.to_account_info(),to:ctx.accounts.treasury.to_account_info(),authority:ctx.accounts.buyer.to_account_info()}),amount,6)?;
        sub.set_inner(Subscription{config:ctx.accounts.config.key(),wallet:ctx.accounts.buyer.key(),plan,expires_at:until,bump:ctx.bumps.subscription});
        ctx.accounts.receipt.set_inner(Receipt{config:ctx.accounts.config.key(),buyer:ctx.accounts.buyer.key(),invoice,mint:ctx.accounts.mint.key(),amount,plan,months,paid_at:now,expires_at:until,bump:ctx.bumps.receipt});
        emit!(SubscriptionPurchased{buyer:ctx.accounts.buyer.key(),receipt:ctx.accounts.receipt.key(),plan,amount,expires_at:until});Ok(())
    }
    /// Optional sponsored proof of an ACCOUNT trial, not an unrestricted wallet faucet.
    /// Authority must attest a salted account commitment; wallet must also consent.
    /// Existing free web trial does not require this transaction or wallet ownership.
    pub fn issue_trial(ctx:Context<IssueTrial>,subject:[u8;32])->Result<()> {
        require!(nonzero(&subject),ProtocolError::InvalidInput);
        let now=Clock::get()?.unix_timestamp;
        let until=now.checked_add(86_400).ok_or(ProtocolError::Overflow)?;
        ctx.accounts.trial.set_inner(Trial{config:ctx.accounts.config.key(),subject,wallet:ctx.accounts.wallet.key(),claimed_at:now,expires_at:until,bump:ctx.bumps.trial});Ok(())
    }
}

#[derive(Accounts)]
pub struct VerifyEvidence<'info>{
    #[account(seeds=[b"record",record.series.as_ref(),record.version.to_le_bytes().as_ref()],bump=record.bump)]pub record:Account<'info,Record>,
}
#[derive(Accounts)]
pub struct Initialize<'info>{
    #[account(mut)] pub authority:Signer<'info>,
    #[account(init,payer=authority,space=8+Config::INIT_SPACE,seeds=[b"config",authority.key().as_ref()],bump)] pub config:Account<'info,Config>,
    pub system_program:Program<'info,System>,
}
#[derive(Accounts)]
pub struct Admin<'info>{
    pub authority:Signer<'info>,
    #[account(mut,has_one=authority,seeds=[b"config",authority.key().as_ref()],bump=config.bump)]pub config:Account<'info,Config>,
}
#[derive(Accounts)]
pub struct SetRoles<'info>{
    #[account(mut)]pub authority:Signer<'info>,
    #[account(has_one=authority,seeds=[b"config",authority.key().as_ref()],bump=config.bump)]pub config:Account<'info,Config>,
    /// CHECK: Public key identifying the permit recipient; no account data is read.
    pub wallet:UncheckedAccount<'info>,
    #[account(init_if_needed,payer=authority,space=8+Permit::INIT_SPACE,seeds=[b"permit",config.key().as_ref(),wallet.key().as_ref()],bump)]pub permit:Account<'info,Permit>,
    pub system_program:Program<'info,System>,
}
#[derive(Accounts)]
#[instruction(item:[u8;32])]
pub struct OpenSeries<'info>{
    #[account(mut)]pub author:Signer<'info>,
    #[account(seeds=[b"config",config.authority.as_ref()],bump=config.bump,constraint=!config.paused @ ProtocolError::Paused)]pub config:Account<'info,Config>,
    #[account(seeds=[b"permit",config.key().as_ref(),author.key().as_ref()],bump=permit.bump,constraint=permit.roles&1==1 @ ProtocolError::Unauthorized)]pub permit:Account<'info,Permit>,
    #[account(init,payer=author,space=8+Series::INIT_SPACE,seeds=[b"series",config.key().as_ref(),author.key().as_ref(),item.as_ref()],bump)]pub series:Account<'info,Series>,
    pub system_program:Program<'info,System>,
}
#[derive(Accounts)]
#[instruction(version:u32)]
pub struct PublishVersion<'info>{
    #[account(mut)]pub author:Signer<'info>,
    #[account(seeds=[b"config",config.authority.as_ref()],bump=config.bump,constraint=!config.paused @ ProtocolError::Paused)]pub config:Account<'info,Config>,
    #[account(seeds=[b"permit",config.key().as_ref(),author.key().as_ref()],bump=permit.bump,constraint=permit.roles&1==1 @ ProtocolError::Unauthorized)]pub permit:Account<'info,Permit>,
    #[account(mut,has_one=config,has_one=author,seeds=[b"series",config.key().as_ref(),author.key().as_ref(),series.item.as_ref()],bump=series.bump)]pub series:Account<'info,Series>,
    #[account(init,payer=author,space=8+Record::INIT_SPACE,seeds=[b"record",series.key().as_ref(),version.to_le_bytes().as_ref()],bump)]pub record:Account<'info,Record>,
    pub system_program:Program<'info,System>,
}
#[derive(Accounts)]
pub struct Attest<'info>{
    #[account(mut)]pub reviewer:Signer<'info>,
    #[account(seeds=[b"config",config.authority.as_ref()],bump=config.bump,constraint=!config.paused @ ProtocolError::Paused)]pub config:Account<'info,Config>,
    #[account(seeds=[b"permit",config.key().as_ref(),reviewer.key().as_ref()],bump=permit.bump,constraint=permit.roles&2==2 @ ProtocolError::Unauthorized)]pub permit:Account<'info,Permit>,
    #[account(has_one=config,seeds=[b"record",record.series.as_ref(),record.version.to_le_bytes().as_ref()],bump=record.bump)]pub record:Account<'info,Record>,
    #[account(init,payer=reviewer,space=8+Attestation::INIT_SPACE,seeds=[b"review",record.key().as_ref(),reviewer.key().as_ref()],bump)]pub attestation:Account<'info,Attestation>,
    pub system_program:Program<'info,System>,
}
#[derive(Accounts)]
pub struct Retract<'info>{
    #[account(mut)]pub author:Signer<'info>,
    // Retractions remain possible during an operational pause.
    #[account(has_one=author,seeds=[b"record",record.series.as_ref(),record.version.to_le_bytes().as_ref()],bump=record.bump)]pub record:Account<'info,Record>,
    #[account(init,payer=author,space=8+Retraction::INIT_SPACE,seeds=[b"retraction",record.key().as_ref()],bump)]pub retraction:Account<'info,Retraction>,
    pub system_program:Program<'info,System>,
}
#[derive(Accounts)]
#[instruction(plan:u8,invoice:[u8;32])]
pub struct Purchase<'info>{
    #[account(mut,constraint=buyer.key()!=MERCHANT @ ProtocolError::InvalidInput)]pub buyer:Signer<'info>,
    #[account(seeds=[b"config",config.authority.as_ref()],bump=config.bump,constraint=!config.paused @ ProtocolError::Paused)]pub config:Account<'info,Config>,
    #[account(constraint=mint.key()==USDC||mint.key()==USDT @ ProtocolError::InvalidMint,constraint=mint.decimals==6 @ ProtocolError::InvalidMint)]pub mint:Account<'info,Mint>,
    #[account(mut,token::mint=mint,token::authority=buyer)]pub source:Account<'info,TokenAccount>,
    #[account(mut,token::mint=mint,constraint=treasury.owner==MERCHANT @ ProtocolError::Unauthorized,constraint=source.key()!=treasury.key() @ ProtocolError::InvalidInput)]pub treasury:Account<'info,TokenAccount>,
    #[account(init_if_needed,payer=buyer,space=8+Subscription::INIT_SPACE,seeds=[b"subscription",config.key().as_ref(),buyer.key().as_ref(),&[plan]],bump)]pub subscription:Account<'info,Subscription>,
    #[account(init,payer=buyer,space=8+Receipt::INIT_SPACE,seeds=[b"receipt",config.key().as_ref(),buyer.key().as_ref(),invoice.as_ref()],bump)]pub receipt:Account<'info,Receipt>,
    pub token_program:Program<'info,Token>,
    pub system_program:Program<'info,System>,
}
#[derive(Accounts)]
#[instruction(subject:[u8;32])]
pub struct IssueTrial<'info>{
    #[account(mut)]pub authority:Signer<'info>,
    pub wallet:Signer<'info>,
    #[account(has_one=authority,seeds=[b"config",authority.key().as_ref()],bump=config.bump,constraint=!config.paused @ ProtocolError::Paused)]pub config:Account<'info,Config>,
    #[account(init,payer=authority,space=8+Trial::INIT_SPACE,seeds=[b"trial",config.key().as_ref(),subject.as_ref()],bump)]pub trial:Account<'info,Trial>,
    pub system_program:Program<'info,System>,
}

#[account]#[derive(InitSpace)]pub struct Config{pub authority:Pubkey,pub paused:bool,pub bump:u8}
#[account]#[derive(InitSpace)]pub struct Permit{pub config:Pubkey,pub wallet:Pubkey,pub roles:u8,pub bump:u8}
#[account]#[derive(InitSpace)]pub struct Series{pub config:Pubkey,pub author:Pubkey,pub item:[u8;32],pub kind:u8,pub next_version:u32,pub last_hash:[u8;32],pub bump:u8}
#[account]#[derive(InitSpace)]pub struct Record{pub config:Pubkey,pub series:Pubkey,pub author:Pubkey,pub version:u32,pub kind:u8,pub content_hash:[u8;32],pub evidence_root:[u8;32],pub parent_hash:[u8;32],pub recorded_at:i64,pub bump:u8}
#[account]#[derive(InitSpace)]pub struct Attestation{pub record:Pubkey,pub reviewer:Pubkey,pub verdict:u8,pub reason_hash:[u8;32],pub recorded_at:i64,pub bump:u8}
#[account]#[derive(InitSpace)]pub struct Retraction{pub record:Pubkey,pub author:Pubkey,pub reason_hash:[u8;32],pub recorded_at:i64,pub bump:u8}
#[account]#[derive(InitSpace)]pub struct Subscription{pub config:Pubkey,pub wallet:Pubkey,pub plan:u8,pub expires_at:i64,pub bump:u8}
#[account]#[derive(InitSpace)]pub struct Receipt{pub config:Pubkey,pub buyer:Pubkey,pub invoice:[u8;32],pub mint:Pubkey,pub amount:u64,pub plan:u8,pub months:u8,pub paid_at:i64,pub expires_at:i64,pub bump:u8}
#[account]#[derive(InitSpace)]pub struct Trial{pub config:Pubkey,pub subject:[u8;32],pub wallet:Pubkey,pub claimed_at:i64,pub expires_at:i64,pub bump:u8}
#[event]pub struct EvidenceVerified{pub record:Pubkey,pub leaf_hash:[u8;32],pub evidence_root:[u8;32]}
#[event]pub struct RoleChanged{pub config:Pubkey,pub wallet:Pubkey,pub roles:u8}
#[event]pub struct VersionPublished{pub record:Pubkey,pub author:Pubkey,pub content_hash:[u8;32],pub version:u32,pub recorded_at:i64}
#[event]pub struct SubscriptionPurchased{pub buyer:Pubkey,pub receipt:Pubkey,pub plan:u8,pub amount:u64,pub expires_at:i64}
#[error_code]pub enum ProtocolError{
    #[msg("Invalid input")]InvalidInput,
    #[msg("Not authorized")]Unauthorized,
    #[msg("Writes paused")]Paused,
    #[msg("Version or parent mismatch")]VersionConflict,
    #[msg("Self-review not permitted")]SelfReview,
    #[msg("Arithmetic or time outside bounds")]Overflow,
    #[msg("Unsupported mint or decimals")]InvalidMint,
    #[msg("Quote expired or too far in future")]ExpiredQuote,
    #[msg("Amount differs from fixed plan price")]PriceMismatch,
    #[msg("Evidence inclusion proof does not match committed root")]InvalidEvidenceProof,
}
#[cfg(test)]mod tests{
    use super::*;
    #[test]fn fixed_prices(){assert_eq!(price(1,1),Some(19_000_000));assert_eq!(price(2,12),Some(948_000_000));}
    #[test]fn rejects_unknown_plan_and_term(){assert_eq!(price(0,1),None);assert_eq!(price(3,1),None);assert_eq!(price(2,0),None);assert_eq!(price(2,13),None);}
    #[test]fn only_publish_review_roles(){for n in 0..=3{assert!(roles_valid(n));}assert!(!roles_valid(4));assert!(!roles_valid(255));}
    #[test]fn commitments_not_blank(){assert!(!nonzero(&[0;32]));assert!(nonzero(&[1;32]));}
    #[test]fn evidence_domains_and_bounds(){let leaf=[1;32];assert_eq!(evidence_root(&leaf,&[]),Some(hashv(&[b"orakt-evidence-leaf-v1",&leaf]).to_bytes()));assert_eq!(evidence_root(&[0;32],&[]),None);assert_eq!(evidence_root(&leaf,&[[2;32];17]),None);assert_ne!(evidence_root(&leaf,&[[2;32]]),evidence_root(&leaf,&[[3;32]]));}
    #[test]fn record_space_covers_all_fields(){assert_eq!(Record::INIT_SPACE,206);assert_eq!(Trial::INIT_SPACE,113);}
}
