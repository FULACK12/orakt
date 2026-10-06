"use client";
import {useId,useState} from "react";
import {useSceneActivity} from "./useSceneActivity";
import styles from "./OraktContour.module.css";

// Original geometric letter outlines. These are paths, not a raster or a font dependency.
const word="M125 100H195Q270 100 270 175V280Q270 355 195 355H125Q50 355 50 280V175Q50 100 125 100ZM132 153Q104 153 104 181V274Q104 302 132 302H188Q216 302 216 274V181Q216 153 188 153Z M315 100H449Q518 100 518 170V190Q518 236 472 249L532 355H466L411 255H372V355H315ZM372 153V205H440Q462 205 462 185V175Q462 153 440 153Z M557 355L644 100H709L796 355H736L718 299H635L617 355ZM652 246H701L677 168Z M838 100H895V203L976 100H1046L947 223L1055 355H982L895 246V355H838Z M1090 100H1315V154H1231V355H1174V154H1090Z";

export default function OraktContour({language}:{language:"zh"|"en"}){
 const {ref,running,reduced}=useSceneActivity();
 const [paused,setPaused]=useState(false);
 const id=useId().replace(/:/g,"");
 const gradient=`${id}-spectrum`,glyph=`${id}-letters`;
 const zh=language==="zh";
 return <div ref={ref} id="orakt-signature" className={styles.signature} data-contour="orakt" data-animation="permanent-loop" data-running={running&&!paused}>
   <div className={styles.caption}><span>ORAKT / CONNECTED INTELLIGENCE</span><button type="button" onClick={()=>setPaused(value=>!value)} disabled={reduced} aria-pressed={paused||reduced} aria-label={zh?(paused?"播放品牌线条动画":"暂停品牌线条动画"):(paused?"Play brand contour animation":"Pause brand contour animation")}>{paused||reduced?"▶":"Ⅱ"}</button></div>
   <svg className={styles.art} viewBox="0 0 1400 520" role="img" aria-labelledby={`${id}-title`}>
     <title id={`${id}-title`}>{zh?"ORAKT 三色渐变线条字标：荧光绿、青蓝与紫色层叠延展":"ORAKT contour wordmark in layered lime, cyan and violet"}</title>
     <defs><linearGradient id={gradient} x1="30" y1="390" x2="1330" y2="80" gradientUnits="userSpaceOnUse"><stop stopColor="#a3ff12"/><stop offset=".47" stopColor="#00e5ff"/><stop offset="1" stopColor="#9b5cff"/></linearGradient><path id={glyph} d={word} fill="none" vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round"/></defs>
     <g stroke={`url(#${gradient})`} strokeWidth="1.1" className={styles.contours}>
       {Array.from({length:18},(_,i)=>{const depth=17-i;return <use key={depth} href={`#${glyph}`} transform={`translate(${-depth*3.4} ${depth*6.8+12})`} opacity={.09+i*.023}/>;})}
     </g>
     <use href={`#${glyph}`} transform="translate(0 12)" stroke={`url(#${gradient})`} strokeWidth="1.7" opacity=".94"/>
     <use className={styles.highlight} href={`#${glyph}`} transform="translate(0 12)" stroke={`url(#${gradient})`} strokeWidth="2.4" strokeDasharray="120 1800"/>
   </svg>
   <div className={styles.baseline}><span>OBSERVE / CONNECT / VERIFY</span><span>BY INSOLVE TECH</span></div>
 </div>;
}
