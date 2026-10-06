"use client";
import {useEffect,useMemo,useRef,useState} from "react";
import {useSceneActivity} from "./useSceneActivity";
import {validateLandPoints} from "./scene-clock.mjs";
import styles from "./OraktWorldScene.module.css";

type Point=[number,number];
const stations=[
 {x:-180,z:-20,color:"#a3ff12",en:"NEWS",zh:"新闻",code:"01"},
 {x:0,z:-182,color:"#00e5ff",en:"MACRO",zh:"宏观",code:"02"},
 {x:180,z:20,color:"#9b5cff",en:"MARKETS",zh:"市场",code:"03"},
 {x:0,z:184,color:"#00e5ff",en:"SUPPLY",zh:"供应链",code:"04"},
];

export default function OraktWorldScene({language}:{language:"zh"|"en"}){
 const {ref,running,visible,reduced}=useSceneActivity();
 const canvasRef=useRef<HTMLCanvasElement>(null),timeRef=useRef(0);
 const [land,setLand]=useState<Point[]>([]),[unavailable,setUnavailable]=useState(false),[paused,setPaused]=useState(false);
 const playing=running&&!paused;
 const globePoints=useMemo(()=>land.map(([lon,lat])=>{
  const phi=lat*Math.PI/180,theta=lon*Math.PI/180;
  return [Math.cos(phi)*Math.sin(theta),-Math.sin(phi),Math.cos(phi)*Math.cos(theta)];
 }),[land]);
 useEffect(()=>{
  if(!visible||land.length||unavailable)return;
  const controller=new AbortController();
  fetch("/brand/world-land-points.json",{signal:controller.signal})
   .then(response=>{if(!response.ok)throw new Error("geography");return response.json();})
   .then(validateLandPoints).then(points=>{if(!controller.signal.aborted)setLand(points);})
   .catch(()=>{if(!controller.signal.aborted)setUnavailable(true);});
  return ()=>controller.abort();
 },[visible,land.length,unavailable]);
 useEffect(()=>{
  const canvas=canvasRef.current;if(!canvas)return;
  const ctx=canvas.getContext("2d",{alpha:true});if(!ctx)return;
  let frame=0,last=0,sceneScale=1;
  const scale=()=>{
   const {width,height}=canvas.getBoundingClientRect();
   const dpr=Math.min(window.devicePixelRatio||1,1.75);
   canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
   sceneScale=Math.max(.1,Math.min(width/720,height/530));
   ctx.setTransform(sceneScale*dpr,0,0,sceneScale*dpr,(width-720*sceneScale)*dpr/2,(height-530*sceneScale)*dpr/2);
  };
  const project=(x:number,z:number,h=0):Point=>[360+(x-z)*.78,340+(x+z)*.35-h];
  const polygon=(points:Point[],fill:string,stroke?:string)=>{
   ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();
   ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.stroke();}
  };
  const line=(points:Point[],color:string,width=1)=>{
   ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();
  };
  const tile=(x:number,z:number,size:number,h:number,depth:number,color:string)=>{
   const corners=[project(x-size,z-size,h),project(x+size,z-size,h),project(x+size,z+size,h),project(x-size,z+size,h)];
   polygon([corners[1],corners[2],project(x+size,z+size,h-depth),project(x+size,z-size,h-depth)],"#121b2a",color+"35");
   polygon([corners[2],corners[3],project(x-size,z+size,h-depth),project(x+size,z+size,h-depth)],"#0d1320",color+"4d");
   polygon(corners,"#141b26",color+"90");
   line([corners[3],corners[2],corners[1]],color+"bc",1.3);
   return corners;
  };
  const drawStation=(station:typeof stations[number],index:number,t:number)=>{
   const {x,z,color}=station,lift=20+Math.sin(t*.9+index)*2;
   tile(x,z,31,lift,14,color);tile(x,z,27,lift+6,4,color);
   if(index===0){
    for(let i=0;i<4;i++)tile(x,z,21,lift+13+i*6,3,color);
    const [cx,cy]=project(x,z,lift+35);ctx.save();ctx.translate(cx,cy);
    for(let i=0;i<3;i++)line([[-13+i*2,i*5-8],[11,i*5-8]],color+(i===0?"ee":"70"),1.7);ctx.restore();
   }else if(index===1){
    const [cx,cy]=project(x,z,lift+48);
    polygon([[cx-22,cy-10],[cx+22,cy+2],[cx+22,cy+37],[cx-22,cy+25]],"#0b1923",color+"a0");
    for(let i=0;i<4;i++)line([[cx-16,cy+i*7],[cx+16,cy+9+i*7]],color+"20",.7);
    line([[cx-16,cy+18],[cx-7,cy+12],[cx+1,cy+18],[cx+10,cy+7],[cx+17,cy+10]],color,1.7);
   }else if(index===2){
    for(let i=0;i<4;i++)tile(x-17+i*11,z-3,4,lift+16+i*11,10+i*11,color);
   }else{
    tile(x-12,z-8,10,lift+20,13,color);tile(x+12,z-8,10,lift+20,13,color);tile(x,z+13,10,lift+20,13,color);
   }
   const [cx,cy]=project(x,z,lift);
   ctx.font=`500 ${11/sceneScale}px system-ui`;ctx.textAlign="center";ctx.fillStyle="#d9e5e9";ctx.fillText(language==="zh"?station.zh:station.en,cx,cy+39/sceneScale);
   ctx.font=`${8/sceneScale}px monospace`;ctx.fillStyle=color;ctx.fillText(station.code,cx,cy+54/sceneScale);
  };
  const draw=()=>{
   const t=timeRef.current;
   ctx.save();ctx.resetTransform();ctx.clearRect(0,0,canvas.width,canvas.height);ctx.restore();
   const glow=ctx.createRadialGradient(360,310,20,360,310,320);
   glow.addColorStop(0,"#213c562a");glow.addColorStop(.65,"#402a6220");glow.addColorStop(1,"#11132100");ctx.fillStyle=glow;ctx.fillRect(0,0,720,530);
   // Bevelled observation floor, two layers and a fine engraved coordinate grid.
   tile(0,0,224,-12,11,"#9b5cff");tile(0,0,218,0,10,"#516581");
   for(let i=-208;i<=208;i+=26){
    line([project(i,-215,1),project(i,215,1)],i%52===0?"#41587160":"#41587128",.6);
    line([project(-215,i,1),project(215,i,1)],i%52===0?"#41587160":"#41587128",.6);
   }
   for(let x=-182;x<=182;x+=52)for(let z=-182;z<=182;z+=52){const [px,py]=project(x,z,2);ctx.fillStyle="#506c8c88";ctx.fillRect(px-.8,py-.8,1.6,1.6);}
   // Orthogonal light paths carry symbolic signals, not live market observations.
   stations.forEach((station,index)=>{
    const points=[project(station.x,station.z,3),project(station.x*.48,station.z,3),project(station.x*.48,station.z*.33,3),project(0,0,3)];
    line(points,station.color+"42",1.2);
    ctx.setLineDash([5,8]);line(points,station.color+"25",.6);ctx.setLineDash([]);
    for(let packet=0;packet<3;packet++){
     const u=((t*.22+packet+index*.7)%3),section=Math.floor(u),mix=u-section;
     const a=points[section],b=points[section+1],x=a[0]+(b[0]-a[0])*mix,y=a[1]+(b[1]-a[1])*mix;
     ctx.fillStyle=station.color;ctx.shadowColor=station.color;ctx.shadowBlur=5;ctx.fillRect(x-2,y-1.2,4,2.4);ctx.shadowBlur=0;
    }
   });
   drawStation(stations[0],0,t);drawStation(stations[1],1,t);
   // Layered optical plinth and suspension beneath the globe.
   tile(0,0,68,15,11,"#9b5cff");tile(0,0,61,30,8,"#00e5ff");tile(0,0,54,38,4,"#a3ff12");
   for(let i=0;i<3;i++){const [cx,cy]=project(0,0,47+i*9);ctx.beginPath();ctx.ellipse(cx,cy,48-i*6,16-i*2,0,0,Math.PI*2);ctx.strokeStyle=["#9b5cff60","#00e5ff80","#a3ff1260"][i];ctx.lineWidth=.8;ctx.stroke();}
   const gx=360,gy=205+Math.sin(t*.65)*3,radius=86;
   ctx.save();ctx.translate(gx,gy);
   const atmosphere=ctx.createRadialGradient(-30,-25,4,0,0,105);
   atmosphere.addColorStop(0,"#285069b0");atmosphere.addColorStop(.67,"#101e31f0");atmosphere.addColorStop(.81,"#377aa378");atmosphere.addColorStop(.86,"#7294d44d");atmosphere.addColorStop(1,"#3e439000");
   ctx.fillStyle=atmosphere;ctx.beginPath();ctx.arc(0,0,105,0,Math.PI*2);ctx.fill();
   ctx.strokeStyle="#7897b234";ctx.lineWidth=.55;
   for(const ratio of [.25,.6,1]){ctx.beginPath();ctx.ellipse(0,0,radius*ratio,radius,-.18,0,Math.PI*2);ctx.stroke();}
   for(const yy of [-.66,-.33,0,.33,.66]){ctx.beginPath();ctx.ellipse(0,yy*radius,Math.sqrt(1-yy*yy)*radius,11,-.18,0,Math.PI*2);ctx.stroke();}
   const rotation=t*.075-.9,cos=Math.cos(rotation),sin=Math.sin(rotation);
   globePoints.forEach(([baseX,baseY,baseZ])=>{
    const depth=baseZ*cos-baseX*sin;if(depth<0)return;
    const x=radius*(baseX*cos+baseZ*sin),y=radius*baseY;
    ctx.fillStyle=`rgba(${100+depth*72},${190+depth*48},${218+depth*35},${.25+depth*.72})`;ctx.fillRect(x-.65,y-.65,1.3+depth*.5,1.3+depth*.5);
   });
   // Three axial orbits, with a moving light head on each trajectory.
   for(let i=0;i<3;i++){
    ctx.save();ctx.rotate([-.35,.43,-.86][i]);const rx=116+i*6,ry=29+i*8;
    ctx.beginPath();ctx.ellipse(0,8,rx,ry,0,0,Math.PI*2);ctx.strokeStyle=["#a3ff124e","#00e5ff5b","#9b5cff52"][i];ctx.lineWidth=.8;ctx.stroke();
    const a=t*(.26+i*.05)+i*2;ctx.beginPath();ctx.ellipse(0,8,rx,ry,0,a-.18,a);ctx.strokeStyle=["#a3ff12","#00e5ff","#9b5cff"][i];ctx.lineWidth=2;ctx.stroke();
    ctx.fillStyle="#e6faff";ctx.beginPath();ctx.arc(Math.cos(a)*rx,8+Math.sin(a)*ry,1.8,0,Math.PI*2);ctx.fill();ctx.restore();
   }
   ctx.restore();
   drawStation(stations[3],3,t);drawStation(stations[2],2,t);
  };
  const tick=(now:number)=>{
   if(!last)last=now;
   if(now-last>=32){timeRef.current+=Math.min((now-last)/1000,.05);last=now;draw();}
   frame=requestAnimationFrame(tick);
  };
  scale();draw();const resize=new ResizeObserver(()=>{scale();draw();});resize.observe(canvas);
  if(playing)frame=requestAnimationFrame(tick);
  return ()=>{cancelAnimationFrame(frame);resize.disconnect();};
 },[playing,globePoints,language]);
 return <div ref={ref} className={styles.scene} data-scene="world" data-running={playing} data-animation="loop">
  <div className={styles.header}><span><i/> ORAKT WORLD <b>/ 01</b></span><button type="button" onClick={()=>setPaused(value=>!value)} disabled={reduced} aria-pressed={paused||reduced} aria-label={language==="zh"?(paused?"播放世界动画":"暂停世界动画"):(paused?"Play world animation":"Pause world animation")}>{paused||reduced?"▶":"Ⅱ"}</button></div>
  <div className={styles.caption}><span>GLOBAL OBSERVATORY</span><h4>{language==="zh"?"一个世界，多重传导。":"One world. Many connections."}</h4><p>{language==="zh"?"定位事件 / 连接产业 / 追踪影响":"LOCATE / CONNECT / TRACE"}</p></div>
  <canvas ref={canvasRef} className={styles.canvas} role="img" aria-label={language==="zh"?"立体全球信号观测站，新闻、宏观、供应链与市场通过光路联结。概念动画，非实时数据。":"Isometric global observatory linking news, macro, supply and markets. Concept animation, not live data."}/>
  {unavailable&&<div className={styles.notice} role="status"><span>{language==="zh"?"地图轮廓暂不可用，当前显示网络示意。":"Map outline unavailable. Showing the network schematic."}</span><button type="button" onClick={()=>setUnavailable(false)}>{language==="zh"?"重新加载":"Retry"}</button></div>}
  <div className={styles.footer}><span>{language==="zh"?"地理底图 · Natural Earth":"GEOGRAPHY · NATURAL EARTH"}</span><span>{language==="zh"?"信号网络示意 · 非实时":"NETWORK CONCEPT · NOT LIVE"}</span></div>
 </div>;
}
