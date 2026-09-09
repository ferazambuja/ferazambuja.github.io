/* Presentation only: values and comparisons come from the selected result data. */
function atlasTraceColor(record, row) {
  const colors=['#65b7dc','#e6c645','#bd9ee9','#79cfa0','#ee9f80','#d2dce5'];
  const keys=record.means.length?record.means.map(m=>m.id):[...new Set(record.readings.map(r=>r.pattern))];
  const key=record.means.length?(row.group||row.id):row.pattern;
  return colors[Math.max(0,keys.indexOf(key))%colors.length];
}
function atlasPatternName(experiment, record, row) {
  const alias=experiment.display_labels?.patterns?.[row.pattern];
  if(alias)return alias;
  const readable=s=>String(s).replaceAll('_',' ').replaceAll('-',' ');
  const mean=record.means.some(m=>m.id===row.id&&m.pattern===row.pattern);
  if(mean){
    const members=record.readings.filter(r=>r.group===row.id);
    if(new Set(members.map(r=>r.pattern)).size===1)return atlasPatternName(experiment,record,members[0])+' mean';
    return readable(row.pattern);
  }
  const group=row.group||row.id;
  if(group==='H')return 'Horizontal';
  if(group==='V')return 'Vertical';
  if(/^(BLACK|WHITE|RED|YELLOW|GREEN|BLUE)$/i.test(row.pattern))return row.pattern.toLowerCase().replace(/^./,c=>c.toUpperCase());
  const tone=row.pattern.replace(/^FIXED-RENDERER-(NEXT-COVERAGE39|NEXT39|PILOT)-B-/, '');
  if(tone!==row.pattern)return tone==='N128'?'Neutral gray':tone.toLowerCase().replaceAll('-',' ').replace(/^./,c=>c.toUpperCase());
  return readable(row.pattern);
}
function atlasReadingName(record, row) {
  return 'Reading '+(record.readings.findIndex(r=>r.id===row.id)+1);
}
(() => {
  'use strict';
  const $=id=>document.getElementById(id), colors=['#65b7dc','#e6c645','#bd9ee9','#79cfa0','#ee9f80','#d2dce5'];
  const number=n=>n==null?'—':Math.abs(n)>0&&Math.abs(n)<.001?n.toExponential(2):Number(n).toLocaleString(undefined,{maximumFractionDigits:3});
  const triplet=v=>v?v.map(number).join(', '):'—';
  const node=(tag,text,attrs={})=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));return e;};
  const svgNode=(tag,attrs,text)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!=null)e.textContent=text;return e;};
  let data,experiment,record,selected=null;
  const patternName=row=>atlasPatternName(experiment,record,row);
  const recordName=r=>experiment.display_labels?.records?.[r.id]||r.label;
  const forecastName=e=>experiment.display_labels?.forecasts?.[e.label]||e.label;
  function options(id,values,value){const e=$(id);e.replaceChildren(...values.map(([v,t])=>node('option',t,{value:v})));e.value=values.some(v=>v[0]===value)?value:values[0][0];}
  function state(write=true){
    const u=new URL(location.href);
    if($('atlas-family').value==='stripes'){['experiment','comparison','pattern'].forEach(k=>u.searchParams.delete(k));}
    else{u.searchParams.set('experiment',experiment.id);u.searchParams.set('comparison',record.id);const p=$('atlas-reading-pattern').value;p?u.searchParams.set('pattern',p):u.searchParams.delete('pattern');}
    if(write)history.pushState({},'',u);
  }
  function plot(id,series,wavelengths,unit){
    const svg=$(id);svg.replaceChildren();const width=Math.max(320,Math.min(1100,svg.parentElement.clientWidth-32)),height=300;
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('aria-label',`${unit} versus wavelength, ${series.length} spectral traces`);
    const valid=series.filter(s=>Array.isArray(s.spectrum)&&s.spectrum.length===wavelengths.length);
    if(!valid.length){svg.append(svgNode('text',{x:16,y:40,fill:'#b3bdc4','font-size':15},'No spectrum is included for this selection.'));return;}
    let lo=0,hi=0;valid.forEach(s=>s.spectrum.forEach(v=>{lo=Math.min(lo,v);hi=Math.max(hi,v);}));const pad=(hi-lo||1)*.06;lo=lo<0?lo-pad:0;hi+=pad;
    const x=w=>70+(w-wavelengths[0])/(wavelengths.at(-1)-wavelengths[0])*(width-90),y=v=>250-(v-lo)/(hi-lo)*220;
    for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4;svg.append(svgNode('line',{x1:70,x2:width-20,y1:y(v),y2:y(v),stroke:'#3c464d'}),svgNode('text',{x:62,y:y(v)+5,fill:'#b3bdc4','font-size':14,'text-anchor':'end'},number(v)));}
    const ticks=width<500?3:6;
    for(let i=0;i<ticks;i++){const w=wavelengths[Math.round(i*(wavelengths.length-1)/(ticks-1))];svg.append(svgNode('text',{x:x(w),y:275,fill:'#b3bdc4','font-size':14,'text-anchor':'middle'},number(w)));}
    svg.append(svgNode('text',{x:width/2,y:298,fill:'#b3bdc4','font-size':14,'text-anchor':'middle'},'Wavelength (nm)'));
    valid.forEach(s=>{const p=svgNode('polyline',{points:s.spectrum.map((v,i)=>`${x(wavelengths[i])},${y(v)}`).join(' '),fill:'none',stroke:s.color,'stroke-width':s.mean?3:s.highlight?3:1.25,opacity:selected&&!s.highlight&&!s.mean?.3:s.mean?1:.8,'stroke-dasharray':s.dashed?'7 5':'none','data-reading':s.id||''});p.append(svgNode('title',{},s.name));svg.append(p);});
  }
  function render(){
    if(!record||$('atlas-additional').hidden)return;
    const pattern=$('atlas-reading-pattern').value, rows=record.readings.filter(r=>!pattern||r.pattern===pattern);
    const patterns=[...new Set(record.readings.map(r=>r.pattern))];
    const color=r=>atlasTraceColor(record,r);
    $('atlas-experiment-title').textContent=experiment.title;$('atlas-experiment-note').textContent=experiment.note;
    $('atlas-condition').textContent=[recordName(record),experiment.condition,`${rows.length} individual readings shown`].filter(Boolean).join(' · ');
    $('atlas-convention').textContent=experiment.convention;
    $('atlas-source').replaceChildren(...experiment.sources.map(s=>node('span',`${s.name} · SHA-256 ${s.sha256} `)));
    $('atlas-comparison-identity').textContent='Saved comparison: '+record.id;
    $('atlas-reading-identities').replaceChildren(...rows.map(r=>{const tr=node('tr');tr.append(node('td',atlasReadingName(record,r)),node('td',r.id),node('td',r.pattern));return tr;}));
    const dl=node('dl');dl.className='atlas-metrics';
    record.metrics.forEach(([name,value,unit])=>{const d=node('div');d.append(node('dt',name),node('dd',`${number(value)} ${unit}`));dl.append(d);});
    $('atlas-summary').replaceChildren(dl);
    $('atlas-means').hidden=!record.means.length;
    $('atlas-mean-rows').replaceChildren(...record.means.map(m=>{const tr=node('tr');tr.append(node('td',patternName(m)),node('td',triplet(m.xyz)),node('td',triplet(m.lab)));return tr;}));
    const series=rows.map(r=>({...r,color:color(r),name:atlasReadingName(record,r)+' · '+patternName(r),highlight:r.id===selected}));
    if(!pattern)record.means.forEach(m=>series.push({...m,color:color(m),name:patternName(m),mean:true}));
    const highlighted=rows.find(r=>r.id===selected);
    if(highlighted)highlighted.evaluations.filter(e=>e.predicted_spectrum).forEach((e,i)=>series.push({spectrum:e.predicted_spectrum,color:colors[(i+2)%colors.length],name:forecastName(e),dashed:true,mean:true}));
    $('atlas-spectrum-title').textContent=record.unit;
    plot('atlas-spectrum',series,record.wavelengths,record.unit);
    $('atlas-spectrum-caption').textContent=record.means.length&&!pattern?'Thin lines are individual readings; thick lines are the saved group means. Colors identify traces, not a simulation of display appearance.':'Each line is an individual measured spectrum. Selecting a reading highlights it; a dashed forecast appears only when a spectral prediction was saved.';
    $('atlas-series-key').replaceChildren(...(record.means.length&&!pattern?record.means:patterns.filter(p=>!pattern||p===pattern).map(p=>record.readings.find(r=>r.pattern===p))).map(m=>{const s=node('span');const key=node('i');key.style.color=color(m);s.append(key,document.createTextNode(patternName(m)));return s;}));
    $('atlas-difference-figure').hidden=!record.difference||!!pattern;
    if(record.difference&&!pattern){$('atlas-difference-title').textContent=`${record.difference.label} · signed spectrum difference`;plot('atlas-difference',[{spectrum:record.difference.spectrum,color:colors[2],mean:true,name:record.difference.label}],record.wavelengths,record.unit.startsWith('Reflectance')?'Difference (percentage points)':'Difference (CR-250 units)');}
    $('atlas-signed-color').textContent=record.difference?`${record.difference.label}: XYZ ${triplet(record.difference.xyz)}; Lab ${triplet(record.difference.lab)}.`:'';
    $('atlas-readings').replaceChildren(...rows.map(r=>{const tr=node('tr');tr.dataset.selected=r.id===selected;const cell=node('td'),b=node('button',atlasReadingName(record,r));b.addEventListener('click',()=>{selected=selected===r.id?null:r.id;render();});cell.append(b);tr.append(cell,node('td',patternName(r)+(r.context_role?' · '+r.context_role:'')),node('td',triplet(r.xyz)),node('td',triplet(r.lab)),node('td',r.temperature_c==null?'—':`${number(r.temperature_c)} °C`));return tr;}));
    const evaluations=rows.flatMap(r=>r.evaluations.map(e=>({r,e})));
    $('atlas-evaluations').hidden=!evaluations.length;
    $('atlas-evaluation-note').textContent=evaluations.some(x=>x.e.kind==='development')?'Development errors, not a fresh validation test. No pass/fail classification is added here.':'Output forecasts, desired image colors and familiar references are labeled separately. Results use each test’s chosen color-distance limit, not a universal visibility threshold. Signed vectors use the direction named in each row.';
    $('atlas-errors').replaceChildren(...evaluations.map(({r,e})=>{const tr=node('tr');tr.append(node('td',atlasReadingName(record,r)+' · '+patternName(r)),node('td',`${forecastName(e)} (${e.kind==='target'?'desired color':e.kind==='reference'?'reference':e.kind==='context'?'context forecast':e.kind==='development'?'development':'output forecast'})`),node('td',triplet(e.predicted_xyz)),node('td',number(e.delta_e)),node('td',number(e.limit)),node('td',`${e.direction}: ${triplet(e.residual_xyz)}`),node('td',e.status==='PASS'?'Within chosen limit':e.status==='FAIL'?'Outside chosen limit':e.status||'—'));return tr;}));
  }
  function chooseRecord(id,pattern){record=experiment.records.find(r=>r.id===id)||experiment.records[0];$('atlas-pattern').value=record.id;options('atlas-reading-pattern',[['','All patterns'],...[...new Set(record.readings.map(r=>r.pattern))].map(p=>[p,patternName(record.readings.find(r=>r.pattern===p))])],pattern||'');selected=null;render();}
  function chooseExperiment(id,comparison,pattern){experiment=data.experiments.find(e=>e.id===id);$('atlas-experiment').value=id;options('atlas-pattern',experiment.records.map(r=>[r.id,recordName(r)]),comparison);chooseRecord($('atlas-pattern').value,pattern);}
  function familyChanged(preferred,comparison,pattern){const f=$('atlas-family').value,legacy=f==='stripes';$('legacy-atlas').hidden=!legacy;$('atlas-additional').hidden=legacy;if(legacy){if(typeof renderMap==='function'&&typeof MAP_DATA!=='undefined'&&MAP_DATA)renderMap();return;}const candidates=data.experiments.filter(e=>e.family===f);options('atlas-experiment',candidates.map(e=>[e.id,e.title]),preferred);chooseExperiment($('atlas-experiment').value,comparison,pattern);}
  function restore(){const q=new URLSearchParams(location.search),e=data.experiments.find(e=>e.id===q.get('experiment'));$('atlas-family').value=e?e.family:'stripes';familyChanged(e?.id,q.get('comparison'),q.get('pattern'));}
  fetch('atlas-experiments.json').then(r=>{if(!r.ok)throw Error('Additional measurements unavailable');return r.json();}).then(d=>{
    if(d.schema!=='portfolio-measurement-atlas/1'||!d.experiments.length)throw Error('Unsupported atlas data');data=d;
    options('atlas-family',[['stripes','Stripe widths · all 15 color pairs'],...[...new Set(data.experiments.map(e=>e.family))].map(f=>[f,f])],'stripes');
    $('atlas-coverage').textContent=`75 stripe comparisons, plus ${data.experiments.length} experiment views covering arrangement, proportions, instruments, history and predictions.`;
    restore();$('atlas-family').addEventListener('change',()=>{familyChanged();state();});$('atlas-experiment').addEventListener('change',()=>{chooseExperiment($('atlas-experiment').value);state();});$('atlas-pattern').addEventListener('change',()=>{chooseRecord($('atlas-pattern').value);state();});$('atlas-reading-pattern').addEventListener('change',()=>{selected=null;render();state();});window.addEventListener('popstate',restore);window.addEventListener('resize',render);
  }).catch(error=>{$('atlas-coverage').textContent='The additional experiments could not be loaded. The stripe comparisons remain available.';console.error(error);});
})();
