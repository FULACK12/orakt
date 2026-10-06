import {marketingGuides} from "./marketing-guide-content";
import type {MarketingPageKey} from "./marketing-pages";
import {methodNotes} from "./marketing-method-notes";
import styles from "./MarketingGuide.module.css";

export default function MarketingGuide({page,language}:{page:MarketingPageKey;language:"zh"|"en"}){
 const content=marketingGuides[page],note=methodNotes[page],zh=language==="zh";
 return <section className={styles.guide} aria-label={zh?"深入理解与使用指南":"Concepts and practical guide"} data-guide={page}>
   <header id="abstract" className={styles.intro} data-method-note={page}>
     <div className={styles.paperMeta}><span>ORAKT / {page.toUpperCase()}</span><span>{note.kind[language]}</span></div><h2>{note.title[language]}</h2>
     <div className={styles.abstractLabel}>{zh?"摘要":"ABSTRACT"}</div>
     {note.abstract.map((p,i)=><p className={styles.abstract} key={i}>{p[language]}</p>)}
     <div className={styles.keywords}><span>{zh?"关键词":"KEYWORDS"}</span>{note.keywords.map(k=><span key={k.en}>{k[language]}</span>)}</div>
   </header>
   <div className={styles.layout}>
     <aside className={styles.contents}><nav aria-label={zh?"本页阅读目录":"On this page"}><span>{zh?"内容索引":"CONTENTS"}</span><a href="#abstract"><small>ABS</small>{zh?"摘要与研究范围":"Abstract & scope"}</a>{content.sections.map((section,i)=><a key={section.id} href={`#${section.id}`}><small>{String(i+1).padStart(2,"0")}</small>{section.title[language]}</a>)}<a href="#methodology"><small>MTH</small>{zh?"技术说明与适用条件":"Technical specification"}</a><a href="#faq"><small>Q/A</small>{zh?"常见问题":"Common questions"}</a></nav><p>{zh?"定义、方法与证据边界。":"Definitions, methods and evidence boundaries."}</p></aside>
     <div className={styles.chapters}>
       {content.sections.map((section,index)=><section key={section.id} id={section.id} className={styles.chapter} aria-labelledby={`${section.id}-heading`}>
         <div className={styles.chapterRule}><span>{String(index+1).padStart(2,"0")}</span><i/></div>
         <h2 id={`${section.id}-heading`}>{section.title[language]}</h2><p className={styles.lead}>{section.lead[language]}</p>
         {section.paragraphs?.map((p,i)=><p className={styles.prose} key={i}>{p[language]}</p>)}
         {section.cards&&<div className={styles.cards}>{section.cards.map(card=><article key={card.title.en}><h3>{card.title[language]}</h3><p>{card.body[language]}</p></article>)}</div>}
         {section.steps&&<ol className={styles.steps}>{section.steps.map((step,i)=><li key={step.title.en}><span aria-hidden="true">{String(i+1).padStart(2,"0")}</span><div><h3>{step.title[language]}</h3><p>{step.body[language]}</p></div></li>)}</ol>}
         {section.table&&<div className={styles.tableWrap} role="region" aria-label={section.title[language]} tabIndex={0}><table><caption>{section.title[language]}</caption><thead><tr>{section.table.headers.map(cell=><th key={cell.en} scope="col">{cell[language]}</th>)}</tr></thead><tbody>{section.table.rows.map((row,i)=><tr key={i}>{row.map((cell,j)=>j===0?<th key={j} scope="row">{cell[language]}</th>:<td key={j}>{cell[language]}</td>)}</tr>)}</tbody></table></div>}
         {section.callout&&<aside className={styles.callout}><span>{section.callout.label[language]}</span><p>{section.callout.body[language]}</p></aside>}
         {section.references&&<div className={styles.references}><span>{zh?"概念参考 · 不代表对本产品的认证":"Concept references · Not product endorsements"}</span>{section.references.map(reference=><a key={reference.href} href={reference.href} target="_blank" rel="noopener noreferrer">{reference.title}<span aria-hidden="true">↗</span></a>)}</div>}
       </section>)}
       <section id="methodology" className={styles.chapter} aria-labelledby="methodology-heading">
         <div className={styles.chapterRule}><span>MTH</span><i/></div><h2 id="methodology-heading">{zh?"技术说明与适用条件":"Technical specification & conditions"}</h2><p className={styles.lead}>{note.kind[language]}</p>
         {note.methods.map((method,i)=><article key={method.title.en} className={styles.method}><div className={styles.methodLabel}>M.{String(i+1).padStart(2,"0")}</div><h3>{method.title[language]}</h3>{method.paragraphs.map((p,j)=><p key={j} className={styles.prose}>{p[language]}</p>)}{method.formula&&<figure className={styles.equation}><figcaption>{zh?"模型定义 · 非实测结果":"MODEL DEFINITION · NOT AN EMPIRICAL RESULT"}</figcaption><code>{method.formula.expression}</code><p>{method.formula.definition[language]}</p></figure>}</article>)}
         <aside className={styles.methodBoundary}><strong>{zh?"范围与局限":"Scope and limitations"}</strong><p>{note.boundary[language]}</p></aside>
         {note.references&&<div className={styles.references}><span>{zh?"方法文献 · 不代表对 ORAKT 的认证":"Method references · Not ORAKT endorsements"}</span>{note.references.map(reference=><a href={reference.href} key={reference.href} target="_blank" rel="noopener noreferrer">{reference.title} ↗</a>)}</div>}
       </section>
       <section id="faq" className={styles.faq} aria-labelledby="faq-heading"><div className={styles.chapterRule}><span>Q/A</span><i/></div><h2 id="faq-heading">{zh?"补充说明":"Further considerations"}</h2><p className={styles.lead}>{zh?"常见概念分歧与使用边界。":"Common conceptual distinctions and usage boundaries."}</p>{content.faq.map(item=><details key={item.question.en}><summary>{item.question[language]}<span aria-hidden="true"/></summary><p>{item.answer[language]}</p></details>)}</section>
       <nav className={styles.next} aria-label={zh?"继续阅读":"Continue reading"}>{content.next.map((item,i)=><a href={item.href} key={item.href}><small>{zh?"继续探索":"KEEP EXPLORING"} / 0{i+1}</small><span>{item.label[language]}<b aria-hidden="true">↗</b></span></a>)}</nav>
     </div>
   </div>
 </section>;
}

