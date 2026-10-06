import OraktBrandIcon from "./OraktBrandIcon";
import ReleaseStatus from "./ReleaseStatus";
import styles from "./SiteFooter.module.css";

export const footerGroups=[
 {zh:"产品与数据",en:"Product & data",links:[
  {href:"/platform",zh:"事件地图",en:"Event map"},
  {href:"/platform/research",zh:"研究报告目录",en:"Report catalog"},
  {href:"/platform/filings",zh:"公司披露查验",en:"Filings review"},
  {href:"/platform/data",zh:"数据状态",en:"Data status"},
  {href:"/lab",zh:"因子实验室",en:"Factor lab"},
 ]},
 {zh:"学习与方法",en:"Learn & understand",links:[
  {href:"/lab#alpha",zh:"什么是 Alpha",en:"What is Alpha?"},
  {href:"/lab#validation",zh:"因子如何验证",en:"How factors are tested"},
  {href:"/research#evidence",zh:"理解证据链",en:"Understanding evidence"},
  {href:"/research#read-report",zh:"报告阅读指南",en:"How to read a report"},
  {href:"/research#data-boundaries",zh:"数据与来源边界",en:"Data & source limits"},
 ]},
 {zh:"公司与方向",en:"Company & direction",links:[
  {href:"/company",zh:"关于 INSOLVE TECH",en:"About INSOLVE TECH"},
  {href:"/company#principles",zh:"研究原则",en:"Research principles"},
  {href:"/research",zh:"研究方法",en:"Methodology"},
  {href:"/roadmap",zh:"未来方向",en:"Product direction"},
  {href:"/plans",zh:"套餐方案预览",en:"Plan preview"},
 ]},
 {zh:"账号与帮助",en:"Account & help",links:[
  {href:"/membership",zh:"账号与访问指南",en:"Identity & access guide"},
  {href:"/access",zh:"登录 ORAKT",en:"Sign in"},
  {href:"/access/register",zh:"注册独立账号",en:"Create an account"},
  {href:"/account",zh:"账号中心",en:"Account center"},
  {href:"/access/recover",zh:"恢复账号",en:"Account recovery"},
  {href:"/membership#account-help",zh:"常见问题与帮助",en:"Account help"},
 ]},
] as const;

export default function SiteFooter({language,snapshotAt,page}:{language:"zh"|"en";snapshotAt:string;page:string}){
 const zh=language==="zh";
 return <footer className={styles.footer} data-site-footer>
   <div className={styles.top}><a className={styles.brand} href="/" aria-label={zh?"ORAKT 官网首页":"ORAKT home"}><OraktBrandIcon/><span><strong>ORAKT</strong><small>BY INSOLVE TECH</small></span></a><p>{zh?"从看见事件，到理解证据。\n为每一个“为什么”，保留继续追问的入口。":"From seeing an event to understanding its evidence.\nKeep a way to question every “why”."}</p><a className={styles.start} href="/research#read-report">{zh?"从阅读指南开始":"Start with the reading guide"}<span aria-hidden="true">↗</span></a></div>
   <nav className={styles.directory} aria-label={zh?"网站底部导航":"Site footer navigation"}>{footerGroups.map(group=><section key={group.en}><h2>{group[language]}</h2><ul>{group.links.map(link=><li key={link.href}><a href={link.href} aria-current={link.href===`/${page}`?"page":undefined}>{link[language]}</a></li>)}</ul></section>)}</nav>
   <div className={styles.notes}><p>{zh?"研究工具，非投资建议。网站提供已发布数据，不是实时交易终端。在线 AI 生成、自动交易与自动扣费尚未开放。":"Research tool, not investment advice. Published data, not a live trading terminal. Online AI generation, automated trading and automatic billing are not enabled."}</p><div><a href="/research#risk-notice">{zh?"研究风险说明":"Research risk notice"}</a><a href="/membership#account-safety">{zh?"账号安全说明":"Account safety"}</a><a href="/roadmap#status-language">{zh?"功能状态说明":"Feature availability"}</a></div></div>
   <div className={styles.bottom}><span>© 2026 ORAKT · INSOLVE TECH</span><span>{zh?"数据版本日期":"Data version date"} · {new Date(snapshotAt).toISOString().slice(0,10)}</span><ReleaseStatus language={language}/><a href={page==="home"?"#top":"#main-content"}>{zh?"返回顶部 ↑":"Back to top ↑"}</a></div>
 </footer>;
}
