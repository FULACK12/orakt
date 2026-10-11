import {readFileSync,writeFileSync} from 'node:fs';
const file='app/account/billing/page.tsx';let s=readFileSync(file,'utf8');
for(const [a,b] of [
 ['演示聊天包含在线 AI 吗？','套餐包含本地 AI 研究吗？'],['Does demo chat include online AI?','Does my plan include local AI research?'],
 ['不包含。询问 ORAKT 目前是本地交互演示，套餐付款不会开放模型生成或产生额外调用额度。','RESEARCH（含有效赠送授权）可使用本地 orakt-14b 生成九章草稿，每账号每天最多 5 次、同时 1 个任务；需工作机在线并单 GPU 排队。Signal 和 Explorer 不含生成权限。结果未经实质复审，不自动发布或上链。'],
 ['No. Ask ORAKT currently provides a local interaction demo. Paying for a plan does not enable model generation or additional AI credits.','RESEARCH, including valid complimentary grants, can generate nine-chapter drafts with local orakt-14b: up to five jobs per account per day and one active job, subject to worker availability and a single-GPU queue. Signal and Explorer do not include generation. Outputs are unreviewed and are not automatically published or anchored.']
]){if(!s.includes(a))throw Error('Missing copy');s=s.replaceAll(a,b);}writeFileSync(file,s);
