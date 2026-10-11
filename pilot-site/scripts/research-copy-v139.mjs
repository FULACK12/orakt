import {readFileSync,writeFileSync} from 'node:fs';
function update(path,replacements){let text=readFileSync(path,'utf8');for(const [before,after] of replacements){if(!text.includes(before))throw Error(path+': missing anchor');text=text.replaceAll(before,after);}writeFileSync(path,text);}
update('app/account/AccountCenter.tsx',[
 ['manageUsers:boolean','manageUsers:boolean;generateAI?:boolean'],
 ['<span>DEMO</span>','<span>LOCAL AI</span>'],
 ['{label:zh?"在线 AI 生成":"Online AI generation",enabled:false}','{label:zh?"本地 AI 研究草稿":"Local AI research drafts",enabled:access!.research&&!!data.account.membership.permissions.generateAI}'],
 ['所有账号均不能调用后台 AI 生成。','RESEARCH 可排队生成本地 AI 草稿，需工作机在线，结果须复审。'],
 ['AI generation remains disabled.','RESEARCH can queue local AI drafts when the worker is online; outputs require review.']
]);
update('app/PersonalResearch.tsx',[
 [",[mode,setMode]=useState('evidence')",''],
 ['<select aria-label={t(\'研究模式\',\'Research mode\')} value={mode} disabled={busy} onChange={e=>setMode(e.target.value)}><option value="evidence">{t(\'证据研究\',\'Evidence research\')}</option><option value="brief">{t(\'简洁提纲\',\'Quick outline\')}</option></select>',"<span>{t('九章证据研究','Nine-chapter evidence research')}</span>"],
 ['草稿未审核；历史任务保存在账号下。','草稿未审核；问题与所选证据将传至运营方本地工作机处理，任务和结果保存在账号下。请勿提交敏感资料。'],
 ['Drafts are unreviewed; jobs are retained under your account.','Drafts are unreviewed. Questions and selected evidence are processed on the operator’s local worker; jobs and results are retained under your account. Do not submit sensitive data.']
]);
update('app/legal/LegalDocument.tsx',[
 ["privacy:{title:['隐私与账号数据','Privacy & account data'],sections:[","privacy:{title:['隐私与账号数据','Privacy & account data'],sections:[\n  ['本地 AI 研究任务','Local AI research jobs','提交研究问题时，问题、语言、账号任务标识与所选公开证据保存在网站队列，并传至运营方本地工作机，由 orakt-14b 生成草稿。本地保存章节检查点，网站保存任务和结果以便账号访问。此功能不调用付费云模型，不自动联网或上链。取消任务会停止后续处理，但不自动删除已保存的任务和检查点。请勿输入敏感个人信息、秘密或无权处理的资料。删除请求需核验账号后由运营方处理。','Research questions, language, account-linked job identifiers and selected public evidence are stored in the website queue and processed by orakt-14b on the operator’s local worker. Chapter checkpoints are retained locally; jobs and outputs are retained by the website for account access. This feature does not call paid cloud models, browse automatically or publish on-chain. Cancellation stops further processing but does not automatically erase retained jobs or checkpoints. Do not enter sensitive personal data, secrets or material you cannot process. Deletion requests require ownership verification by the operator.'],"],
 ['更新于 2026-10-06','更新于 2026-10-11'],['Updated 2026-10-06','Updated 2026-10-11']
]);
