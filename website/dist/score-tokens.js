(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const byId = id => document.getElementById(id);
  const format = value => Math.round(value).toLocaleString('en-US');
  const labelOffsets = {
    astra_tools: [12, -12], luna_tools: [12, -10],
    astra_high: [20, 3], astra_medium: [12, -6],
    fable: [12, -10], fable_high: [12, 8],
    deepseek_high: [-12, -24, 'end'], deepseek_low: [-12, -10, 'end'],
    luna_high: [12, -8], luna_medium: [12, 10],
    qwen38: [-10, 27, 'end'], qwen35: [-18, -20, 'end'],
    qwen9: [20, -2], qwen4: [-14, 7, 'end'],
  };
  function el(tag, attrs = {}, text) {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = text;
    return node;
  }
  window.EndlessScoreTokens = {
    render(data) {
      const host = byId('token-plot'), tooltip = byId('token-plot-tooltip');
      if (!host || !tooltip) return;
      const rows = [...data.rows].sort((a, b) => b.score - a.score);
      const modelCounts = new Map();
      for (const row of rows) modelCounts.set(row.model, (modelCounts.get(row.model) || 0) + 1);
      const xMax = Math.max(25000, Math.ceil(Math.max(...rows.map(r => r.mean_output_tokens)) / 25000) * 25000);
      const yMax = Math.max(150, Math.ceil(Math.max(...rows.map(r => r.score)) * 1.08 / 25) * 25);
      let active = null, frame = 0, geometry = [], svg, labelLayer, referenceY = 0, dimensions, groups = new Map();
      function updateSelection() {
        for (const [key, group] of groups) {
          group.classList.toggle('is-selected', key === active);
          group.setAttribute('aria-pressed', String(key === active));
        }
        if (labelLayer) drawLabels();
      }
      function positionTooltip() {
        const point = geometry.find(p => p.row.id === active);
        if (!point || !svg || tooltip.hidden) return;
        const box=svg.getBoundingClientRect(), outer=host.getBoundingClientRect();
        const x=point.x*box.width/dimensions.width, y=point.y*box.height/dimensions.height;
        const width=tooltip.offsetWidth, height=tooltip.offsetHeight, gap=16;
        let left=x+gap, top=y-32;
        if(left+width>host.clientWidth-8) {
          left=x-gap-width;
          if(left<8) {
            left=x-width/2;
            top=y-height-gap;
            if(top<8)top=y+gap;
          }
        }
        left=Math.max(8,Math.min(left,host.clientWidth-width-8));
        const minTop=Math.max(8,8-outer.top), maxTop=Math.min(host.clientHeight-8,innerHeight-outer.top-8)-height;
        top=Math.max(minTop,Math.min(top,Math.max(minTop,maxTop)));
        tooltip.style.left=left+'px'; tooltip.style.top=top+'px';
      }
      function showRow(id) {
        const row=rows.find(r=>r.id===id);
        if(!row)return;
        active=id;
        byId('token-tooltip-model').textContent=row.model;
        byId('token-tooltip-setting').textContent=`${row.effort} effort · ${row.track==='tool-assisted'?'Code + web':'No tools'}`;
        byId('token-tooltip-score').textContent=row.score.toFixed(2);
        byId('token-tooltip-usage').textContent=format(row.mean_output_tokens)+(row.token_usage_is_lower_bound?'*':'');
        const note=byId('token-tooltip-note');note.hidden=!row.token_usage_is_lower_bound;
        note.textContent=row.token_usage_is_lower_bound?'* Some usage was not reported; actual token use may be higher.':'';
        tooltip.hidden=false;updateSelection();positionTooltip();
      }
      function hideTooltip() {
        if(active===null&&tooltip.hidden)return;
        active=null;tooltip.hidden=true;updateSelection();
      }
      function drawLabels() {
        labelLayer.replaceChildren();
        const compact = host.clientWidth < 640;
        if (compact) return;
        const occupied = [], {width, height} = dimensions;
        const overlap = (a, b) => Math.max(0, Math.min(a.right,b.right)-Math.max(a.left,b.left)) * Math.max(0, Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
        for (const p of geometry) {
          const label = el('text', {'data-id':p.row.id,class:'plot-point-label' + (p.row.id === active ? ' is-selected' : '')});
          label.append(el('tspan',{x:0,y:0,class:'plot-label-model'},p.row.model));
          if (modelCounts.get(p.row.model) > 1 || p.row.track === 'tool-assisted') {
            const setting = p.row.effort + (p.row.track === 'tool-assisted' ? ' · code + web' : '');
            label.append(el('tspan',{x:0,y:14,class:'plot-label-setting'},setting));
          }
          labelLayer.append(label);
          const preferred = [...(labelOffsets[p.row.id] || [12,-12])];
          const rightOffset = p.row.token_usage_is_lower_bound ? 20 : 12;
          if (preferred[0] > 0) preferred[0] = Math.max(preferred[0],rightOffset);
          const candidates = [preferred];
          for (const dy of [-12, 4, -28, 22, -44, 38]) {
            candidates.push([rightOffset,dy,'start'],[-12,dy,'end']);
          }
          let best;
          for (const [dx,dy,anchor='start'] of candidates) {
            label.setAttribute('text-anchor',anchor);
            const box = label.getBBox();
            let x=p.x+dx, y=p.y+dy;
            x=Math.max(60-box.x,Math.min(x,width-12-box.x-box.width));
            y=Math.max(31-box.y,Math.min(y,height-72-box.y-box.height));
            const bounds={left:x+box.x-3,right:x+box.x+box.width+3,top:y+box.y-3,bottom:y+box.y+box.height+3};
            let penalty=occupied.reduce((sum,other)=>sum+overlap(bounds,other)*100,0);
            for (const point of geometry) {
              penalty+=overlap(bounds,{left:point.x-9,right:point.x+9,top:point.y-9,bottom:point.y+9})*100;
              if (point.row.token_usage_is_lower_bound) penalty+=overlap(bounds,{left:point.x+5,right:point.x+17,top:point.y-18,bottom:point.y-3})*100;
            }
            if (bounds.top<referenceY+5 && bounds.bottom>referenceY-5) penalty+=10000;
            penalty+=Math.abs(dx-preferred[0])+Math.abs(dy-preferred[1]);
            if (!best || penalty<best.penalty) best={x,y,anchor,bounds,penalty};
          }
          const {x,y,anchor,bounds}=best;
          label.setAttribute('text-anchor',anchor);
          label.setAttribute('transform',`translate(${x} ${y})`);
          occupied.push(bounds);
          const nearX=Math.max(bounds.left,Math.min(p.x,bounds.right));
          const nearY=Math.max(bounds.top,Math.min(p.y,bounds.bottom));
          if (Math.hypot(nearX-p.x,nearY-p.y)>16) labelLayer.insertBefore(el('line',{x1:p.x,y1:p.y,x2:nearX,y2:nearY,class:'plot-leader'}),label);
        }
      }
      function draw() {
        frame = 0;
        const width = host.clientWidth;
        if (width < 1) return;
        const compact = width < 640, height = compact ? 355 : 480;
        dimensions={width,height};
        const margin = {left:compact ? 40 : 52,right:compact ? 18 : 30,top:34,bottom:62};
        const plotWidth = width - margin.left - margin.right, plotHeight = height - margin.top - margin.bottom;
        const x = value => margin.left + value / xMax * plotWidth;
        const y = value => margin.top + (1 - value / yMax) * plotHeight;
        referenceY = y(100);
        svg = el('svg', {viewBox:`0 0 ${width} ${height}`,role:'group','aria-label':'Overall score versus mean reported output tokens per instance. Hover, focus or tap a point for details.'});
        const axes = el('g', {'aria-hidden':'true'});
        axes.append(el('text', {x:margin.left,y:16,class:'plot-axis-title'}, 'Overall score'));
        for (let value=0; value<yMax; value+=25) {
          const ref = value === 100;
          if (value % 50 === 0) axes.append(el('line', {x1:margin.left,y1:y(value),x2:width-margin.right,y2:y(value),class:ref?'plot-parity':'plot-grid'}));
          axes.append(el('text', {x:margin.left-10,y:y(value)+4,'text-anchor':'end',class:ref?'plot-tick plot-tick-reference':'plot-tick'}, value));
        }
        axes.append(el('text', {x:width-margin.right,y:y(100)-8,'text-anchor':'end',class:'plot-reference-label'}, '100 = reference'));
        const divisions = compact ? 4 : 5;
        for (let i=0;i<=divisions;i++) {
          const value=xMax*i/divisions;
          axes.append(el('line', {x1:x(value),y1:y(0),x2:x(value),y2:y(0)+5,class:'plot-axis'}));
          axes.append(el('text', {x:x(value),y:y(0)+22,'text-anchor':'middle',class:'plot-tick'}, value===0?'0':`${value/1000}k`));
        }
        axes.append(el('line', {x1:margin.left,y1:margin.top,x2:margin.left,y2:y(0),class:'plot-axis'}));
        axes.append(el('text', {x:margin.left+plotWidth/2,y:height-8,'text-anchor':'middle',class:'plot-axis-title'}, compact?'Mean output tokens / instance':'Mean output tokens per instance'));
        svg.append(axes);
        const points = el('g'); groups = new Map();
        geometry = rows.map(row => ({row,x:x(row.mean_output_tokens),y:y(row.score)}));
        for (const p of geometry) {
          const row=p.row, tool=row.track==='tool-assisted';
          const group=el('g', {class:`plot-point ${tool?'with-tools':'without-tools'}`,tabindex:0,role:'button','aria-pressed':String(row.id===active),'data-id':row.id,'aria-label':`${row.model}, ${row.effort}, ${tool?'code and web':'no tools'}. Score ${row.score.toFixed(2)}, ${format(row.mean_output_tokens)} mean output tokens${row.token_usage_is_lower_bound?', lower bound':''}.`});
          group.append(el('circle',{cx:p.x,cy:p.y,r:13,class:'plot-hit'}));
          group.append(el('circle',{cx:p.x,cy:p.y,r:8,class:'plot-selection'}));
          group.append(tool ? el('path',{d:`M${p.x} ${p.y-5.5}l5.5 5.5-5.5 5.5-5.5-5.5Z`,class:'plot-dot'}) : el('circle',{cx:p.x,cy:p.y,r:4.4,class:'plot-dot'}));
          if (row.token_usage_is_lower_bound) group.append(el('text',{x:p.x+7,y:p.y-6,class:'plot-star','aria-hidden':'true'},'*'));
          group.addEventListener('focus',()=>showRow(row.id));
          group.addEventListener('blur',hideTooltip);
          group.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();showRow(row.id);}if(event.key==='Escape'){event.preventDefault();hideTooltip();}});
          points.append(group); groups.set(row.id,group);
        }
        svg.append(points); labelLayer=el('g',{'aria-hidden':'true',class:'plot-labels'});svg.append(labelLayer);
        host.replaceChildren(svg,tooltip);updateSelection();positionTooltip();
      }
      function nearest(event) {
        if(!svg)return null;
        const box=svg.getBoundingClientRect(),px=(event.clientX-box.left)*dimensions.width/box.width,py=(event.clientY-box.top)*dimensions.height/box.height;
        let best=null,distance=host.clientWidth<640?24:18;
        for(const p of geometry){const d=Math.hypot(px-p.x,py-p.y);if(d<distance){best=p.row.id;distance=d;}}
        return best;
      }
      function schedule(){if(!frame)frame=requestAnimationFrame(draw);}
      host.addEventListener('pointermove',event=>{
        if(event.pointerType!=='mouse'||tooltip.contains(event.target))return;
        const id=nearest(event);
        if(id){if(id!==active||tooltip.hidden)showRow(id);}else hideTooltip();
      });
      host.addEventListener('pointerleave',event=>{if(event.pointerType==='mouse')hideTooltip();});
      host.addEventListener('click',event=>{
        if(tooltip.contains(event.target))return;
        const id=nearest(event);if(id)showRow(id);else hideTooltip();
      });
      document.addEventListener('pointerdown',event=>{if(!host.contains(event.target))hideTooltip();});
      document.addEventListener('keydown',event=>{if(event.key==='Escape')hideTooltip();});
      window.addEventListener('scroll',hideTooltip,{passive:true});
      new ResizeObserver(schedule).observe(host);
      if (document.fonts) document.fonts.ready.then(schedule);
      draw();
    }
  };
})();
