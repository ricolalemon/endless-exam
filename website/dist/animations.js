(function () {
  'use strict';
  const data = typeof module !== 'undefined' && module.exports ? require('./story-data.js') : window.EndlessAtlasData;
  const TAU = 2 * Math.PI, clamp = (v,a=0,b=1)=>Math.min(b,Math.max(a,v));
  const smooth = v => (v=clamp(v))*v*(3-2*v), mix=(a,b,t)=>a+(b-a)*t;
  function trianglePoints(t) {
    return Array.from({length:7},(_,i)=>{const a=TAU*i/7-Math.PI/2+.11*Math.sin(t*.16+i*1.4),r=.36+.045*Math.sin(t*.23+i*.83);return [Math.round((.5+r*Math.cos(a))*10000),Math.round((.5+r*Math.sin(a))*10000)];});
  }
  function minimumTriangle(points) {
    let area=Infinity,indices=[];const areas=[];
    for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++)for(let k=j+1;k<points.length;k++){
      const [a,b,c]=[points[i],points[j],points[k]],v=Math.abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2e8;
      areas.push(v);if(v<area){area=v;indices=[i,j,k];}
    }return {area,indices,areas};
  }
  function distances(edges,source,n=10){const d=Array(n).fill(Infinity),queue=[source];d[source]=0;for(const u of queue)for(const [a,b] of edges){const v=a===u?b:b===u?a:-1;if(v>=0&&d[v]===Infinity){d[v]=d[u]+1;queue.push(v);}}return d;}
  const math={data,trianglePoints,minimumTriangle,distances};
  if(typeof module!=='undefined'&&module.exports)module.exports=math;
  if(typeof document==='undefined')return;
  const $=id=>document.getElementById(id),root=$('constructions');
  if(!root)return;
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  const palette={gold:'#916b2e',white:'#3c4735',muted:'#707966',line:'#758267',ink:'#f8f8f5',soft:'#69755c'};
  let ctx,W=0,H=0,frame=0,still=media.matches;
  const states=data.map(f=>{const article=$('family-'+f.id),canvas=$('figure-'+f.id);return {f,article,canvas,figure:article.querySelector('figure'),context:canvas.getContext('2d'),progress:0,target:0,dirty:true,width:0,height:0};});
  const reveal=(p,i,n)=>smooth((p*n-i)*1.5), font=()=>W<450?13:16;
  function line(a,b,color=palette.line,alpha=.35,width=1){ctx.globalAlpha=clamp(alpha);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();ctx.globalAlpha=1;}
  function dot(p,r=4,color=palette.white,alpha=1){
    ctx.save();ctx.globalAlpha=clamp(alpha);ctx.fillStyle=color;
    ctx.beginPath();ctx.arc(p[0],p[1],Math.max(0,r),0,TAU);ctx.fill();ctx.restore();
  }
  function ring(p,r,color=palette.gold,alpha=.6,width=1){ctx.globalAlpha=clamp(alpha);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.arc(p[0],p[1],Math.max(0,r),0,TAU);ctx.stroke();ctx.globalAlpha=1;}
  function text(s,x,y,size=font(),color=palette.muted,align='center',alpha=1){ctx.globalAlpha=clamp(alpha);ctx.fillStyle=color;ctx.font=`${size}px 'DM Sans',Arial,sans-serif`;ctx.textAlign=align;ctx.textBaseline='middle';ctx.fillText(String(s),x,y);ctx.globalAlpha=1;}
  function rect(x,y,w,h,color=palette.gold,alpha=.15,stroke=false){ctx.globalAlpha=clamp(alpha);if(stroke){ctx.strokeStyle=color;ctx.lineWidth=1;ctx.strokeRect(x,y,w,h);}else{ctx.fillStyle=color;ctx.fillRect(x,y,w,h);}ctx.globalAlpha=1;}
  function polygon(points,color=palette.gold,alpha=.13){ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.fillStyle=color;ctx.globalAlpha=alpha;ctx.fill();ctx.globalAlpha=1;}
  function bracket(p,color=palette.white){line([p[0]-5,p[1]-5],[p[0]+5,p[1]+5],color,.55);line([p[0]+5,p[1]-5],[p[0]-5,p[1]+5],color,.55);}
  function project(v,angle,scale,cx=W/2,cy=H*.47){const [x,y,z]=v,a=x*Math.cos(angle)+z*Math.sin(angle),b=-x*Math.sin(angle)+z*Math.cos(angle),tilt=-.35,yy=y*Math.cos(tilt)-b*Math.sin(tilt),zz=y*Math.sin(tilt)+b*Math.cos(tilt),f=4.5/(4.5+zz);return [cx+a*scale*f,cy-yy*scale*f,zz,f];}
  function curve(a,b,bend,color=palette.gold,alpha=.45){ctx.globalAlpha=alpha;ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(...a);ctx.bezierCurveTo(a[0],a[1]+bend,b[0],b[1]-bend,...b);ctx.stroke();ctx.globalAlpha=1;}
  const phaseWords={
    capset:['Begin with a finite space of possible points.','Select a structured set of points.','No selected triple sums to zero.'],
    labs:['A sequence of thirteen signs.','Compare the sequence with a shifted copy.','The nonzero-shift correlations stay small.'],
    heilbronn:['Place seven points inside the square.','Every triple forms a triangle.','The highlighted triangle limits the objective.'],
    spherical_code:['Directions live on a unit sphere.','Twelve well-separated directions appear.','Even the closest pair exceeds 60°.'],
    corners:['Begin with the square grid.','A corner-free set takes shape.','The third point of this corner is absent.'],
    matmul:['Start with the two input matrices.','Compute seven shared scalar products.','Recombine them to obtain the matrix product.'],
    degdiam:['A graph with three edges at every vertex.','Follow a first step, then a second.','Every vertex is at most two steps away.'],
    lineq:['Choose numbers from a finite interval.','Retain a set with no forbidden solution.','This weighted average falls outside the set.'],
    covering:['There are twenty-one pairs to cover.','Each triple covers three pairs.','Seven triples cover every pair.'],
    schur:['Start with the integers in order.','Separate them into three colour classes.','Every same-colour sum leaves its colour class.'],
    apfree_q:['Arithmetic wraps around modulo five.','Six selected points form a valid set.','A third term would lie outside the set.'],
    mols:['Every row and column contains each symbol.','Bring the two Latin squares together.','All nine ordered pairs are different.'],
    shannon:['Neighbours on a cycle can be confused.','Combine two channel positions into a word.','Each pair is separated in at least one position.'],
    trifference:['Arrange nine ternary codewords.','Choose any three of the words.','A column separates them as 0, 1 and 2.']
  };
  const draws={
    capset(f,p){
      const pts=[];for(let x=0;x<3;x++)for(let y=0;y<3;y++)for(let z=0;z<3;z++)pts.push([x,y,z]);
      const sc=Math.min(W*.25,H*.235),angle=.3+p*1.5,q=pts.map(v=>project(v.map(x=>x-1),angle,sc));
      pts.forEach((a,i)=>pts.forEach((b,j)=>{if(j>i&&a.reduce((s,v,k)=>s+Math.abs(v-b[k]),0)===1)line(q[i],q[j],palette.line,.17,.7);}));
      const origin=project([-1,-1,-1],angle,sc);
      [[1.2,-1,-1],[-1,1.2,-1],[-1,-1,1.2]].forEach((v,i)=>{const end=project(v,angle,sc);line(origin,end,palette.line,.36);text(['x','y','z'][i],end[0]+9,end[1]-5,12,palette.muted);});
      const amount=clamp((p-.12)/.64),count=Math.ceil(amount*9);
      pts.map((v,i)=>({v,q:q[i]})).sort((a,b)=>b.q[2]-a.q[2]).forEach(({v,q})=>{
        const j=f.points.findIndex(a=>a.every((x,k)=>x===v[k])),a=j<0?0:reveal(amount,j,9);
        dot(q,2.2*q[3],palette.muted,.3);if(a){dot(q,5.5*q[3],palette.gold,a);}
      });
      if(count)text('Selected vector: ('+f.points[Math.min(8,count-1)].join(', ')+')',W/2,H-17,12,palette.muted);
      return [count,'selected points'];
    },
    labs(f,p){
      const seq=f.answer,n=seq.length,scan=clamp((p-.16)/.73)*11,slide=1+Math.floor(scan)+smooth(clamp((scan%1)/.25)),size=Math.min(39,(W-38)/13),left=(W-size*13)/2,y1=H*.22,y2=H*.43;
      text('sequence',left,y1-16,12,palette.muted,'left');
      seq.forEach((v,i)=>{const x=left+i*size;rect(x+1,y1,size-2,size-3,palette.gold,v>0?.22:.04);text(v>0?'+':'−',x+size/2,y1+size*.45,Math.max(13,size*.48),v>0?palette.gold:palette.white);});
      const a=smooth((p-.1)*6),pairK=Math.min(12,Math.ceil(slide));
      for(let i=0;i<n-pairK;i++){const x=left+(i+slide)*size,tx=left+(i+pairK+.5)*size;rect(x+1,y2,size-2,size-3,palette.white,.065*a);text(seq[i]>0?'+':'−',x+size/2,y2+size*.45,Math.max(13,size*.48),palette.white,'center',a);line([tx,y1+size],[x+size/2,y2-4],palette.gold,.35*a);}
      text(`shift ${pairK} · correlation ${f.correlations[pairK-1]}`,W/2,y2+size+24,13,palette.gold,'center',a);
      const bw=Math.min(28,(W-65)/12),base=H*.86;
      line([W/2-bw*6,base],[W/2+bw*6,base],palette.line,.25);
      f.correlations.forEach((v,i)=>{const x=W/2+(i-5.5)*bw,show=i<pairK,h=Math.abs(v)*32;rect(x-bw*.27,base-h,bw*.54,Math.max(2,h),i===pairK-1?palette.gold:palette.white,show?.72:.1);text(i+1,x,base+15,12,palette.muted);});
      return [f.objective.toFixed(2),'merit factor'];
    },
    heilbronn(f,p){
      const side=Math.min(W*.67,H*.73),cx=W*.39,ox=cx-side/2,oy=(H-side)/2-8,pts=trianglePoints(4+p*23),r=minimumTriangle(pts),q=pts.map(([x,y])=>[ox+x/10000*side,oy+(1-y/10000)*side]);
      rect(ox,oy,side,side,palette.line,.35,true);
      for(let i=1;i<4;i++){line([ox+side*i/4,oy],[ox+side*i/4,oy+side],palette.line,.08);line([ox,oy+side*i/4],[ox+side,oy+side*i/4],palette.line,.08);}
      q.forEach((a,i)=>q.forEach((b,j)=>{if(j>i)line(a,b,palette.line,.08+.1*smooth(p*3),.7);}));
      const tri=r.indices.map(i=>q[i]);polygon(tri,palette.gold,.16);tri.forEach((a,i)=>line(a,tri[(i+1)%3],palette.gold,.95,1.5));
      ctx.save();ctx.beginPath();tri.forEach((v,i)=>i?ctx.lineTo(...v):ctx.moveTo(...v));ctx.closePath();ctx.clip();for(let y=oy-side;y<oy+side*2;y+=7)line([ox,y],[ox+side,y+side],palette.gold,.23,.6);ctx.restore();
      q.forEach((a,i)=>{dot(a,r.indices.includes(i)?4.5:3.4,r.indices.includes(i)?palette.gold:palette.white);text(i+1,a[0]+9,a[1]-8,12,palette.muted);});
      const values=[...r.areas].sort((a,b)=>a-b),barX=W*.82,barY=oy+15,barH=(side-30)/35,range=Math.max(...values);
      values.forEach((v,i)=>rect(barX,barY+i*barH,Math.max(2,v/range*(W*.12)),Math.max(1.5,barH-2),i===0?palette.gold:palette.line,i===0?.95:.26));
      text('smallest',barX+W*.055,oy-1,12,palette.gold);text('35 areas',barX+W*.055,oy+side+14,12,palette.muted);
      return [(100*r.area).toFixed(2)+'%','minimum area'];
    },
    spherical_code(f,p){
      const v=f.answer.map(a=>{const n=Math.hypot(...a);return a.map(x=>x/n);}),radius=Math.min(W*.3,H*.4),angle=.25+p*1.35;
      for(let lat=-2;lat<=2;lat++){const a=lat*Math.PI/6;let prev;for(let j=0;j<=80;j++){const b=j*TAU/80,q=project([Math.cos(a)*Math.cos(b),Math.sin(a),Math.cos(a)*Math.sin(b)],angle,radius);if(prev)line(prev,q,palette.line,.24,.7);prev=q;}}
      for(let i=0;i<6;i++){const b=i*Math.PI/6;let prev;for(let j=0;j<=80;j++){const a=j*TAU/80,q=project([Math.cos(a)*Math.cos(b),Math.sin(a),Math.cos(a)*Math.sin(b)],angle,radius);if(prev)line(prev,q,palette.line,.2,.7);prev=q;}}
      const growth=clamp((p-.08)/.58),q=v.map(a=>project(a,angle,radius));
      q.map((q,i)=>({q,i})).sort((a,b)=>b.q[2]-a.q[2]).forEach(({q,i})=>{const a=reveal(growth,i,12);dot(q,4.5*q[3],palette.gold,a*(q[2]>.25?.62:1));});
      let pair=[0,1],best=-2;for(let i=0;i<12;i++)for(let j=i+1;j<12;j++){const d=v[i].reduce((s,x,k)=>s+x*v[j][k],0);if(d>best){best=d;pair=[i,j];}}
      if(p>.67){const a=smooth((p-.67)*6),center=project([0,0,0],angle,radius);pair.forEach(i=>line(center,q[i],palette.gold,.45*a));let prev;for(let j=0;j<=32;j++){const vv=v[pair[0]].map((x,k)=>mix(x,v[pair[1]][k],j/32)),n=Math.hypot(...vv),qq=project(vv.map(x=>x/n),angle,radius);if(prev)line(prev,qq,palette.gold,a,2);prev=qq;}text((Math.acos(best)*180/Math.PI).toFixed(1)+'°',W/2,H*.49,font()+3,palette.gold,'center',a);}
      return [Math.ceil(growth*12),'directions'];
    },
    corners(f,p){
      const n=7,gap=Math.min((W-85)/6,(H-64)/6),ox=(W-gap*6)/2,oy=(H-gap*6)/2-8;
      const pos=([x,y])=>[ox+x*gap,oy+(6-y)*gap],progress=clamp((p-.06)/.63);
      for(let x=0;x<7;x++)for(let y=0;y<7;y++)dot(pos([x,y]),2,palette.muted,.23);
      f.answer.forEach((v,i)=>{const a=reveal(progress,i,f.answer.length);dot(pos(v),4.2,palette.gold,a);});
      if(p>.65){const a=smooth((p-.65)*5),q=f.missingCorner.map(pos);line(q[0],q[1],palette.gold,a,1.5);line(q[0],q[2],palette.gold,a,1.5);text('d',(q[0][0]+q[1][0])/2,q[0][1]+14,12,palette.gold,'center',a);text('d',q[0][0]-13,(q[0][1]+q[2][1])/2,12,palette.gold,'center',a);ring(q[2],8,palette.white,a*.65);bracket(q[2]);const d=Math.sign(q[1][0]-q[0][0])*10,e=Math.sign(q[2][1]-q[0][1])*10;line([q[0][0]+d,q[0][1]],[q[0][0]+d,q[0][1]+e],palette.gold,a);line([q[0][0]+d,q[0][1]+e],[q[0][0],q[0][1]+e],palette.gold,a);}
      return [Math.ceil(progress*f.answer.length),'selected points'];
    },
    matmul(f,p){
      const cell=Math.min(35,W*.075,H*.085),amount=clamp((p-.18)/.42),active=Math.min(6,Math.floor(amount*7));
      const matrix=(values,cx,cy,label,alpha=1,coeffs=null)=>{text(label,cx,cy-cell*1.48,13,palette.muted,'center',alpha);values.forEach((v,i)=>{const x=cx+(i%2-1)*cell,y=cy+(Math.floor(i/2)-1)*cell,on=coeffs&&coeffs[i]!==0;rect(x+1,y+1,cell-2,cell-2,on?palette.gold:palette.white,(on?.2:.06)*alpha);text(v,x+cell/2,y+cell/2,16,on?palette.gold:palette.white,'center',alpha);});};
      matrix(f.A,W*.31,H*.19,'A',1,p>.15?f.answer[active][0]:null);matrix(f.B,W*.69,H*.19,'B',1,p>.15?f.answer[active][1]:null);
      const step=Math.min(70,(W-32)/7),py=H*.44;
      f.products.forEach((v,i)=>{const x=W/2+(i-3)*step,a=reveal(amount,i,7),on=i===active;curve([W*.31,H*.19+cell],[x,py-17],26,palette.line,(on?.5:.12)*a);curve([W*.69,H*.19+cell],[x,py-17],26,palette.line,(on?.5:.12)*a);ring([x,py],Math.min(19,step*.42),palette.gold,(on?.55:.15)*a);text(v,x,py,16,palette.gold,'center',a);text('M'+(i+1),x,py+27,12,palette.muted,'center',a);});
      const formula=['(1 + 4) × (2 + 3) = 25','(3 + 4) × 2 = 14','1 × (1 − 3) = −2','4 × (1 − 2) = −4','(1 + 2) × 3 = 9','(3 − 1) × (2 + 1) = 6','(2 − 4) × (1 + 3) = −8'];
      text('M'+(active+1)+': '+formula[active],W/2,H*.61,13,palette.gold,'center',smooth((p-.18)*6));
      const result=smooth((p-.64)*6);matrix(f.C,W/2,H*.84,'C = AB',result);
      if(result){text('4 = M1 + M4 − M5 + M7',W/2,H*.98,12,palette.muted,'center',result);}
      return [7,'scalar products'];
    },
    degdiam(f,p){
      const r=Math.min(W*.32,H*.4),q=Array.from({length:10},(_,i)=>{const a=i%5*TAU/5-Math.PI/2+.18*p,rad=i<5?r:r*.45;return [W/2+rad*Math.cos(a),H*.46+rad*Math.sin(a)];}),d=distances(f.answer,0),wave=clamp((p-.23)*3.1,0,2.3);
      f.answer.forEach(([a,b])=>{line(q[a],q[b],palette.line,.3);if(d[a]===d[b])return;const from=d[a]<d[b]?a:b,to=from===a?b:a,k=clamp(wave-d[from]);if(k>0){const end=q[from].map((v,i)=>mix(v,q[to][i],k));line(q[from],end,palette.gold,.9,1.8);if(k<1)dot(end,3,palette.white);}});
      q.forEach((v,i)=>{const a=smooth((wave-d[i]+.2)*3);dot(v,5,palette.muted,.6);dot(v,5,palette.gold,a);if(a>.5)text(d[i],v[0]+12,v[1]-10,12,palette.gold,'center',a);});ring(q[0],11,palette.gold,.5);text('Shortest distance from the marked vertex',W/2,H*.95,12,palette.muted);
      return [10,'vertices · 2 hops'];
    },
    lineq(f,p){
      const n=27,gap=Math.min((W-70)/8,(H-60)/3),ox=(W-gap*8)/2,oy=H*.25,flatten=smooth((p-.66)*3.5),amount=clamp((p-.08)/.55);
      const pos=v=>[mix(ox+((v-1)%9)*gap,25+(v-1)*(W-50)/26,flatten),mix(oy+Math.floor((v-1)/9)*gap,H*.52,flatten)];
      if(flatten)line([25,H*.52],[W-25,H*.52],palette.line,.4*flatten);
      for(let i=1;i<=n;i++){const v=pos(i),ix=f.answer.indexOf(i),a=ix<0?0:reveal(amount,ix,f.answer.length);dot(v,3,palette.muted,.2);dot(v,4,palette.gold,a);if(flatten<.7||(W<450?f.missingAverage.includes(i)||i===1||i===27:ix>=0||i%5===0))text(i,v[0],v[1]+18,12,a?palette.gold:palette.muted,'center',a?1:.35);}
      if(flatten>.1){const [x,y,z]=f.missingAverage,a=pos(x),b=pos(y),c=pos(z);ctx.setLineDash([3,4]);curve([a[0],a[1]-9],[b[0],b[1]-9],-H*.3,palette.gold,flatten*.7);ctx.setLineDash([]);ring(c,9,palette.white,flatten*.7);bracket(c);text(`${x} + 2 × ${y} = 3 × ${z}`,W/2,H*.85,font()+2,palette.gold,'center',flatten);}
      return [Math.ceil(amount*f.answer.length),'selected integers'];
    },
    covering(f,p){
      const r=Math.min(W*.32,H*.38),q=Array.from({length:7},(_,i)=>[W/2+r*Math.cos(i*TAU/7-Math.PI/2),H*.46+r*Math.sin(i*TAU/7-Math.PI/2)]),num=clamp((p-.12)/.78*7,0,7),coverage=new Set();
      q.forEach((a,i)=>q.forEach((b,j)=>{if(j>i)line(a,b,palette.line,.1,.7);}));
      f.answer.forEach((block,i)=>{const a=smooth(num-i);if(a<=0)return;const pts=block.map(k=>q[k]);polygon(pts,palette.gold,a*(i===Math.ceil(num)-1?.18:.025));block.forEach((a,j)=>block.slice(j+1).forEach(b=>coverage.add([a,b].sort().join(','))));pts.forEach((v,j)=>line(v,pts[(j+1)%3],palette.gold,a*.65,1.1));});
      q.forEach((v,i)=>{dot(v,6,palette.gold);text(i+1,v[0]+(v[0]-W/2)*.14,v[1]+(v[1]-H*.46)*.14,14,palette.white);});
      return [coverage.size+'/21','pairs covered'];
    },
    schur(f,p){
      const colors=[palette.gold,palette.white,palette.soft],group=[0,0,0],size=Math.min(49,(W-75)/5,H*.18),amount=smooth((p-.2)*2),presence=clamp(p*3),q=[];
      f.answer.forEach((color,i)=>{const rank=group[color]++,start=[W/2+(i%7-3)*size*.86,H*.32+Math.floor(i/7)*size],end=[W/2+(rank-2)*size,H*.22+color*size*1.55],v=[mix(start[0],end[0],amount),mix(start[1],end[1],amount)],a=reveal(presence,i,13);q.push(v);rect(v[0]-size*.36,v[1]-size*.36,size*.72,size*.72,colors[color],(.11+.1*amount)*a);text(i+1,...v,font()+2,colors[color],'center',a);});
      if(amount>.5)for(let r=0;r<3;r++)text(['A','B','C'][r],W/2-size*2.8,H*.22+r*size*1.55,13,colors[r],'center',amount);
      if(p>.75){const a=smooth((p-.75)*5);curve([q[0][0],q[0][1]+size*.42],[q[1][0],q[1][1]-size*.42],20,palette.gold,a*.6);text('1 + 1 = 2 · different colours',W/2,H*.88,font(),palette.muted,'center',a);}
      return [13,'integers · 3 colours'];
    },
    apfree_q(f,p){
      const gap=Math.min((W-95)/4,(H-85)/4),ox=(W-gap*4)/2,oy=(H-gap*4)/2-12,pos=([x,y])=>[ox+x*gap,oy+(4-y)*gap],amount=clamp((p-.1)/.58);
      for(let x=0;x<5;x++)for(let y=0;y<5;y++){dot(pos([x,y]),2.5,palette.line,.26);if(y===0)text(x,ox+x*gap,oy+gap*4+22,12,palette.muted);}
      f.points.forEach((v,i)=>{const a=reveal(amount,i,6);dot(pos(v),5.5,palette.gold,a);});
      if(p>.72){const x=f.points[0],y=f.points[2],z=y.map((v,k)=>(2*v-x[k]+5)%5),a=smooth((p-.72)*6);ctx.setLineDash([3,5]);line(pos(x),pos(y),palette.gold,a*.6);line(pos(y),pos(z),palette.gold,a*.6);ctx.setLineDash([]);ring(pos(z),9,palette.white,a*.6);bracket(pos(z));}
      return [Math.ceil(amount*6),'selected points'];
    },
    mols(f,p){
      const merge=smooth((p-.38)/.38),base=Math.min(70,(W-50)/7,H*.19),cell=mix(base,Math.min(92,(W-65)/3,H*.26),merge),sep=mix(base*2,0,merge),top=H*.44-cell*1.5,colors=[palette.gold,palette.white,palette.soft];
      f.answer.forEach((square,k)=>{const cx=W/2+(k?sep:-sep),fade=1-merge;text(k?'L₂':'L₁',cx,top-18,14,k?palette.white:palette.gold,'center',fade);
        for(let r=0;r<3;r++)for(let c=0;c<3;c++){const x=cx+(c-1.5)*cell,y=top+r*cell,v=square[r][c];rect(x+2,y+2,cell-4,cell-4,colors[v],.12*(fade||0));text(v,x+cell/2,y+cell/2,Math.max(14,Math.min(28,cell*.44)),colors[v],'center',fade);}
      });
      if(merge){for(let r=0;r<3;r++)for(let c=0;c<3;c++){const x=W/2+(c-1.5)*cell,y=top+r*cell,a=f.answer[0][r][c],b=f.answer[1][r][c];rect(x+2,y+2,cell-4,cell-4,palette.gold,.1*merge);const fs=Math.max(14,Math.min(26,cell*.34));text(a,x+cell*.34,y+cell/2,fs,palette.gold,'center',merge);text(',',x+cell*.5,y+cell/2,fs,palette.muted,'center',merge);text(b,x+cell*.66,y+cell/2,fs,palette.white,'center',merge);}}
      text(merge>.5?'All ordered pairs are distinct':'Each row and column contains 0, 1 and 2',W/2,top+cell*3+35,font(),palette.muted);
      return [2,'orthogonal squares'];
    },
    shannon(f,p){
      const radius=Math.min(W*.16,H*.23),cy=H*.37,centres=[W*.27,W*.73],q=centres.map(cx=>Array.from({length:5},(_,i)=>[cx+radius*Math.cos(i*TAU/5-Math.PI/2),cy+radius*Math.sin(i*TAU/5-Math.PI/2)]));
      const step=Math.min(70,(W-28)/5),wordy=H*.84,count=clamp((p-.12)/.51*5,0,5),focus=Math.min(4,Math.floor(count)),compare=smooth((p-.69)*5);
      q.forEach((pts,k)=>{text('Position '+(k+1),centres[k],cy-radius-35,12,palette.muted);pts.forEach((a,i)=>{line(a,pts[(i+1)%5],palette.line,.35);dot(a,4.5,palette.white,.6);text(i,a[0]+(a[0]-centres[k])*.26,a[1]+(a[1]-cy)*.26,13,palette.muted);});});
      f.answer.forEach((word,i)=>{const a=smooth(count-i),x=W/2+(i-2)*step;if(!a)return;const selected=compare&&i<2;rect(x-step*.34,wordy-17,step*.68,34,palette.gold,(selected?.24:.09)*a);text(word.split('').join(' '),x,wordy,16,palette.gold,'center',a);if(i===focus||count===5&&i===4){for(let k=0;k<2;k++){const v=q[k][Number(word[k])];dot(v,5,palette.gold,a*(1-compare));curve(v,[x,wordy-21],40,palette.gold,.38*a*(1-compare));}}});
      if(compare){q.forEach((pts,k)=>{const a=pts[0],b=pts[k?2:1];line(a,b,k?palette.gold:palette.white,compare*(k?.95:.5),k?2:1);[a,b].forEach(v=>{ring(v,9,k?palette.gold:palette.white,compare*.6);dot(v,5,k?palette.gold:palette.white,compare);});text(k?'0 and 2':'0 and 1',centres[k],H*.65,12,k?palette.gold:palette.muted,'center',compare);text(k?'distinguishable':'confusable',centres[k],H*.7,12,k?palette.gold:palette.muted,'center',compare);});text('Compare 00 with 12',W/2,H*.96,12,palette.muted,'center',compare);}
      return [Math.ceil(count),'codewords'];
    },
    trifference(f,p){
      const cell=Math.min(46,(W-75)/4,(H-32)/9),ox=W/2-cell*2,oy=H*.47-cell*4.5,presence=clamp((p-.05)/.4),which=Math.min(3,Math.floor(clamp((p-.5)/.5)*4)),triple=f.triples[which],spot=smooth((p-.5)*8);
      f.answer.forEach((word,r)=>{const visible=reveal(presence,r,9),active=triple.includes(r),alpha=visible*(1-spot*.83*(active?0:1));word.split('').forEach((v,c)=>{const x=ox+c*cell,y=oy+r*cell;rect(x+2,y+2,cell-4,cell-4,palette.white,.035*alpha);if(active&&c===which)rect(x+2,y+2,cell-4,cell-4,palette.gold,.2*spot);text(v,x+cell/2,y+cell/2,Math.max(14,cell*.45),active&&c===which?palette.gold:palette.white,'center',alpha);});});
      if(spot){rect(ox+which*cell,oy,cell,9*cell,palette.gold,.6*spot,true);triple.forEach(r=>line([ox-17,oy+(r+.5)*cell],[ox-5,oy+(r+.5)*cell],palette.gold,spot,2));}
      return [9,'codewords · length 4'];
    }
  };
  function render(state){
    ctx=state.context;W=state.width;H=state.height;
    if(W<1||H<1)return;
    const p=still?1:state.progress;
    ctx.clearRect(0,0,W,H);ctx.lineCap='round';ctx.lineJoin='round';
    const result=draws[state.f.id](state.f,p),phase=p<.32?0:p<.72?1:2;
    state.figure.querySelector('[data-value]').textContent=String(result[0]);
    state.figure.querySelector('[data-unit]').textContent=result[1];
    state.figure.querySelector('[data-phase]').textContent=phaseWords[state.f.id][phase];
    state.figure.style.setProperty('--progress',p);
  }
  function tick(){
    frame=0;let moving=false;
    for(const state of states){
      const box=state.figure.getBoundingClientRect();
      const visible=box.top<innerHeight+100&&box.bottom>-100;
      if(!visible&&!state.dirty)continue;
      const picture=state.canvas.getBoundingClientRect();
      // Finish with the complete diagram centred, leaving a full reading interval.
      const start=innerHeight*.92,finish=Math.max(24,(innerHeight-picture.height)/2);
      state.target=clamp((start-picture.top)/(start-finish));
      const next=still?1:mix(state.progress,state.target,.28);
      state.progress=Math.abs(next-state.target)<.0003?state.target:next;
      state.figure.style.setProperty('--entry',still?1:smooth(clamp((innerHeight-box.top)/(innerHeight*.3))));
      if(visible||state.dirty)render(state);
      state.dirty=false;
      if(visible&&!still&&Math.abs(state.progress-state.target)>.0003)moving=true;
    }
    if(moving)frame=requestAnimationFrame(tick);
  }
  function schedule(){if(!frame&&!document.hidden)frame=requestAnimationFrame(tick);}
  function resize(){
    const dpr=Math.min(devicePixelRatio||1,2);
    for(const state of states){const box=state.canvas.getBoundingClientRect();if(state.width!==box.width||state.height!==box.height||state.dpr!==dpr){state.width=box.width;state.height=box.height;state.dpr=dpr;state.canvas.width=Math.round(box.width*dpr);state.canvas.height=Math.round(box.height*dpr);state.context.setTransform(dpr,0,0,dpr,0,0);state.dirty=true;}}
    schedule();
  }
  function anchor(){const id=location.hash.slice(1),target=id==='play'?root:document.getElementById(id);if(target&&(id.startsWith('family-')||id==='play'))window.scrollTo({top:target.getBoundingClientRect().top+scrollY-28,behavior:'instant'});schedule();}
  const motion=$('story-motion');
  function control(){motion.setAttribute('aria-pressed',String(still));motion.querySelector('[data-motion-label]').textContent=still?'Still illustrations':'Scroll animation';root.classList.toggle('is-still',still);states.forEach(s=>s.dirty=true);schedule();}
  motion.addEventListener('click',()=>{still=!still;control();});
  media.addEventListener('change',e=>{still=e.matches;control();});
  window.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',resize);document.addEventListener('visibilitychange',schedule);
  const observer=new ResizeObserver(resize);states.forEach(s=>observer.observe(s.canvas.parentElement));observer.observe($('leaderboard-body'));
  document.addEventListener('endless:results-ready',anchor);window.addEventListener('hashchange',schedule);
  control();resize();anchor();
})();
