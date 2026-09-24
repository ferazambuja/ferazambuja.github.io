"use strict";
function drawProcessMap(){
  const map=document.getElementById("process-map");if(!map)return;const svg=map.querySelector("svg"),bounds=map.getBoundingClientRect(),mobile=window.matchMedia("(max-width:640px)").matches;
  svg.querySelectorAll("path[data-process-edge]").forEach(path=>path.remove());
  svg.setAttribute("viewBox",`0 0 ${bounds.width} ${bounds.height}`);
  const nodes=new Map([...map.querySelectorAll("[data-process-node]")].map(node=>{
    const r=node.getBoundingClientRect();return [node.dataset.processNode,{node,left:r.left-bounds.left,right:r.right-bounds.left,top:r.top-bounds.top,bottom:r.bottom-bounds.top,x:r.left-bounds.left+r.width/2,y:r.top-bounds.top+r.height/2}];
  }));
  for(const [from,a] of nodes)for(const to of (a.node.dataset.processNext||"").split(" ").filter(Boolean)){
    const b=nodes.get(to);let d;
    if(from==="P"&&to==="Q"){
      const outer=bounds.width-4;d=`M${a.right},${a.y} H${outer} V${b.y} H${b.right}`;
    }else if(from==="A"&&to==="R"){
      d=`M${a.left},${a.y} H4 V${b.y} H${b.left}`;
    }else if(mobile&&from==="D"&&to==="V"){
      d=`M${a.left},${a.y} H10 V${b.y} H${b.left}`;
    }else if(mobile&&from==="F"&&to==="R"){
      d=`M${a.x},${a.bottom} V${a.bottom+15} H${b.x} V${b.top}`;
    }else if(Math.abs(a.y-b.y)<2){
      d=a.x<b.x?`M${a.right},${a.y} H${b.left}`:`M${a.left},${a.y} H${b.right}`;
    }else{
      const down=b.y>a.y,start=down?a.bottom:a.top,end=down?b.top:b.bottom,mid=(start+end)/2;
      d=`M${a.x},${start} V${mid} H${b.x} V${end}`;
    }
    const path=document.createElementNS("http://www.w3.org/2000/svg","path");path.dataset.processEdge=from+"-"+to;path.setAttribute("d",d);svg.appendChild(path);
  }
}
drawProcessMap();
if(typeof ResizeObserver!=="undefined"&&document.getElementById("process-map"))new ResizeObserver(drawProcessMap).observe(document.getElementById("process-map"));
else window.addEventListener("resize",drawProcessMap);
function setupDetailLinks(){
  function reveal(hash){
    let id;try{id=decodeURIComponent(hash.slice(1))}catch{return null}
    const target=document.getElementById(id);if(!target)return null;
    let detail=target.closest("details"),opened=false;
    while(detail){if(!detail.open){detail.open=true;opened=true}detail=detail.parentElement?.closest("details")}
    if(opened)requestAnimationFrame(()=>target.scrollIntoView());
    return target;
  }
  document.querySelectorAll('a[href^="#"]').forEach(link=>{
    link.addEventListener("click",()=>reveal(link.getAttribute("href")));
  });
  window.addEventListener("hashchange",()=>reveal(location.hash));
  reveal(location.hash);
}
setupDetailLinks();

const C = { h:"#cf7520", v:"#2f96c9", diff:"#948a10", ref:"#7c8790",
  ink:"#f1f0e8", muted:"#a9b0b7", grid:"#27313a" };
const VIEWS = [
  ["lab","1 · See measured color"],
  ["spectra","2 · Inspect the spectra"],
  ["time","3 · Check timing & repeats"],
  ["recipe","4 · Test the pixel-count idea"],
  ["uv","5 · See chromaticity"],
];
const VIEW_COPY = {
  spectra:{title:"What spectral detail does RMS summarize?",
    body:"Compare the horizontal and vertical spectra, then look at their difference beside two repeated measurements of the same patterns.",
    why:"The full curves show where the readings changed across visible wavelengths. One summary number cannot show that shape.",
    limit:"A repeated difference still does not tell us whether the pattern direction, the display, the meter, or another condition caused it."},
  time:{title:"Could measurement order be fooling us?",
    body:"See the four readings in the order they happened and how much time passed before each pattern was measured again.",
    why:"A slow change during the session could imitate a pattern difference, so timing and order have to stay visible.",
    limit:"This chart cannot untangle time from contact, flash, pressure, handling, or the display's recent history."},
  lab:{title:"What color did each B/G pattern measure as?",
    body:"Start with the XYZ and Lab coordinates for each measured color, then keep the direction of the horizontal-minus-vertical shift separate from the unsigned DeltaE00 distance.",
    why:"A future ICC-style model has to predict each absolute measured color. A recurring gap or one RMS number cannot do that job.",
    limit:"DeltaE00 does not say which direction the color moved. Here it is a color distance, not a visibility limit, uncertainty estimate, or model prediction error."},
  recipe:{title:"Could pixel counts alone explain it?",
    body:"Place several blue/green patterns between the solid-green and solid-blue measurements, then show what that simple line cannot describe.",
    why:"The investigation began because a model based only on blue and green amounts treated the two stripe patterns alike.",
    limit:"These points combine sessions. They do not reveal an image's true blue percentage or turn a pattern into a proven color recipe."},
  uv:{title:"Where did the colors land?",
    body:"See the chromaticity coordinates separately from brightness, with solid colors and media white shown for context.",
    why:"This makes color direction easier to see when a single distance number hides it.",
    limit:"Because the points come from different sessions, this chart cannot prove a mixing law, blue fraction, or display linearity."},
};
const SESSION_META = {
  "orientation-period-v2":{label:"Repeated H/V measurement",short:"Repeated H/V",
    context:"Each stripe pattern was measured twice in V-H-H-V order during one session."},
  "azimuth-0":{label:"Before meter rotation",short:"Before rotation",
    context:"The first H-V-V-H block, measured before rotating the meter."},
  "azimuth-90":{label:"After 90° meter rotation",short:"After 90°",
    context:"The meter was rotated and placed on the screen again. Any change can include rotation, placement, contact, pressure, timing, and display history."},
  "azimuth-zero-repeat":{label:"After returning the meter",short:"Return",
    context:"The meter was returned to its starting angle and the H-V-V-H block was measured again. This brackets the observation but does not identify its cause."},
};
const SESSION_VIEWS = new Set(["lab","spectra","time"]);
let DATA = null, view = "lab", session = "orientation-period-v2";

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
function plainText(html){ const node=document.createElement("span"); node.innerHTML=html.replace(/<br\b[^>]*>/gi," "); return node.textContent.replace(/\s+/g," ").trim(); }
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
    const px = (evt.clientX - box.left) * (980 / box.width);
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

function drawSpectra(){
  const s = DATA.sessions[session], nm = DATA.wavelengths_nm;
  const overlay = document.getElementById("svg-overlay"); clear(overlay);
  describeSvg(overlay,"Horizontal and vertical spectra for the selected measurement set, including both readings of each pattern.");
  const readings = s.readings;
  const all = [].concat(s.h_mean_spectrum_percent, s.v_mean_spectrum_percent);
  const x = scale([380,730],[52,960]);
  const y = scale([0, Math.ceil(Math.max(...all)/5)*5],[290,20]);
  axis(overlay, x, y, {xt:[380,450,520,590,660,730], yt:[0,10,20,30,40].filter(t=>t<=y.domain[1]),
    xlabel:"wavelength (nm)", ylabel:"reflectance factor (%)", yd:0});
  for (const id of ["BG-c1-H","BG-c1-H-repeat"])
    line(overlay, nm, readings[id].spectrum_percent, x, y,
      {stroke:C.h, "stroke-width":1, opacity:.45});
  for (const id of ["BG-c1-V","BG-c1-V-repeat"])
    line(overlay, nm, readings[id].spectrum_percent, x, y,
      {stroke:C.v, "stroke-width":1, opacity:.45});
  line(overlay, nm, s.h_mean_spectrum_percent, x, y, {stroke:C.h});
  line(overlay, nm, s.v_mean_spectrum_percent, x, y, {stroke:C.v});
  el("text", {x:x(700), y:y(s.h_mean_spectrum_percent[32])-8, fill:C.h,
    "font-size":12}, overlay, "H");
  el("text", {x:x(700), y:y(s.v_mean_spectrum_percent[32])+16, fill:C.v,
    "font-size":12}, overlay, "V");
  crosshair(overlay, x, y, nm, [
    {label:"H mean", color:C.h, values:s.h_mean_spectrum_percent},
    {label:"V mean", color:C.v, values:s.v_mean_spectrum_percent}]);
  legend("legend-spectra", [[C.h,"horizontal pattern · two readings and average"],
    [C.v,"vertical pattern · two readings and average"]]);

  const diff = document.getElementById("svg-diff"); clear(diff);
  describeSvg(diff,"Horizontal-minus-vertical spectral difference beside the change seen when each pattern was measured again.");
  const spread = [].concat(s.signed_h_minus_v_percentage_points,
    s.signed_h_repeat_difference, s.signed_v_repeat_difference);
  const m = Math.max(0.4, Math.max(...spread.map(Math.abs)) * 1.15);
  const x2 = scale([380,730],[52,960]), y2 = scale([-m, m],[260,20]);
  axis(diff, x2, y2, {xt:[380,450,520,590,660,730],
    yt:[-m, -m/2, 0, m/2, m], xlabel:"wavelength (nm)",
    ylabel:"signed difference (percentage points)", yd:2});
  el("line", {x1:52, x2:960, y1:y2(0), y2:y2(0), stroke:C.muted, "stroke-width":1}, diff);
  line(diff, nm, s.signed_h_repeat_difference, x2, y2,
    {stroke:C.ref, "stroke-width":1.5, opacity:.8});
  line(diff, nm, s.signed_v_repeat_difference, x2, y2,
    {stroke:C.ref, "stroke-width":1.5, opacity:.8, "stroke-dasharray":"5 4"});
  line(diff, nm, s.signed_h_minus_v_percentage_points, x2, y2, {stroke:C.diff, "stroke-width":2.5});
  crosshair(diff, x2, y2, nm, [
    {label:"H − V", color:C.diff, values:s.signed_h_minus_v_percentage_points},
    {label:"H repeat", color:C.ref, values:s.signed_h_repeat_difference},
    {label:"V repeat", color:C.ref, values:s.signed_v_repeat_difference}]);
  legend("legend-diff", [[C.diff,"horizontal average minus vertical average"],
    [C.ref,"change when horizontal repeated"],[C.ref,"change when vertical repeated · dashed"]]);
  document.getElementById("spectra-summary").textContent =
    "For this session, the average wavelength-by-wavelength separation was " +
    fmt(s.effect_spectral_rms_percentage_points,4) + " percentage points RMS. " +
    "That describes the size of the spectral gap, not what either color was or " +
    "which direction it moved. Their measured-media-white-relative DeltaE00 color separation was " +
    fmt(s.effect_delta_e_2000_media_white_relative,4) + ". Repeating horizontal changed by " +
    fmt(s.repeat_spectral_rms_percentage_points.H,4) + " pp RMS and repeating vertical " +
    "by " + fmt(s.repeat_spectral_rms_percentage_points.V,4) +
    " pp RMS. The repeat values are context, not a detection threshold.";
}

function drawRecipe(){
  const svg = document.getElementById("svg-recipe"); clear(svg);
  describeSvg(svg,"Blue and green pattern measurements projected onto the line between solid blue and solid green; this is not a measurement of true pixel fraction.");
  const x = scale([-0.04,1.04],[60,950]), y = scale([-0.04,1.04],[336,22]);
  axis(svg, x, y, {xt:[0,.25,.5,.75,1], yt:[0,.25,.5,.75,1],
    xlabel:"nominal blue fraction", ylabel:"measured fraction equivalent (solid axis)",
    xd:2, yd:2});
  el("line", {x1:x(0), y1:y(0), x2:x(1), y2:y(1), stroke:C.muted,
    "stroke-width":1.5, "stroke-dasharray":"6 5"}, svg);
  const shapes = {"quarter-tile":"circle","error-diffused":"rect",
    "solid":"diamond","checkerboard":"triangle"};
  function mark(cx, cy, kind, color, tip){
    let node;
    if (kind === "rect") node = el("rect",{x:cx-5,y:cy-5,width:10,height:10,fill:color},svg);
    else if (kind === "diamond") node = el("path",
      {d:"M"+cx+" "+(cy-6)+"L"+(cx+6)+" "+cy+"L"+cx+" "+(cy+6)+"L"+(cx-6)+" "+cy+"Z",fill:color},svg);
    else if (kind === "triangle") node = el("path",
      {d:"M"+cx+" "+(cy-6)+"L"+(cx+6)+" "+(cy+5)+"L"+(cx-6)+" "+(cy+5)+"Z",fill:color},svg);
    else node = el("circle",{cx,cy,r:5.5,fill:color},svg);
    node.setAttribute("stroke", "#11151a"); node.setAttribute("stroke-width", "1.5");
    node.style.cursor = "default";
    bindTip(node,tip);
  }
  for (const p of DATA.recipe_points){
    const kind = p.label.startsWith("quarter") ? "circle" :
      p.label.startsWith("error") ? "rect" :
      p.label.startsWith("checker") ? "triangle" : "diamond";
    mark(x(p.nominal_blue_fraction), y(p.measured_fraction_equivalent), kind, C.ref,
      "<b>"+p.label+"</b><br>measured t = "+fmt(p.measured_fraction_equivalent,4)+
      "<br>off-axis "+fmt(p.off_axis_spectral_rms_percentage_points,3)+" pp");
  }
  for (const [name, s] of Object.entries(DATA.sessions)){
    mark(x(0.5), y(s.h_v_fraction_equivalents.H), "circle", C.h,
      "<b>H · "+SESSION_META[name].label+"</b><br>t = "+fmt(s.h_v_fraction_equivalents.H,4)+
      "<br><small>"+name+"</small>");
    mark(x(0.5), y(s.h_v_fraction_equivalents.V), "circle", C.v,
      "<b>V · "+SESSION_META[name].label+"</b><br>t = "+fmt(s.h_v_fraction_equivalents.V,4)+
      "<br><small>"+name+"</small>");
  }
  legend("legend-recipe", [[C.ref,"earlier blue/green construction measurements",true],
    [C.h,"horizontal patterns at requested 50% blue",true],
    [C.v,"vertical patterns at requested 50% blue",true]]);

  const off = document.getElementById("svg-offaxis"); clear(off);
  describeSvg(off,"The part of each pattern's measured spectrum that the simple solid-blue-to-solid-green line does not describe.");
  const pts = DATA.recipe_points.filter(p=>p.off_axis_spectral_rms_percentage_points>0);
  const xo = scale([-0.6, pts.length-0.4],[60,950]);
  const yo = scale([0, Math.max(...pts.map(p=>p.off_axis_spectral_rms_percentage_points))*1.2],[180,18]);
  for (const t of [0, yo.domain[1]/2, yo.domain[1]])
    el("text",{x:52,y:yo(t)+4,fill:C.muted,"font-size":11,"text-anchor":"end"},off,fmt(t,2));
  pts.forEach((p,i)=>{
    const bar = el("rect",{x:xo(i)-26, y:yo(p.off_axis_spectral_rms_percentage_points),
      width:52, height:yo(0)-yo(p.off_axis_spectral_rms_percentage_points),
      rx:4, fill:C.ref},off);
    bindTip(bar,"<b>"+p.label+"</b><br>"+
      fmt(p.off_axis_spectral_rms_percentage_points,3)+" pp off-axis");
    el("text",{x:xo(i), y:200, fill:C.muted, "font-size":11,
      "text-anchor":"middle"}, off, p.label.replace(" 25%"," 25").replace(" 75%"," 75").replace(" 50%"," 50"));
  });
}

function drawTime(){
  const s = DATA.sessions[session], svg = document.getElementById("svg-time"); clear(svg);
  describeSvg(svg,"The selected measurement set's four blue-green readings in presentation order against seconds since the first reading.");
  const order = s.presentation_order;
  const seconds = order.map(id => s.readings[id].seconds_since_first);
  const ts = order.map(id => s.readings[id].fraction_equivalent_along_solid_chord);
  const pad = Math.max(...seconds) * 0.08 + 2;
  const x = scale([-pad, Math.max(...seconds)+pad],[60,950]);
  const lo = Math.min(...ts), hi = Math.max(...ts), m = (hi-lo)*0.35 + 0.004;
  const y = scale([lo-m, hi+m],[250,25]);
  axis(svg, x, y, {xt:seconds, yt:[lo, (lo+hi)/2, hi],
    xlabel:"seconds since first quartet reading", ylabel:"fraction equivalent", xd:0, yd:3});
  line(svg, seconds, ts, x, y, {stroke:C.grid, "stroke-width":1});
  order.forEach((id,i)=>{
    const horizontal = id.includes("-H");
    const dot = el("circle",{cx:x(seconds[i]), cy:y(ts[i]), r:7,
      fill:horizontal?C.h:C.v, stroke:"#11151a","stroke-width":1.5},svg);
    bindTip(dot,"<b>"+id+"</b><br>"+fmt(seconds[i],1)+" s · t = "+fmt(ts[i],4));
    el("text",{x:x(seconds[i]), y:y(ts[i])-13, fill:C.muted,"font-size":11,
      "text-anchor":"middle"},svg, id.replace("BG-c1-","").replace("-repeat","′"));
  });
  legend("legend-time", [[C.h,"horizontal pattern",true],[C.v,"vertical pattern",true]]);
  const hSpan = Math.abs(s.readings["BG-c1-H-repeat"].seconds_since_first -
    s.readings["BG-c1-H"].seconds_since_first);
  const vSpan = Math.abs(s.readings["BG-c1-V-repeat"].seconds_since_first -
    s.readings["BG-c1-V"].seconds_since_first);
  document.getElementById("time-summary").textContent =
    "The horizontal pattern was repeated after " + fmt(hSpan,1) +
    " seconds; the vertical pattern after " + fmt(vSpan,1) +
    " seconds. Because those intervals differ, the two repeat changes are context for the " +
    "session, not directly comparable noise limits.";
}

function drawUv(){
  const svg = document.getElementById("svg-uv"); clear(svg);
  describeSvg(svg,"CIE u-prime v-prime chromaticity positions for the blue-green measurements, earlier patterns, and media-white context.");
  const pts = [];
  for (const p of DATA.recipe_points)
    pts.push({u:p.uv.u_prime, v:p.uv.v_prime, Y:p.uv.Y, label:p.label, color:C.ref});
  for (const [name, s] of Object.entries(DATA.sessions)){
    for (const id of Object.keys(s.readings)){
      const r = s.readings[id];
      pts.push({u:r.uv.u_prime, v:r.uv.v_prime, Y:r.uv.Y,
        label:id+" · "+SESSION_META[name].label, color:id.includes("-H")?C.h:C.v});
    }
    pts.push({u:s.media_white_uv.u_prime, v:s.media_white_uv.v_prime,
      Y:s.media_white_uv.Y, label:"media white · "+SESSION_META[name].label, color:C.ink});
  }
  const us = pts.map(p=>p.u), vs = pts.map(p=>p.v);
  const padU = (Math.max(...us)-Math.min(...us))*0.12 + 0.002;
  const padV = (Math.max(...vs)-Math.min(...vs))*0.12 + 0.002;
  const x = scale([Math.min(...us)-padU, Math.max(...us)+padU],[60,950]);
  const y = scale([Math.min(...vs)-padV, Math.max(...vs)+padV],[386,24]);
  axis(svg, x, y, {xt:[x.domain[0]+padU, (x.domain[0]+x.domain[1])/2, x.domain[1]-padU],
    yt:[y.domain[0]+padV, (y.domain[0]+y.domain[1])/2, y.domain[1]-padV],
    xlabel:"u′", ylabel:"v′", xd:3, yd:3});
  for (const p of pts){
    const dot = el("circle",{cx:x(p.u), cy:y(p.v), r:p.color===C.ink?5:6.5,
      fill:p.color, stroke:"#11151a","stroke-width":1.5, opacity:p.color===C.ref?.8:1},svg);
    bindTip(dot,"<b>"+p.label+"</b><br>u′ "+fmt(p.u,4)+" · v′ "+
      fmt(p.v,4)+" · Y "+fmt(p.Y,2));
  }
  legend("legend-uv", [[C.h,"horizontal readings · all sessions",true],
    [C.v,"vertical readings · all sessions",true],[C.ref,"earlier constructions and solid colors",true],
    [C.ink,"media white",true]]);
}

function drawLab(){
  const svg = document.getElementById("svg-lab"); clear(svg);
  describeSvg(svg,"DeltaE00 color distance between horizontal and vertical, plus the change seen when each pattern was measured again.");
  const names = Object.keys(DATA.sessions);
  const groups = names.map(n => {
    const s = DATA.sessions[n];
    return [s.effect_delta_e_2000_media_white_relative,
      s.repeat_delta_e_2000_media_white_relative.H,
      s.repeat_delta_e_2000_media_white_relative.V];
  });
  const top = Math.max(...groups.flat())*1.2;
  const x = scale([0, names.length],[60,950]), y = scale([0, top],[212,18]);
  for (const t of [0, top/2, top])
    el("text",{x:52,y:y(t)+4,fill:C.muted,"font-size":11,"text-anchor":"end"},svg,fmt(t,1));
  names.forEach((n,g)=>{
    const base = x(g)+18, w = (x(1)-x(0)-52)/3;
    [["effect",C.diff],["H repeat",C.ref],["V repeat",C.ref]].forEach(([label,color],i)=>{
      const value = groups[g][i];
      const bar = el("rect",{x:base+i*(w+2), y:y(value), width:w,
        height:y(0)-y(value), rx:4, fill:color,
        opacity:label==="V repeat"?.6:1},svg);
      bindTip(bar,"<b>"+SESSION_META[n].label+"</b><br>"+label+
        " ΔE00 = "+fmt(value,4)+"<br><small>"+n+"</small>");
    });
    el("text",{x:x(g)+ (x(1)-x(0))/2, y:232, fill:C.muted,"font-size":11,
      "text-anchor":"middle"},svg,SESSION_META[n].short);
  });
  legend("legend-lab", [[C.diff,"horizontal-versus-vertical DeltaE00"],
    [C.ref,"change when the same pattern was repeated"]]);

  const selected = DATA.sessions[session];
  const h = selected.mean_color.H, v = selected.mean_color.V;
  const dl = selected.signed_h_minus_v_lab_media_white_relative;
  const dx = selected.signed_h_minus_v_xyz_d50;
  const colorTable = document.getElementById("color-table");
  function vectorCells(values, signed){
    return values.map(value=>"<td>"+(signed?fmtSigned(value,3):fmt(value,3))+"</td>").join("");
  }
  colorTable.innerHTML = "<tr><th>measurement</th><th>X</th><th>Y</th><th>Z</th><th>L*</th><th>a*</th><th>b*</th></tr>"+
    "<tr><td><strong>Horizontal mean</strong></td>"+vectorCells(h.xyz_d50,false)+vectorCells(h.lab_media_white_relative,false)+"</tr>"+
    "<tr><td><strong>Vertical mean</strong></td>"+vectorCells(v.xyz_d50,false)+vectorCells(v.lab_media_white_relative,false)+"</tr>"+
    "<tr><td><strong>H minus V</strong></td>"+vectorCells(dx,true)+vectorCells(dl,true)+"</tr>";

  const table = document.getElementById("lab-table");
  table.innerHTML = "<tr><th>measurement set</th><th>H−V spectrum difference (pp RMS)</th>"+
    "<th>H repeat change (pp RMS)</th><th>V repeat change (pp RMS)</th>"+
    "<th>H/V ΔE00</th></tr>" +
    names.map(n=>{
      const s = DATA.sessions[n];
      return "<tr><td><strong>"+SESSION_META[n].label+"</strong></td><td>"+
      fmt(s.effect_spectral_rms_percentage_points,4)+
      "</td><td>"+fmt(s.repeat_spectral_rms_percentage_points.H,4)+
      "</td><td>"+fmt(s.repeat_spectral_rms_percentage_points.V,4)+
      "</td><td>"+fmt(s.effect_delta_e_2000_media_white_relative,4)+"</td></tr>";}).join("");
}

const DRAW = {spectra:drawSpectra, recipe:drawRecipe, time:drawTime, uv:drawUv, lab:drawLab};

function updateSelectedSession(){
  const s=DATA.sessions[session], meta=SESSION_META[session];
  const h=s.mean_color.H, v=s.mean_color.V,
    dl=s.signed_h_minus_v_lab_media_white_relative;
  document.getElementById("selected-session-title").textContent=meta.label;
  document.getElementById("selected-session-context").textContent=meta.context;
  document.getElementById("selected-session-id").textContent="";
  document.getElementById("metric-effect-rms").textContent=
    fmt(s.effect_spectral_rms_percentage_points,4)+" pp";
  document.getElementById("metric-effect-de").textContent=
    fmt(s.effect_delta_e_2000_media_white_relative,4);
  document.getElementById("metric-h-lab").textContent="Lab "+h.lab_media_white_relative.map(x=>fmt(x,2)).join(" · ");
  document.getElementById("metric-h-xyz").textContent="XYZ "+h.xyz_d50.map(x=>fmt(x,2)).join(" · ");
  document.getElementById("metric-v-lab").textContent="Lab "+v.lab_media_white_relative.map(x=>fmt(x,2)).join(" · ");
  document.getElementById("metric-v-xyz").textContent="XYZ "+v.xyz_d50.map(x=>fmt(x,2)).join(" · ");
  document.getElementById("metric-delta-lab").textContent="Delta Lab "+dl.map(x=>fmtSigned(x,2)).join(" · ");
  document.getElementById("metric-repeat-context").textContent=
    "H "+fmt(s.repeat_spectral_rms_percentage_points.H,4)+" · V "+
    fmt(s.repeat_spectral_rms_percentage_points.V,4)+" pp RMS";
}
function updateViewGuide(){
  const copy=VIEW_COPY[view];
  document.getElementById("view-guide-title").textContent=copy.title;
  document.getElementById("view-guide-body").textContent=copy.body;
  document.getElementById("view-guide-why").textContent=copy.why;
  document.getElementById("view-guide-limit").textContent=copy.limit;
}
function render(){
  for (const [id] of VIEWS)
    document.getElementById("view-"+id).classList.toggle("active", id===view);
  const showsSession=SESSION_VIEWS.has(view);
  document.getElementById("sessions").style.display=showsSession?"flex":"none";
  document.getElementById("session-picker-label").style.display=showsSession?"block":"none";
  updateSelectedSession(); updateViewGuide();
  DRAW[view]();
}
function buildControls(){
  const tabs = document.getElementById("tabs");
  for (const [id,label] of VIEWS){
    const b = document.createElement("button");
    b.textContent = label;
    b.setAttribute("aria-pressed", String(id===view));
    b.setAttribute("aria-controls","view-"+id);
    b.addEventListener("click", ()=>{ view = id;
      for (const other of tabs.children)
        other.setAttribute("aria-pressed", String(other===b));
      render(); });
    tabs.appendChild(b);
  }
  const pills = document.getElementById("sessions");
  for (const name of Object.keys(DATA.sessions)){
    const b = document.createElement("button");
    b.textContent = SESSION_META[name].label;
    b.title = SESSION_META[name].context;
    b.setAttribute("aria-pressed", String(name===session));
    b.setAttribute("aria-label",SESSION_META[name].label);
    b.addEventListener("click", ()=>{ session = name;
      for (const other of pills.children)
        other.setAttribute("aria-pressed", String(other===b));
      render(); });
    pills.appendChild(b);
  }
}
let MAP_DATA = null;
let mapState = {pairId:"BLUE_GREEN", width:1, rowId:null, preferredOrder:null};
const MAP_COLORS = {BLACK:"#111820",WHITE:"#f1eee4",RED:"#d44239",YELLOW:"#e1c136",GREEN:"#3d8b55",BLUE:"#3569b8"};
const MAP_PHASE_BY_WIDTH = {1:0,2:0,3:2};
function mapPairLabel(pairId){return pairId.split("_").map(x=>x[0]+x.slice(1).toLowerCase()).join(" / ")}
function mapRenderHookPatterns(){
  for(const orientation of ["h","v"]){
    const target=document.getElementById("hook-pattern-"+orientation);if(!target)continue;clear(target);
    for(let y=0;y<8;y++)for(let x=0;x<18;x++){
      const cell=document.createElement("span"),index=orientation==="h"?y:x;
      cell.style.background=index%2?"#4f9b69":"#3569b8";
      cell.dataset.nativeState=index%2?"GREEN":"BLUE";
      cell.setAttribute("aria-hidden","true");
      cell.textContent=index%2?"G":"B";cell.style.color=index%2?"#101820":"#fff";
      target.appendChild(cell);
    }
  }
}
function mapXyzPreview(xyz){
  const [x50,y50,z50]=xyz.map(value=>value/100),x65=.9555766*x50-.0230393*y50+.0631636*z50,y65=-.0282895*x50+1.0099416*y50+.0210077*z50,z65=.0122982*x50-.020483*y50+1.3299098*z50;
  const linear=[3.2404542*x65-1.5371385*y65-.4985314*z65,-.969266*x65+1.8760108*y65+.041556*z65,.0556434*x65-.2040259*y65+1.0572252*z65],encode=value=>value<=.0031308?12.92*value:1.055*Math.pow(value,1/2.4)-.055;
  return "#"+linear.map(value=>Math.round(Math.max(0,Math.min(1,encode(value)))*255).toString(16).padStart(2,"0")).join("");
}
function renderMeasuredComparisonPreviews(){
  document.querySelectorAll(".measured-color-card[data-xyz-d50]").forEach(card=>{
    const xyz=card.dataset.xyzD50.split(",").map(Number),swatch=card.querySelector("i");
    if(swatch&&xyz.length===3&&xyz.every(Number.isFinite))swatch.style.background=mapXyzPreview(xyz);
  });
}
function mapRenderPairOverview(){
  const body=document.getElementById("pair-comparison-body");if(!body)return;clear(body);
  const rows=MAP_DATA.rows.filter(row=>row.cell_size_pixels===1).sort((a,b)=>b.difference.delta_e_2000-a.difference.delta_e_2000);
  const rmsRank=new Map([...rows].sort((a,b)=>b.difference.rms_pp-a.difference.rms_pp).map((row,index)=>[row.row_id,index+1]));
  for(const row of rows){
    const tr=document.createElement("tr");tr.dataset.pairId=row.pair_id;tr.dataset.rowId=row.row_id;tr.dataset.deltaE=String(row.difference.delta_e_2000);tr.dataset.deltaL=String(row.difference.lab_d50[0]);tr.dataset.rmsPp=String(row.difference.rms_pp);
    const pair=document.createElement("th");pair.setAttribute("scope","row");
    const link=document.createElement("a");link.className="pair-reading-link";link.href="/reflective-color-display/measurements/?pair="+encodeURIComponent(row.pair_id)+"&width=1&order="+row.quartet_order;
    link.setAttribute("aria-label","Open readings: "+mapPairLabel(row.pair_id)+", one-pixel stripes, "+row.quartet_order);
    const pairBox=document.createElement("div");pairBox.className="pair-label";
    const states=row.pair_id.split("_");
    states.forEach((state,index)=>{if(index){const separator=document.createElement("span");separator.className="pair-separator";separator.textContent="/";pairBox.appendChild(separator)}const chip=document.createElement("span");chip.className="native-name";chip.dataset.state=state;chip.textContent=state[0]+state.slice(1).toLowerCase();pairBox.appendChild(chip)});
    const instructions=document.createElement("div");instructions.className="pair-instructions";instructions.setAttribute("aria-hidden","true");
    for(const orientation of ["H","V"]){const label=document.createElement("span"),glyph=document.createElement("img");label.textContent=orientation;glyph.dataset.orientation=orientation;glyph.setAttribute("src","/reflective-color-display/assets/pattern-previews/"+row.pair_id.toLowerCase()+"-c1-"+orientation.toLowerCase()+"-crop.png");glyph.alt=orientation+" crop of the exact retained digital pixel map";glyph.loading="lazy";label.appendChild(glyph);instructions.appendChild(label)}
    link.append(pairBox,instructions);pair.appendChild(link);
    const order=document.createElement("td");order.dataset.metric="order";order.textContent=row.quartet_order.split("").map(letter=>letter==="A"?"H":"V").join("–");order.title=row.quartet_order;
    const previews=document.createElement("td"),previewBox=document.createElement("div");previewBox.className="preview-pair";
    for(const orientation of ["H","V"]){const group=document.createElement("div"),label=document.createElement("span"),swatch=document.createElement("span");label.className="preview-label";label.textContent=orientation;swatch.className="preview-chip";swatch.style.background=mapXyzPreview(row[orientation].xyz_d50);swatch.setAttribute("aria-label",orientation+" approximate sRGB preview derived from measured XYZ");group.append(label,swatch);previewBox.appendChild(group)}
    previews.appendChild(previewBox);
    const metric=(name,value)=>{const td=document.createElement("td");td.dataset.metric=name;td.className="metric-value";td.textContent=value;return td;};
    const distance=metric("delta-e",fmt(row.difference.delta_e_2000,2)),rms=metric("rms-pp",fmt(row.difference.rms_pp,3));
    for(const [cell,rank] of [[distance,rows.indexOf(row)+1],[rms,rmsRank.get(row.row_id)]]){const label=document.createElement("small");label.dataset.rank=String(rank);label.textContent="Rank "+rank+" of "+rows.length;cell.appendChild(label);}
    const deltaL=row.difference.lab_d50[0],direction=metric("delta-l",fmtSigned(deltaL,2)),meaning=document.createElement("small");meaning.textContent=deltaL>0?"H lighter":deltaL<0?"V lighter":"Equal mean lightness";direction.appendChild(meaning);
    const movement=document.createElement("td");movement.dataset.metric="movement";
    for(const orientation of ["H","V"]){const value=document.createElement("div");value.dataset.orientation=orientation;value.textContent=orientation+" "+fmt(row[orientation].movement_rms_pp,3);movement.appendChild(value)}
    tr.append(pair,order,previews,distance,rms,direction,movement);body.appendChild(tr);
  }
}
function mapRenderWidthOverview(){
  if(!document.getElementById("native-width-overview"))return;
  const svg=document.getElementById("native-width-overview");clear(svg);
  describeSvg(svg,"Every native color pair with its measured one-, two-, and three-pixel horizontal-minus-vertical spectral RMS observations. Horizontal position uses a logarithmic scale; paired observations are joined only to show the two reading orders.");
  const rows=MAP_DATA.rows,values=rows.map(row=>row.difference.rms_pp).filter(value=>value>0),minimum=Math.min(...values),maximum=Math.max(...values);
  const left=260,right=1020,top=58,rowStep=39,bottom=top+MAP_DATA.pair_order.length*rowStep;
  const log=value=>Math.log10(value),x=scale([Math.floor(log(minimum)),Math.ceil(log(maximum))],[left,right]);
  const ticks=[];for(let power=Math.floor(log(minimum));power<=Math.ceil(log(maximum));power++)ticks.push(10**power);
  el("text",{x:left,y:24,fill:C.muted,"font-size":13},svg,"spectrum difference (percentage points RMS, logarithmic scale)");
  for(const tick of ticks){const px=x(log(tick)),label=tick<.01?tick.toFixed(3):tick<.1?tick.toFixed(2):tick<1?tick.toFixed(1):String(tick);el("line",{x1:px,x2:px,y1:38,y2:bottom,stroke:C.grid,"stroke-width":1},svg);el("text",{x:px,y:bottom+24,fill:C.muted,"font-size":11,"text-anchor":"middle"},svg,label);}
  const colors={1:"#5550cf",2:"#168ba6",3:"#d77812"}; const focusPoints=[];
  MAP_DATA.pair_order.forEach((pairId,index)=>{
    const y=top+index*rowStep;el("line",{x1:20,x2:1065,y1:y+19,y2:y+19,stroke:C.grid,"stroke-width":1},svg);
    el("text",{x:20,y:y+5,fill:C.ink,"font-size":12,"font-weight":750},svg,mapPairLabel(pairId).toUpperCase());
    for(const width of [1,2,3]){
      const candidates=rows.filter(row=>row.pair_id===pairId&&row.cell_size_pixels===width).sort((a,b)=>a.quartet_order.localeCompare(b.quartet_order));
      const offset=(width-2)*8,points=candidates.map(row=>({row,px:x(log(row.difference.rms_pp))}));
      if(points.length>1)el("line",{x1:points[0].px,x2:points[points.length-1].px,y1:y+offset,y2:y+offset,stroke:colors[width],"stroke-width":3},svg);
      for(const point of points){const dot=el("circle",{cx:point.px,cy:y+offset,r:5,fill:colors[width],stroke:"#0a0c0f","stroke-width":1},svg);bindTip(dot,"<b>"+mapPairLabel(pairId)+" · "+width+" px · "+point.row.quartet_order+"</b><br>"+fmt(point.row.difference.rms_pp,4)+" pp RMS");dot.setAttribute("tabindex",focusPoints.length?"-1":"0");focusPoints.push(dot);}
    }
  });
  svg.setAttribute("role","group");
  focusPoints.forEach((dot,index)=>dot.addEventListener("keydown",event=>{
    const steps={ArrowRight:1,ArrowDown:1,ArrowLeft:-1,ArrowUp:-1};
    let next;
    if(event.key==="Home")next=0;else if(event.key==="End")next=focusPoints.length-1;
    else if(event.key in steps)next=(index+steps[event.key]+focusPoints.length)%focusPoints.length;else return;
    event.preventDefault();dot.setAttribute("tabindex","-1");focusPoints[next].setAttribute("tabindex","0");focusPoints[next].focus();
  }));
}
function mapRenderMetricExample(pairId,svgId,rmsId,deId,movementId){
  if(!document.getElementById(svgId))return;
  const row=MAP_DATA.rows.find(item=>item.pair_id===pairId&&item.cell_size_pixels===1),svg=document.getElementById(svgId);clear(svg);
  describeSvg(svg,mapPairLabel(pairId)+" horizontal and vertical mean reflectance factor spectra above their signed difference.");
  const width=Math.max(280,Math.round(svg.getBoundingClientRect().width)),left=42,right=width-20,narrow=width<500;
  svg.setAttribute("viewBox",`0 0 ${width} 370`);
  const nm=MAP_DATA.wavelengths_nm,all=[...row.H.spectrum_percent,...row.V.spectrum_percent],top=Math.max(1,Math.ceil(Math.max(...all)/5)*5);
  const x=scale([380,730],[left,right]),y=scale([0,top],[190,55]),ticks=narrow?[380,550,730]:[380,450,520,590,660,730];
  axis(svg,x,y,{xt:ticks,yt:[0,top/2,top],ylabel:"reflectance factor (%)",yd:top<2?2:0});
  const hColor=mapXyzPreview(row.H.xyz_d50),vColor=mapXyzPreview(row.V.xyz_d50);
  for(const [key,color,dash] of [["H",hColor,null],["V",vColor,"7 4"]]){
    line(svg,nm,row[key].spectrum_percent,x,y,{stroke:"#edf1f4","stroke-width":4.8,opacity:.55,...(dash?{"stroke-dasharray":dash}:{})});
    line(svg,nm,row[key].spectrum_percent,x,y,{stroke:color,"stroke-width":2.7,...(dash?{"stroke-dasharray":dash}:{})});
  }
  el("text",{x:left,y:32,fill:C.ink,"font-size":12},svg,"Solid: H · Dashed: V");
  const limit=Math.max(.05,Math.max(...row.difference.spectrum_pp.map(Math.abs))*1.12),yd=scale([-limit,limit],[330,255]);
  el("text",{x:left,y:238,fill:C.ink,"font-size":12},svg,"H minus V (percentage points)");
  for(const tick of [-limit,0,limit]){
    el("line",{x1:left,x2:right,y1:yd(tick),y2:yd(tick),stroke:C.grid,"stroke-width":1},svg);
    el("text",{x:left-6,y:yd(tick)+4,fill:C.muted,"font-size":10,"text-anchor":"end"},svg,fmt(tick,1));
  }
  line(svg,nm,row.difference.spectrum_pp,x,yd,{stroke:C.diff,"stroke-width":2.5});
  for(const tick of ticks)el("text",{x:x(tick),y:346,fill:C.muted,"font-size":10,"text-anchor":"middle"},svg,String(tick));
  el("text",{x:(left+right)/2,y:365,fill:C.muted,"font-size":11,"text-anchor":"middle"},svg,"wavelength (nm)");
  document.getElementById(rmsId).textContent=fmt(row.difference.rms_pp,2)+" pp RMS";document.getElementById(deId).textContent="DeltaE00 "+fmt(row.difference.delta_e_2000,2);
  document.getElementById(movementId).textContent="H "+fmt(row.H.movement_rms_pp,3)+" pp · V "+fmt(row.V.movement_rms_pp,3)+" pp RMS";
}
function mapRenderFeaturedExample(){
  if(!document.querySelector("[data-featured-row]"))return;
  const row=MAP_DATA.rows.find(item=>item.row_id===document.querySelector("[data-featured-row]").dataset.featuredRow),svg=document.getElementById("featured-spectrum-native");clear(svg);
  describeSvg(svg,"Mean horizontal and vertical black-yellow reflectance spectra above their signed horizontal-minus-vertical spectrum. Line colors are approximate previews derived from the measured XYZ values.");
  const width=Math.max(280,Math.round(svg.getBoundingClientRect().width)),left=40,right=width-18,narrow=width<500,ticks=narrow?[380,550,730]:[380,450,520,590,660,730];
  svg.setAttribute("viewBox",`0 0 ${width} 430`);
  const nm=MAP_DATA.wavelengths_nm,all=[...row.H.spectrum_percent,...row.V.spectrum_percent],top=Math.max(1,Math.ceil(Math.max(...all)/5)*5),hColor=mapXyzPreview(row.H.xyz_d50),vColor=mapXyzPreview(row.V.xyz_d50),x=scale([380,730],[left,right]),y=scale([0,top],[220,65]);
  axis(svg,x,y,{xt:ticks,yt:[0,top/2,top],ylabel:"reflectance factor (%)",yd:top<2?2:0});
  line(svg,nm,row.H.spectrum_percent,x,y,{stroke:"#edf1f4","stroke-width":5,opacity:.55});line(svg,nm,row.V.spectrum_percent,x,y,{stroke:"#edf1f4","stroke-width":5,opacity:.55,"stroke-dasharray":"8 5"});
  line(svg,nm,row.H.spectrum_percent,x,y,{stroke:hColor,"stroke-width":3});line(svg,nm,row.V.spectrum_percent,x,y,{stroke:vColor,"stroke-width":3,"stroke-dasharray":"8 5"});
  el("line",{x1:left,x2:left+23,y1:37,y2:37,stroke:hColor,"stroke-width":4},svg);el("text",{x:left+30,y:41,fill:C.ink,"font-size":11},svg,"horizontal");
  el("line",{x1:left+125,x2:left+148,y1:37,y2:37,stroke:vColor,"stroke-width":4,"stroke-dasharray":"7 4"},svg);el("text",{x:left+155,y:41,fill:C.ink,"font-size":11},svg,"vertical");
  const values=row.difference.spectrum_pp,limit=Math.max(.05,Math.max(...values.map(Math.abs))*1.12),yd=scale([-limit,limit],[390,292]);
  el("text",{x:left,y:270,fill:C.ink,"font-size":narrow?11:13,"font-weight":750},svg,narrow?"Horizontal minus vertical (pp)":"Signed horizontal minus vertical spectrum (pp)");
  for(const tick of [-limit,0,limit]){el("line",{x1:left,x2:right,y1:yd(tick),y2:yd(tick),stroke:C.grid,"stroke-width":1},svg);el("text",{x:left-8,y:yd(tick)+4,fill:C.muted,"font-size":10,"text-anchor":"end"},svg,fmt(tick,1));}
  line(svg,nm,values,x,yd,{stroke:C.diff,"stroke-width":3});
  for(const tick of ticks)el("text",{x:x(tick),y:410,fill:C.muted,"font-size":10,"text-anchor":"middle"},svg,String(tick));
  el("text",{x:(left+right)/2,y:426,fill:C.muted,"font-size":10,"text-anchor":"middle"},svg,"wavelength (nm)");
  document.getElementById("featured-h-preview").style.background=hColor;document.getElementById("featured-v-preview").style.background=vColor;
  const lab=value=>value.map((item,index)=>index?fmtSigned(item,2):fmt(item,2)).join(" · ");
  document.getElementById("featured-lab").textContent="H "+lab(row.H.lab_d50)+" · V "+lab(row.V.lab_d50);
  document.getElementById("featured-de").textContent="DeltaE00 "+fmt(row.difference.delta_e_2000,3);
  document.getElementById("featured-rms").textContent=fmt(row.difference.rms_pp,3)+" pp RMS";
  document.getElementById("featured-dlab").textContent=row.difference.lab_d50.map(value=>fmtSigned(value,2)).join(" · ");
  document.getElementById("featured-movement").textContent="H "+fmt(row.H.movement_rms_pp,3)+" pp · V "+fmt(row.V.movement_rms_pp,3)+" pp RMS";
}
function mapRenderNativeFigures(){
  mapRenderHookPatterns();mapRenderFeaturedExample();mapRenderWidthOverview();
  mapRenderMetricExample("BLUE_GREEN","native-metric-blue-green","native-bg-rms","native-bg-de","native-bg-movement");
  mapRenderMetricExample("RED_GREEN","native-metric-red-green","native-rg-rms","native-rg-de","native-rg-movement");
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
  const x=scale([380,730],[52,960]),y=scale([0,top],[290,20]);axis(svg,x,y,{xt:[380,450,520,590,660,730],yt:[0,top/2,top],xlabel:"wavelength (nm)",ylabel:"reflectance factor (%)",yd:top<2?2:0});
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
  const x=scale([380,730],[52,960]),y=scale([-limit,limit],[290,20]);axis(svg,x,y,{xt:[380,450,520,590,660,730],yt:[-limit,0,limit],xlabel:"wavelength (nm)",ylabel:"H minus V (percentage points)",yd:limit<2?2:0});
  el("line",{x1:52,x2:960,y1:y(0),y2:y(0),stroke:C.ref,"stroke-width":1},svg);line(svg,nm,values,x,y,{stroke:C.diff,"stroke-width":2.5});
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
function mapRenderDispositionLists(){
  const groups=MAP_DATA.cr_context.candidate_groups,label=payload=>{const [pair,construction]=payload.split(":");return mapPairLabel(pair)+" "+(construction==="C1_P0"?"C1":"C3")};
  const repeatedPayloads=new Set(MAP_DATA.cr_context.same_condition_and_followup.map(item=>item.pair_id+":"+item.construction_id));
  const history=groups.HISTORY_SENSITIVE_DIAGNOSTIC;
  document.getElementById("map-candidate-list").textContent=groups.PROMISING_FOR_FROZEN_ABSOLUTE_PREDICTION_TEST_NOT_ADMITTED.map(label).join(", ");
  document.getElementById("map-between-history-list").textContent=history.filter(payload=>repeatedPayloads.has(payload)).map(label).join(", ");
  document.getElementById("map-within-movement-list").textContent=history.filter(payload=>!repeatedPayloads.has(payload)).map(label).join(", ");
  document.getElementById("map-contrast-recurrence-list").textContent=groups.CONTRAST_RECURRENCE_WITH_ENDPOINTS_UNRESOLVED.map(label).join(", ");
  document.getElementById("map-unresolved-list").textContent=groups.WEAK_OR_MOVEMENT_LIMITED_DIAGNOSTIC.map(label).join(", ");
}
function renderExactPayloadHistory(){
  const history=MAP_DATA.exact_payload_history;
  if(!history||!document.getElementById("history-black-yellow"))return;
  const by=history.black_yellow_full_screen_h_v,operands=by.operands,cosines=by.signed_shape_relations.map(item=>item.signed_h_minus_v_spectrum_cosine);
  document.getElementById("history-black-yellow").textContent=
    "The same exact full-screen H and V pixel patterns, byte for byte, appear in five comparisons. H-minus-V spectral RMS was "+
    operands.map(item=>fmt(item.h_minus_v_spectral_rms_pp,3)+" pp").join(", ")+" in chronological order. Comparing the direction of the wavelength-by-wavelength changes gives ten cosine values, all "+
    fmt(Math.min(...cosines),4)+" or higher; 1 means the changes point in the same direction. The direction repeated closely, but the size of the difference did not stay fixed. This does not show that either pattern will return to the same measured color.";
  const checker=history.red_blue_checker_repeat_movement,old=checker.legacy_adjacent_repeat,newRows=checker.topology_quartet_operands;
  document.getElementById("history-red-blue-checker").textContent=
    "The identical red/blue checker changed by "+fmt(old.same_payload_movement_rms_pp,3)+" pp RMS between consecutive readings, then by "+
    fmt(newRows[0].same_payload_movement_rms_pp,3)+" pp between the first and last readings in ABBA order and "+fmt(newRows[1].same_payload_movement_rms_pp,3)+
    " pp between the middle two readings in BAAB order. The amount of change varied across these sessions and sequence positions. The readings alone cannot separate those influences; their movement is context, not a noise or uncertainty limit.";
}

function forwardAtlasSelection(){
  for(const link of document.querySelectorAll("[data-atlas-link]")){const target=new URL(link.href);
  for(const [key,value] of new URLSearchParams(location.search))if(["pair","width","order","row"].includes(key))target.searchParams.set(key,value);
  link.href=target.href;
  }
}
function showDataFailure(){
  document.querySelectorAll("[data-data-pending]").forEach(node=>{node.textContent="These interactive details could not load. The written findings remain available; reload to try again.";});
  document.querySelectorAll("[data-chart-status]").forEach(node=>{node.hidden=false;node.textContent="This plot could not load. The written findings and saved example values remain available; reload to try again.";});
}
function redrawResponsivePlots(){
  if(!MAP_DATA)return;
  mapRenderFeaturedExample();
  mapRenderMetricExample("BLUE_GREEN","native-metric-blue-green","native-bg-rms","native-bg-de","native-bg-movement");
  mapRenderMetricExample("RED_GREEN","native-metric-red-green","native-rg-rms","native-rg-de","native-rg-movement");
}
async function loadPageData(){
  try{
    const response=await fetch("/reflective-color-display/measurement-investigation.json");
    if(!response.ok)throw new Error("measurement data unavailable");
    const map=await response.json();
    if(!Array.isArray(map.rows)||!map.rows.length||!Array.isArray(map.wavelengths_nm))throw new Error("invalid measurement data");
    MAP_DATA=map;mapRenderPairOverview();mapRenderNativeFigures();renderExactPayloadHistory();
    document.querySelectorAll("[data-chart-status]").forEach(node=>node.hidden=true);
    if(typeof ResizeObserver!=="undefined"){const observer=new ResizeObserver(redrawResponsivePlots);
    ["featured-spectrum-native","native-metric-blue-green","native-metric-red-green"].forEach(id=>{const node=document.getElementById(id);if(node)observer.observe(node)});}
    document.getElementById("metric-perspective")?.addEventListener("toggle",redrawResponsivePlots);
  }catch(error){MAP_DATA=null;showDataFailure();}
}
forwardAtlasSelection();
mapRenderHookPatterns();
renderMeasuredComparisonPreviews();
if(document.querySelector("[data-chart-status],#pair-comparison-body"))loadPageData();

// Preserve bookmarks to sections moved off the former single-page article.
async function followMovedFragment(){
  const sourceHref=location.href,source=new URL(sourceHref);
  let id;try{id=decodeURIComponent(source.hash.slice(1))}catch{return}
  if(!id||document.getElementById(id))return;
  try{const response=await fetch("/reflective-color-display/fragment-routes.json");if(!response.ok)return;
    const routes=await response.json();if(location.href!==sourceHref||!Object.hasOwn(routes,id))return;
    const target=new URL(routes[id],source.origin);if(target.origin!==source.origin)return;
    target.search=source.search;if(target.href!==sourceHref)location.replace(target.href);
  }catch{/* A failed compatibility lookup must not hide the readable page. */}
}
followMovedFragment();window.addEventListener("hashchange",followMovedFragment);
