export function anchorState(record){
 if(!record)return 'empty';
 if(record.anchors.some(a=>a.revision===record.revision&&a.signature))return 'finalized';
 if(record.revision>0)return 'ready';
 return 'review';
}
export function visibleStats(items){return {visible:items.length,review:items.filter(x=>x.state==='pending'||x.state==='changes_requested').length,reviewed:items.filter(x=>x.revision>0).length,anchored:items.filter(x=>anchorState(x)==='finalized').length};}
