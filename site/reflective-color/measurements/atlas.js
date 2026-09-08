"use strict";

const C = { h:"#cf7520", v:"#2f96c9", diff:"#948a10", ref:"#7c8790",
  ink:"#f1f0e8", muted:"#a9b0b7", grid:"#27313a" };
const svgNS = "http://www.w3.org/2000/svg";
function el(name, attrs, parent, text){
  const node = document.createElementNS(svgNS, name);
  for (const [k,v] of Object.entries(attrs||{})) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  if (parent) parent.appendChild(node);
  return node;
}
function clear(node){ while(node.firstChild) node.removeChild(node.firstChild); }
const tooltip = document.getElementById("tooltip");
function showTip(evt, html){
  tooltip.innerHTML = html; tooltip.style.display = "block";
  tooltip.style.left = Math.min(evt.clientX + 14, innerWidth - 280) + "px";
  tooltip.style.top = (evt.clientY + 12) + "px";
}
function hideTip(){ tooltip.style.display = "none"; }
function fmt(x, d){ return Number(x).toFixed(d === undefined ? 3 : d); }
function fmtSigned(x, d){ const value=Number(x); return (value>=0?"+":"")+fmt(value,d); }
function plainText(html){ const node=document.createElement("span"); node.innerHTML=html; return node.textContent; }
function bindTip(node, html){
  node.setAttribute("tabindex","0"); node.setAttribute("role","img");
  node.setAttribute("aria-label",plainText(html));
  node.addEventListener("mousemove", evt => showTip(evt, html));
  node.addEventListener("mouseleave", hideTip);
  node.addEventListener("focus", ()=>{ const box=node.getBoundingClientRect();
    showTip({clientX:box.left+box.width/2,clientY:box.top+box.height/2},html); });
  node.addEventListener("blur", hideTip);
}
function describeSvg(svg, label){ svg.setAttribute("role","img"); svg.setAttribute("aria-label",label); }

function scale(domain, range){
  const [d0,d1] = domain, [r0,r1] = range, k = (r1-r0)/(d1-d0);
  const f = x => r0 + (x-d0)*k;
  f.domain = domain; f.range = range;
  return f;
}
function axis(svg, x, y, opts){
  const {xt, yt, xlabel, ylabel} = opts;
  for (const t of yt){
    el("line", {x1:x.range[0], x2:x.range[1], y1:y(t), y2:y(t),
      stroke:C.grid, "stroke-width":1}, svg);
    el("text", {x:x.range[0]-8, y:y(t)+4, fill:C.muted, "font-size":11,
      "text-anchor":"end"}, svg, fmt(t, opts.yd));
  }
  for (const t of xt){
    el("text", {x:x(t), y:y.range[0]+18, fill:C.muted, "font-size":11,
      "text-anchor":"middle"}, svg, fmt(t, opts.xd===undefined?0:opts.xd));
  }
  if (xlabel) el("text", {x:(x.range[0]+x.range[1])/2, y:y.range[0]+34,
    fill:C.muted, "font-size":11, "text-anchor":"middle"}, svg, xlabel);
  if (ylabel) el("text", {x:x.range[0], y:14, fill:C.muted, "font-size":11}, svg, ylabel);
}
function path(points){ return points.map((p,i)=>(i?"L":"M")+fmt(p[0],1)+" "+fmt(p[1],1)).join(""); }
function line(svg, xs, ys, x, y, attrs){
  return el("path", Object.assign({d: path(xs.map((v,i)=>[x(v), y(ys[i])])),
    fill:"none", "stroke-width":2, "stroke-linejoin":"round"}, attrs), svg);
}
function legend(id, items){
  const box = document.getElementById(id); box.innerHTML = "";
  for (const [color, label, dot] of items){
    const span = document.createElement("span");
    const sw = document.createElement("i");
    sw.className = dot ? "dotswatch" : "swatch"; sw.style.background = color;
    span.appendChild(sw); span.appendChild(document.createTextNode(label));
    box.appendChild(span);
  }
}
function crosshair(svg, x, y, wavelengths, series){
  const hit = el("rect", {x:x.range[0], y:16, width:x.range[1]-x.range[0],
    height:y.range[0]-16, fill:"transparent"}, svg);
  const marker = el("line", {y1:16, y2:y.range[0], stroke:C.ref,
    "stroke-width":1, "stroke-dasharray":"3 3", visibility:"hidden"}, svg);
  hit.addEventListener("mousemove", evt => {
    const box = svg.getBoundingClientRect();
    const px = (evt.clientX - box.left) * (svg.viewBox.baseVal.width / box.width);
    let best = 0, dist = Infinity;
    wavelengths.forEach((nm,i)=>{ const d = Math.abs(x(nm)-px); if (d<dist){dist=d;best=i;} });
    const nm = wavelengths[best];
    marker.setAttribute("x1", x(nm)); marker.setAttribute("x2", x(nm));
    marker.setAttribute("visibility", "visible");
    showTip(evt, "<b>"+nm+" nm</b><br>" + series.map(s =>
      '<span style="color:'+s.color+'">&#9632;</span> '+s.label+": "+fmt(s.values[best],3)).join("<br>"));
  });
  hit.addEventListener("mouseleave", ()=>{ marker.setAttribute("visibility","hidden"); hideTip(); });
}

let MAP_DATA = null;
let mapState = {pairId:"BLUE_GREEN", width:1, rowId:null, preferredOrder:null};
const MAP_COLORS = {BLACK:"#111820",WHITE:"#f1eee4",RED:"#d44239",YELLOW:"#e1c136",GREEN:"#3d8b55",BLUE:"#3569b8"};
const MAP_PHASE_BY_WIDTH = {1:0,2:0,3:2};
function mapPairLabel(pairId){return pairId.split("_").map(x=>x[0]+x.slice(1).toLowerCase()).join(" / ")}
function mapXyzPreview(xyz){
  const [x50,y50,z50]=xyz.map(value=>value/100),x65=.9555766*x50-.0230393*y50+.0631636*z50,y65=-.0282895*x50+1.0099416*y50+.0210077*z50,z65=.0122982*x50-.020483*y50+1.3299098*z50;
  const linear=[3.2404542*x65-1.5371385*y65-.4985314*z65,-.969266*x65+1.8760108*y65+.041556*z65,.0556434*x65-.2040259*y65+1.0572252*z65],encode=value=>value<=.0031308?12.92*value:1.055*Math.pow(value,1/2.4)-.055;
  return "#"+linear.map(value=>Math.round(Math.max(0,Math.min(1,encode(value)))*255).toString(16).padStart(2,"0")).join("");
}
function mapSequence(row){return row.quartet_order==="ABBA"?"H–V–V–H":"V–H–H–V"}
function mapRows(){return MAP_DATA.rows.filter(row=>row.pair_id===mapState.pairId&&row.cell_size_pixels===mapState.width)}
function mapChooseRow(rows,rowId,preferredOrder){return rows.find(row=>row.row_id===rowId)||rows.find(row=>row.quartet_order===preferredOrder)||rows[0]}
function mapSelected(){const rows=mapRows();return mapChooseRow(rows,mapState.rowId,mapState.preferredOrder)}
function mapRecurrence(row){return MAP_DATA.recurrence_records.find(r=>r.first.row_id===row.row_id||r.complement.row_id===row.row_id)}
function mapConstruction(row){if(row.cell_size_pixels===1)return "C1_P0";if(row.cell_size_pixels===3&&row.pair_id==="BLACK_YELLOW")return "C3_P2";return null}
function mapVector(values,digits=2){return values.map(value=>fmtSigned(value,digits)).join(" · ")}
function mapReadUrl(){
  const params=new URLSearchParams(location.search),pair=params.get("pair"),width=Number(params.get("width")),order=params.get("order");
  if(MAP_DATA.pair_order.includes(pair))mapState.pairId=pair;
  if([1,2,3].includes(width)&&MAP_DATA.rows.some(row=>row.pair_id===mapState.pairId&&row.cell_size_pixels===width))mapState.width=width;
  if(["ABBA","BAAB"].includes(order))mapState.preferredOrder=order;
  const match=mapRows().find(row=>row.quartet_order===order);if(match)mapState.rowId=match.row_id;
}
function mapWriteUrl(row){
  const params=new URLSearchParams(location.search);params.set("pair",row.pair_id);params.set("width",String(row.cell_size_pixels));params.set("order",row.quartet_order);
  history.replaceState(null,"",location.pathname+"?"+params.toString()+location.hash);
}
function mapRenderPattern(id,orientation,row){
  const target=document.getElementById(id),states=row.pair_id.split("_"),width=row.cell_size_pixels,phase=MAP_PHASE_BY_WIDTH[width];clear(target);
  for(let y=0;y<12;y++)for(let x=0;x<12;x++){
    const axisValue=orientation==="H"?y:x,cell=document.createElement("span");
    const stateIndex=((axisValue+phase)%(2*width))<width?0:1;
    cell.style.background=MAP_COLORS[states[stateIndex]];target.appendChild(cell);
  }
  target.setAttribute("aria-label",(orientation==="H"?"Horizontal":"Vertical")+" "+width+"-pixel "+mapPairLabel(row.pair_id)+" pattern");
}
function mapBuildControls(){
  const pair=document.getElementById("map-pair-select");clear(pair);
  for(const pairId of MAP_DATA.pair_order){const option=document.createElement("option");option.value=pairId;option.textContent=mapPairLabel(pairId);pair.appendChild(option)}
  pair.addEventListener("change",()=>{mapState.pairId=pair.value;mapState.rowId=null;renderMap()});
  const widths=document.getElementById("map-width-controls");clear(widths);
  for(const width of [1,2,3]){const button=document.createElement("button");button.type="button";button.textContent=width+" px";button.dataset.width=String(width);
    button.addEventListener("click",()=>{mapState.width=width;mapState.rowId=null;renderMap()});widths.appendChild(button)}
}
function mapRenderOrderControls(row){
  const box=document.getElementById("map-order-controls");clear(box);
  for(const candidate of mapRows()){
    const button=document.createElement("button");button.type="button";button.textContent=mapSequence(candidate);
    button.setAttribute("aria-pressed",String(candidate.row_id===row.row_id));button.addEventListener("click",()=>{mapState.rowId=candidate.row_id;mapState.preferredOrder=candidate.quartet_order;renderMap()});box.appendChild(button);
  }
}
function mapDrawAbsolute(row){
  const svg=document.getElementById("map-svg-absolute");clear(svg);
  describeSvg(svg,"All four retained reflectance spectra and their means. Solid lines are horizontal; dashed lines are vertical. Thin lines are individual readings and thick lines are means. Line colors are approximate measured-color previews.");
  const nm=MAP_DATA.wavelengths_nm,all=[...row.H.spectrum_percent,...row.V.spectrum_percent,...row.H.individual_readings.flatMap(reading=>reading.spectrum_percent),...row.V.individual_readings.flatMap(reading=>reading.spectrum_percent)],top=Math.max(1,Math.ceil(Math.max(...all)/5)*5),hColor=mapXyzPreview(row.H.xyz_d50),vColor=mapXyzPreview(row.V.xyz_d50);
  const width=Math.max(320,Math.min(980,svg.parentElement.clientWidth));svg.setAttribute("viewBox",`0 0 ${width} 330`);const x=scale([380,730],[52,width-20]),y=scale([0,top],[290,20]);axis(svg,x,y,{xt:width<500?[380,550,730]:[380,450,520,590,660,730],yt:[0,top/2,top],xlabel:"wavelength (nm)",ylabel:"reflectance factor (%)",yd:top<2?2:0});
  for(const reading of row.H.individual_readings)line(svg,nm,reading.spectrum_percent,x,y,{stroke:"#edf1f4","stroke-width":3.2,opacity:.38});
  for(const reading of row.V.individual_readings)line(svg,nm,reading.spectrum_percent,x,y,{stroke:"#edf1f4","stroke-width":3.2,opacity:.38,"stroke-dasharray":"4 3"});
  for(const reading of row.H.individual_readings)line(svg,nm,reading.spectrum_percent,x,y,{stroke:hColor,"stroke-width":1.4,opacity:.82});
  for(const reading of row.V.individual_readings)line(svg,nm,reading.spectrum_percent,x,y,{stroke:vColor,"stroke-width":1.4,opacity:.82,"stroke-dasharray":"4 3"});
  line(svg,nm,row.H.spectrum_percent,x,y,{stroke:"#edf1f4","stroke-width":4.5,opacity:.62});line(svg,nm,row.V.spectrum_percent,x,y,{stroke:"#edf1f4","stroke-width":4.5,opacity:.62,"stroke-dasharray":"7 4"});
  line(svg,nm,row.H.spectrum_percent,x,y,{stroke:hColor,"stroke-width":2.7});line(svg,nm,row.V.spectrum_percent,x,y,{stroke:vColor,"stroke-width":2.7,"stroke-dasharray":"7 4"});
  document.getElementById("map-preview-h").style.background=hColor;document.getElementById("map-preview-v").style.background=vColor;
  crosshair(svg,x,y,nm,[{label:"H mean",color:hColor,values:row.H.spectrum_percent},{label:"V mean",color:vColor,values:row.V.spectrum_percent}]);
}
function mapDrawDifference(row){
  const svg=document.getElementById("map-svg-difference");clear(svg);
  const nm=MAP_DATA.wavelengths_nm,values=row.difference.spectrum_pp,limit=Math.max(.05,Math.max(...values.map(Math.abs))*1.12);
  const width=Math.max(320,Math.min(980,svg.parentElement.clientWidth));svg.setAttribute("viewBox",`0 0 ${width} 330`);const x=scale([380,730],[52,width-20]),y=scale([-limit,limit],[290,20]);axis(svg,x,y,{xt:width<500?[380,550,730]:[380,450,520,590,660,730],yt:[-limit,0,limit],xlabel:"wavelength (nm)",ylabel:"H minus V (percentage points)",yd:limit<2?2:0});
  el("line",{x1:52,x2:x.range[1],y1:y(0),y2:y(0),stroke:C.ref,"stroke-width":1},svg);line(svg,nm,values,x,y,{stroke:C.diff,"stroke-width":2.5});
  crosshair(svg,x,y,nm,[{label:"H minus V",color:C.diff,values}]);
}
function mapRenderMetrics(row){
  document.getElementById("map-h-lab").textContent=mapVector(row.H.lab_d50);document.getElementById("map-h-xyz").textContent="XYZ "+row.H.xyz_d50.map(x=>fmt(x,2)).join(" · ");
  document.getElementById("map-v-lab").textContent=mapVector(row.V.lab_d50);document.getElementById("map-v-xyz").textContent="XYZ "+row.V.xyz_d50.map(x=>fmt(x,2)).join(" · ");
  document.getElementById("map-rms").textContent=fmt(row.difference.rms_pp,4);document.getElementById("map-de").textContent=fmt(row.difference.delta_e_2000,3);
  document.getElementById("map-dlab").textContent=mapVector(row.difference.lab_d50);document.getElementById("map-dxyz").textContent=mapVector(row.difference.xyz_d50);
  document.getElementById("map-movement").textContent="Horizontal moved "+fmt(row.H.movement_rms_pp,4)+" pp RMS (DeltaE00 "+fmt(row.H.movement_delta_e_2000,3)+"); vertical moved "+fmt(row.V.movement_rms_pp,4)+" pp RMS (DeltaE00 "+fmt(row.V.movement_delta_e_2000,3)+").";
}
function mapRenderContext(row){
  const recurrence=mapRecurrence(row),recurrenceBox=document.getElementById("map-recurrence");
  if(recurrence){recurrenceBox.innerHTML="<p>The first sequence was "+mapSequence(recurrence.first)+"; the second was "+mapSequence(recurrence.complement)+".</p><p>Spectral-direction similarity: <strong>"+fmt(recurrence.cosine,4)+"</strong>, where +1 means the same direction, 0 means no directional match, and −1 means opposite directions.</p><details><summary>More repeat details</summary><p>Difference between the two horizontal-minus-vertical spectra: "+fmt(recurrence.discrepancy.rms_pp,4)+" pp RMS. Second/first magnitude ratio: "+fmt(recurrence.magnitude_ratio,3)+"×.</p></details>"}
  else recurrenceBox.innerHTML="<p>No matching opposite-order recurrence analysis is included in this atlas snapshot.</p>";
  const construction=mapConstruction(row),crBox=document.getElementById("map-cr-context");clear(crBox);
  const appendParagraph=(parent,copy)=>{const p=document.createElement("p");p.textContent=copy;parent.appendChild(p)};
  appendParagraph(crBox,"The X-Rite i1Pro 3 touched the display and measured reflected light from its own illumination. The Colorimetry Research CR-250 viewed an externally illuminated display from a distance and measured spectral radiance.");
  if(!construction){appendParagraph(crBox,"This atlas snapshot does not include a CR-250 comparison for this stripe-width construction.");return}
  const relation=MAP_DATA.cr_context.survey_shape_context.find(item=>item.pair_id===row.pair_id&&item.construction_id===construction&&item.quartet_order===row.quartet_order);
  if(!relation){appendParagraph(crBox,"This atlas snapshot does not include a matching CR-250 comparison for this pattern and reading order.");return}
  const operand=relation.i1pro_operand;
  if(!operand?.row_id){appendParagraph(crBox,"The saved comparison does not identify the exact i1Pro 3 measurement it used, so the two routes are not presented as a matched comparison here.");return}
  const exactSelectedRow=operand.row_id===row.row_id,operandOccurrence=operand.row_id.split("::")[0],technicalParts=[];
  appendParagraph(crBox,"For this exact pixel construction and reading order, the two instruments' signed H-minus-V spectral changes had a direction similarity of "+fmt(relation.signed_spectrum_cosine,3)+". A value near +1 means the two changes point in a similar spectral direction, 0 means no directional match, and −1 means opposite directions.");
  appendParagraph(crBox,"This compares the shape and direction of the change, not its size. CR-250 radiance and i1Pro 3 reflectance factor remain different physical quantities.");
  appendParagraph(crBox,exactSelectedRow?"The i1Pro 3 measurement used for this comparison is the one shown above.":"The i1Pro 3 side comes from another retained measurement of the same exact H and V pixel buffers. Its identity is listed in the technical details below.");
  technicalParts.push("i1Pro 3 operand: "+operand.comparison_id+" from occurrence "+operandOccurrence+".");
  const repeated=MAP_DATA.cr_context.same_condition_and_followup.find(item=>item.pair_id===row.pair_id&&item.construction_id===construction);
  if(repeated){
    const firstMove=repeated.first_within_quartet_same_payload_movement_rms_native_units,secondMove=repeated.second_within_quartet_same_payload_movement_rms_native_units,betweenMove=repeated.between_row_absolute_endpoint_movement_rms_native_units;
    technicalParts.push("A later CR-250 quartet had signed-shape cosine "+fmt(repeated.signed_spectrum_cosine,3)+" and a second/first spectral-RMS magnitude ratio of "+fmt(repeated.magnitude_ratio_second_over_first,3)+" within CR-250 radiance units.");
    technicalParts.push("Within-quartet H/V movement was "+fmt(firstMove.H,7)+" / "+fmt(firstMove.V,7)+" in the first row and "+fmt(secondMove.H,7)+" / "+fmt(secondMove.V,7)+" in the later row. Between-row absolute endpoint movement is separate: H "+fmt(betweenMove.H,7)+", V "+fmt(betweenMove.V,7)+" in CR-250 radiance units.");
  }
  const geometry=MAP_DATA.cr_context.matched_geometry.find(item=>item.pair_id===row.pair_id&&item.construction_id===construction);
  if(geometry){
    technicalParts.push("The nominal-300 and exact-200 CR-250 sections had signed-shape cosine "+fmt(geometry.signed_spectrum_cosine,3)+" and a second/first spectral-RMS magnitude ratio of "+fmt(geometry.magnitude_ratio_second_over_first,3)+" within CR-250 radiance units.");
    const brackets=MAP_DATA.cr_context.reference_context.brackets,nominal=brackets.find(item=>item.condition_id==="OPERATOR_CORRECTED_NOMINAL_300_MM_PANEL_PLANE"),exact=brackets.find(item=>item.condition_id==="MEASURED_EXACT_200_MM_PANEL_PLANE");
    technicalParts.push("The physical reference level changed "+fmtSigned((nominal.absolute_spectral_rms_ratio_end_over_start-1)*100,1)+"% during nominal-300 and "+fmtSigned((exact.absolute_spectral_rms_ratio_end_over_start-1)*100,1)+"% during exact-200 while its spectral shape stayed nearly unchanged. This is chronology, placement, and illumination context, not normalization.");
  }
  if(row.pair_id==="BLACK_WHITE"&&construction==="C1_P0"){
    const context=MAP_DATA.cr_context.black_white_c1_i1pro_context,alternate=context.alternate_i1pro_operand,campaign=context.cr_relation_i1pro_operand;
    technicalParts.push("Two i1Pro 3 sessions measuring the same exact patterns did not point in the same spectral direction: "+alternate.quartet_order+" "+alternate.comparison_id+" to "+campaign.quartet_order+" "+campaign.comparison_id+" had cosine "+fmt(context.i1pro_to_i1pro_signed_spectrum_cosine,3)+". The sessions are shown separately, not combined into one result.");
  }
  if(row.pair_id==="BLACK_YELLOW"&&(construction==="C1_P0"||construction==="C3_P2")){
    const endpointRows=MAP_DATA.cr_context.black_yellow_endpoint_context.rows,surveyC1=endpointRows.find(item=>item.condition_id==="SURVEY_APPROX_PANEL_PLANE_260_280_MM"&&item.construction_id==="C1_P0"),surveyC3=endpointRows.find(item=>item.condition_id==="SURVEY_APPROX_PANEL_PLANE_260_280_MM"&&item.construction_id==="C3_P2");
    technicalParts.push("In the CR-250 survey, mean Y was C1 H/V "+fmt(surveyC1.mean_y.H,2)+" / "+fmt(surveyC1.mean_y.V,2)+" and C3 H/V "+fmt(surveyC3.mean_y.H,2)+" / "+fmt(surveyC3.mean_y.V,2)+". In that survey the C1 V endpoint lay near both C3 endpoints while C1 H was much higher. Width, phase, order, and history all changed between constructions.");
  }
  if(technicalParts.length){
    const details=document.createElement("details"),summary=document.createElement("summary"),body=document.createElement("div");summary.textContent="Technical comparison details";details.appendChild(summary);details.appendChild(body);
    for(const copy of technicalParts)appendParagraph(body,copy);crBox.appendChild(details);
  }
}
function renderMap(){
  const requestedOrder=mapState.preferredOrder,row=mapSelected();if(!row)return;
  const fellBack=Boolean(requestedOrder&&row.quartet_order!==requestedOrder);
  mapState.rowId=row.row_id;mapState.preferredOrder=row.quartet_order;
  document.getElementById("map-pair-select").value=mapState.pairId;
  for(const button of document.getElementById("map-width-controls").children){const width=Number(button.dataset.width);button.disabled=!MAP_DATA.rows.some(item=>item.pair_id===mapState.pairId&&item.cell_size_pixels===width);button.setAttribute("aria-pressed",String(width===mapState.width))}
  mapRenderOrderControls(row);mapWriteUrl(row);mapRenderPattern("map-pattern-h","H",row);mapRenderPattern("map-pattern-v","V",row);
  document.getElementById("map-selection-title").textContent=mapPairLabel(row.pair_id)+" · "+row.cell_size_pixels+" px · "+mapSequence(row);
  document.getElementById("map-selection-title").dataset.rowId=row.row_id;
  document.getElementById("map-selection-context").textContent="Two readings of each pattern in the order "+mapSequence(row);
  document.getElementById("map-selection-status").textContent=(fellBack?"The requested order is unavailable here; ":"")+"Selected "+mapPairLabel(row.pair_id)+", "+row.cell_size_pixels+" pixel, "+mapSequence(row)+".";
  mapRenderMetrics(row);mapDrawAbsolute(row);mapDrawDifference(row);mapRenderContext(row);
}

fetch("/reflective-color-display/measurement-investigation.json").then(r=>{if(!r.ok)throw new Error("Measurement data unavailable");return r.json()}).then(data=>{MAP_DATA=data;mapReadUrl();mapBuildControls();renderMap()}).catch(error=>{document.getElementById("map-selection-status").classList.remove("sr-only");document.getElementById("map-selection-status").textContent="The measurements could not be loaded. Please reload this page.";console.error(error)});
window.addEventListener("resize",()=>{if(MAP_DATA)renderMap()});