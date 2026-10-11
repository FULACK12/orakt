import styles from './ProtocolSection.module.css';

const source='https://github.com/FULACK12/orakt/tree/main/contracts/solana';
const checks='https://github.com/FULACK12/orakt/actions/workflows/solana-contracts.yml';

export default function ProtocolSection({language}:{language:'zh'|'en'}){
  const t=(zh:string,en:string)=>language==='zh'?zh:en;
  const modules=[
    ['01','PROVENANCE',t('研究版本存证','Research provenance'),t('公司报告、新闻、证据链、因子、组合与 AI 草稿，共用不可覆盖的版本记录。','Company reports, news, evidence chains, factors, portfolios and AI drafts share an append-only version registry.'),'open_series · publish_version'],
    ['02','REVIEW',t('审核与更正历史','Review & correction'),t('发布者与审核者分权；禁止自审。撤回保留历史，更正生成新版本。','Separate publisher and reviewer roles. No self-review. Retractions preserve history; corrections create new versions.'),'attest · retract'],
    ['03','ACCESS',t('按月订阅收据','Monthly subscription receipts'),t('USDC / USDT 直接支付给收款方，同时记录期限。无资金托管，无自动扣款。','USDC / USDT payments go directly to the merchant with an atomic term receipt. No custody or automatic charging.'),'purchase'],
    ['04','TRIAL',t('24 小时体验凭证','24-hour trial proof'),t('可选的账号体验凭证，需要管理员与钱包双方签名；现有免费体验仍无需钱包。','Optional account-trial proof requires both operator and wallet signatures. The existing free trial remains wallet-free.'),'issue_trial'],
    ['05','CONTROL',t('发布权限与暂停','Publishing controls'),t('管理员授予或撤销发布、审核权限。暂停新写入不会删除已经留下的记录。','Administrators grant or revoke publishing and review roles. Pausing new writes cannot erase existing records.'),'set_roles · set_paused'],
    ['06','BOUNDARY',t('把判断留在链外','Judgment stays off-chain'),t('AI 推理、原文、行情、地图和事实核查不搬进合约。哈希证明记录一致，不证明结论正确。','AI inference, source text, prices, maps and fact checking stay off-chain. A hash proves consistency, not the truth of a conclusion.'),t('隐私 · 证据 · 人工复核','Privacy · evidence · human review')],
  ];
  return <section className={styles.section} id="protocol" aria-labelledby="protocol-title">
    <div className={styles.rule}><span>ORAKT PROTOCOL / SOLANA</span><span>{t('实验性合约源码 · 尚未部署','EXPERIMENTAL SOURCE · NOT DEPLOYED')}</span></div>
    <div className={styles.intro}><h2 id="protocol-title">{t('研究可以迭代。','Research evolves.')}<br/><em>{t('记录不该被改写。','Its history should not.')}</em></h2><div><p>{t('把需要信任的动作，变成可以检查的规则。从一份报告的版本，到一次审核、一张订阅收据，让每一步都有可追溯的边界。','Turn trust-sensitive actions into inspectable rules. From a report version to a review and a subscription receipt, each step has a traceable boundary.')}</p><a href={source} target="_blank" rel="noreferrer">{t('查看公开合约源码','Inspect public contract source')} ↗</a></div></div>
    <ol className={styles.flow} aria-label={t('设计流程，非实时交易','Design flow, not live transactions')}>{[t('原始资料','Source material'),t('内容哈希','Content hash'),t('钱包签名','Wallet signature'),t('不可覆盖的记录','Append-only record')].map((label,index)=><li key={label}><span>0{index+1}</span><b>{label}</b>{index<3&&<i aria-hidden="true">→</i>}</li>)}</ol>
    <div className={styles.grid}>{modules.map(([n,kicker,title,body,code])=><article key={n}><header><span>{n}</span><small>{kicker}</small></header><h3>{title}</h3><p>{body}</p><code>{code}</code></article>)}</div>
    <details className={styles.details}><summary>{t('查看实现边界与上线条件','Implementation boundaries & release gates')}<span>＋</span></summary><div><h3>{t('已实现的是源码，不是主网协议。','Source implementation, not a live mainnet protocol.')}</h3><p>{t('包含 Anchor / Rust 合约与构建检查。当前网站继续使用既有 Memo 存证、服务端订阅校验和免费体验逻辑，尚未切换至这些自定义合约。合约尚未独立安全审计。','Includes Anchor / Rust contracts and build checks. The website continues to use its existing Memo provenance, server-side subscription verification and free-trial logic; it has not migrated to these custom contracts. The contracts have not received an independent security audit.')}</p><p>{t('上线前仍需：部署包验证、真实虚拟机安全测试、独立复核、明确升级权限、测试网验证与服务端收据接入，最后由钱包所有者确认网络费用并签名。不会把编译通过宣传成资金安全保证。','Release requires deployment-artifact verification, VM security tests, independent review, documented upgrade authority, test-network validation and a server receipt integration, followed by owner-approved network fees and wallet signatures. Compilation is not a guarantee of funds safety.')}</p><p>{t('完整原文和个人资料不上链；证据根只承诺所选数据。审核仍是审核者的声明，而不是自动判真的预言机。','Full source text and personal information stay off-chain. Evidence roots commit only selected data. Reviews remain attributed statements, not an oracle that automatically certifies truth.')}</p><a href={checks} target="_blank" rel="noreferrer">{t('查看实时构建结果与失败记录','View current build results and failures')} ↗</a></div></details>
    <footer>{t('未部署 · 未独立审计 · 无自动交易 · 不承诺收益','Not deployed · Not independently audited · No automatic trading · No promised returns')}</footer>
  </section>;
}
