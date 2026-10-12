const API=(window.API_BASE||"").replace(/\/$/,""),SID=sessionStorage.getItem("sid")||(v=>{sessionStorage.setItem("sid",v);return v})(crypto.randomUUID());
const S={base:[],ings:[],bs:4,sv:4,pantry:{},reqs:[],opt:null,over:{},packs:{},rm:{},more:{},appr:[],filter:"all",view:"cards",pantryItems:[],have:[],skipped:[],budget:null,optmode:"best",addr:null,cart:null,step:1,dirty:false,addrLabel:"",extracted:false};
const amt=(n,u)=>u==="g"&&n>=1000?+(n/1000).toFixed(2)+" kg":u==="ml"&&n>=1000?+(n/1000).toFixed(2)+" l":n+" "+(u||"");
const $=i=>document.getElementById(i)||document.body.appendChild(Object.assign(document.createElement("div"),{id:i})),money=n=>n==null||n===""||!isFinite(+n)?"price unavailable":"₹"+(+n).toFixed(2).replace(/\.00$/,""),qty=(q,u)=>q==null?"as needed":safe(q)+" "+safe(u);
const safe=v=>v==null||v==="null"||v==="undefined"||(typeof v==="number"&&!isFinite(v))?"":String(v);
const _rc=Element.prototype.replaceChildren;Element.prototype.replaceChildren=function(...k){return _rc.apply(this,k.flat(2).filter(x=>x!=null&&x!==false&&x!==true))};  // null/undefined/false are NEVER rendered as text ("nullnull" bug)
const ask=(msg,{input=false,ph=""}={})=>new Promise(res=>{const inp=input?h("input",{placeholder:ph,style:"display:block;width:100%;margin:6px 0"}):null,end=v=>{box.remove();res(v)},
 box=h("div",{id:"dlg",role:"dialog","aria-modal":"true",style:"position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:99;padding:16px"},h("div",{class:"card",style:"max-width:440px;background:Canvas;color:CanvasText;padding:16px"},h("p",{style:"white-space:pre-line"},msg),inp,h("button",{onclick:()=>end(input?inp.value:true)},"OK")," ",h("button",{class:"alt",onclick:()=>end(input?null:false)},"Cancel")));document.body.append(box);(inp||box.querySelector("button")).focus()});  // replaces window.confirm/prompt, which some browsers (and embedded previews) don't support
const h=(t,p={},...k)=>{const e=document.createElement(t);for(const[a,v]of Object.entries(p))a.startsWith("on")?e.addEventListener(a.slice(2),v):a==="class"?e.className=v:a.includes("-")?(v!=null&&v!==false&&e.setAttribute(a,v)):e[a]=v;e.append(...k.flat().filter(x=>x!=null&&x!==false&&x!==true));return e};
const pk=p=>`${p.brand||""} ${p.name} — ${p.pack_label||p.pack_quantity+" "+p.pack_unit} — ${money(p.price)}`+(p.rating?` · ⭐${p.rating}`:"");
{const need=["q","go","status","err","banner","title","info","serv","prods","basket","s2","s3","s4","back","next","stepper","addrchip","cov","bar"].filter(i=>!document.getElementById(i));
 if(need.length)document.body.prepend(h("p",{class:"err"},"Page files are out of sync: index.html is missing ["+need.join(", ")+"]. Copy BOTH index.html and app.js from the latest zip, then press Ctrl+F5."))}
async function api(path,body){const r=await fetch(API+path,{method:body?"POST":"GET",headers:{"Content-Type":"application/json","X-Session":SID},body:body?JSON.stringify(body):undefined});
 const d=await r.json().catch(()=>({}));if(!r.ok){const x=new Error(typeof d.detail==="string"?d.detail:"Invalid request ("+r.status+")");x.data=d;throw x};return d}
const run=async f=>{try{$("err").replaceChildren();await f()}catch(e){if(e.data&&e.data.code==="CART_CHANGED"){S.cart=S.cart||{};S.cart.hash=e.data.hash;try{await renderBasket()}catch(_){}}  // refresh the review so "Try again" uses the live cart, not the stale one
  const el=$("err");el.replaceChildren(safe(e.message)||"Something went wrong.");
  if(!(e.data&&e.data.login_required)){el.append(" ",h("button",{class:"alt",type:"button",onclick:()=>run(f)},"Try again"))}
  if(e.data&&e.data.price_changes){if(S.ings.length)refresh(false).catch(()=>{});xRefresh().catch(()=>{})}}};
const show=id=>$(id).classList.remove("hide");
const qcell=i=>{if(i.quantity==null)return "as needed";const base=i.source_text||qty(i.quantity,i.unit);
 const est=i.normalized_is_estimate?`(~${i.quantity} ${i.unit}, estimated)`:(i.est_piece_g&&i.unit==="piece"?`(~${Math.round(i.quantity*i.est_piece_g)} g, estimated)`:"");return base+(est?" "+est:"")};
async function optimize(){S.opt=await api("/api/optimize-cart",{requirements:S.reqs,address_id:S.addr,overrides:S.over,pack_counts:S.packs,approved_substitutes:S.appr,have:S.have,skipped:S.skipped,budget:S.budget,mode:S.optmode});renderProds()}
const svgIcon=()=>{const n="http://www.w3.org/2000/svg",s=document.createElementNS(n,"svg");s.setAttribute("viewBox","0 0 24 24");s.setAttribute("fill","none");s.setAttribute("aria-hidden","true");const p=document.createElementNS(n,"path");p.setAttribute("d","M6 8h12l-1.2 7.2a1.6 1.6 0 0 1-1.6 1.3H8.8a1.6 1.6 0 0 1-1.6-1.3L6 8Zm0 0-.5-2H4");p.setAttribute("stroke","currentColor");p.setAttribute("stroke-width","1.5");p.setAttribute("stroke-linecap","round");p.setAttribute("stroke-linejoin","round");s.append(p);return s};
const ph=c=>h("div",{class:"ph "+(c||"pimg"),role:"img","aria-label":"No product image available"},svgIcon());
const img=(p,c)=>p.image_url&&/^https:\/\//.test(p.image_url)?h("img",{src:p.image_url,loading:"lazy",referrerPolicy:"no-referrer",alt:"",class:c||"pimg",onerror:e=>e.target.replaceWith(ph(c))}):ph(c);
const MATCH={EXACT_MATCH:"✓ Exact match",VALID_VARIANT:"✓ Acceptable alternative",POSSIBLE_ALTERNATIVE:"⚠ Needs review (needs your OK)",USER_ACCEPTED_SUBSTITUTION:"✓ Approved by you"};
function pantrySel(ing,st){return h("select",{"aria-label":"Status of "+ing.name,onchange:e=>{S.pantry[ing.name]=e.target.value;run(()=>refresh(false))}},...[["buy","Need to buy"],["have","Already have (in pantry)"],["skip","Skip"]].map(([v,l])=>h("option",{value:v,selected:st===v},l)))}
const stateOf=(ing,by)=>{const p=S.pantry[ing.name]||"buy",it=by[ing.name];return p==="have"?"have":p==="skip"?"skip":(!it||it.status!=="ok")?"missing":"selected"};
function renderProds(){const by={};S.opt.items.forEach(it=>by[it.requirement.ingredient_name]=it);
 const sts=S.ings.map(i=>stateOf(i,by)),n=k=>sts.filter(x=>x===k).length;
 const F=[["all","All",sts.length],["buy","Need to buy",n("selected")+n("missing")],["selected","Selected",n("selected")],["have","Already have",n("have")],["missing","Missing",n("missing")]];
 $("filters").replaceChildren(...F.map(([k,l,c])=>h("button",{class:S.filter===k?"":"alt",onclick:()=>{S.filter=k;renderProds()}},`${l} (${c})`)),h("span",{style:"margin-left:14px"}),
  ...["cards","list"].map(v=>h("button",{class:S.view===v?"":"alt",onclick:()=>{S.view=v;renderProds()}},v==="cards"?"Cards":"List")));
 const keep=i=>S.filter==="all"||(S.filter==="buy"?["selected","missing"].includes(sts[i]):S.filter===sts[i]);
 $("prods").replaceChildren(...S.ings.map((ing,i)=>{if(!keep(i))return null;const st=sts[i],it=by[ing.name];
  if(st==="have"||st==="skip")return h("div",{class:"card"},h("div",{class:"ihead"},h("div",{class:"req"},h("span",{class:"st off2"},st==="have"?"In pantry":"Skipped"),h("b",{},ing.name)," · ",qcell(ing)),pantrySel(ing,S.pantry[ing.name]||"buy")),
   h("p",{class:"muted"},st==="have"?"Kept in the recipe, not added to your cart.":"Not added to your cart."+(ing.quantity==null?" (no quantity in the recipe)":"")));
  if(!it)return h("div",{class:"card"},h("div",{class:"ihead"},h("div",{class:"req"},h("span",{class:"st bad"},"Unavailable"),h("b",{},ing.name)," · ",qcell(ing)),pantrySel(ing,"buy")));
  return productCard(it,ing)}).filter(Boolean));$("cov").replaceChildren(coverEl());if(S.step===3)run(renderBasket);updateBar()}
function productCard(it,ing){const r=it.requirement,rid=r.requirement_id,c=h("div",{class:"card"}),cards=S.view==="cards";
 const need=r.original?`${r.original} (~${r.required_quantity} ${r.unit}, estimated)`:(r.source_text||qty(r.required_quantity,r.unit));
if(it.status==="search_failed"){c.append(h("div",{class:"ihead"},h("div",{class:"req"},h("span",{class:"st bad"},"Search failed"),h("b",{},r.ingredient_name)),pantrySel(ing,"buy")),h("p",{class:"err"},"Instamart search didn't respond for this item. That is not the same as it being unavailable. "),h("button",{class:"alt",onclick:()=>run(()=>refresh(false))},"Retry search"));return c}
 const stl=it.status==="ok"?["st","Selected"]:it.status==="needs_substitute_approval"?["st mid","Needs your choice"]:["st bad","Unavailable"];
 c.append(h("div",{class:"ihead"},h("div",{class:"req"},h("span",{class:stl[0]},stl[1]),h("b",{},r.ingredient_name)," · needs ",need),pantrySel(ing,"buy")));
 const chosen=it.selection.map(l=>l.product.product_id),opts=[...it.candidates.map(x=>({...x,out:false})),...(it.unavailable||[]).map(x=>({...x,out:true}))];
 if(!opts.length){c.append(h("p",{},`No suitable Instamart product found for "${r.ingredient_name}". You can skip it or buy it elsewhere.`));return c}
 if(!chosen.length)c.append(h("p",{class:"muted"},"No exact match: pick an option, or skip."));
 const pick=a=>run(async()=>{if(a.substitute&&!S.appr.includes(rid))S.appr.push(rid);S.over[rid]=a.product.product_id;delete S.packs[rid];await optimize()});
 const setN=k=>run(async()=>{S.packs[rid]=Math.max(1,Math.min(20,k));await optimize()});
 const open=!!S.more[rid]||!chosen.length;  // alternatives stay collapsed once something is selected; open when the user must choose
 if(chosen.length&&!open){const l0=it.selection[0],p0=l0.product,cand=opts.find(a=>a.product.product_id===p0.product_id),lab0=cand?(cand.substitute?"✓ Substitute you accepted":(MATCH[cand.match]||"")):"";
  c.append(h("div",{class:"chosen"},img(p0,"thumb"),h("div",{},h("b",{},(p0.brand?p0.brand+" · ":"")+p0.name),h("div",{class:"muted"},(p0.pack_label||p0.pack_quantity+" "+p0.pack_unit)+" · "+money(p0.price)+(p0.rating?" · ⭐"+p0.rating:"")),h("small",{},lab0),
   it.selection.length===1?h("div",{class:"stepper-q"},h("button",{class:"alt","aria-label":"Fewer packs",onclick:()=>setN(l0.packs-1)},"−"),h("span",{"aria-live":"polite"},l0.packs+(l0.packs===1?" pack":" packs")),h("button",{class:"alt","aria-label":"More packs",onclick:()=>setN(l0.packs+1)},"+")):null)))}
 const lim=cards?6:3,show=!open?[]:(S.more[rid]?opts.slice(0,30):opts.slice(0,Math.max(lim,opts.length>lim?lim:opts.length))),list=h("div",{class:cards?"row":""});
 show.forEach(a=>{const p=a.product,sel=chosen.includes(p.product_id),line=sel&&it.selection.length===1?it.selection[0]:null;
  const lab=a.out?"Out of stock":sel&&a.substitute?"✓ Accepted substitute":(MATCH[a.match]||""),pack=p.pack_label||p.pack_quantity+" "+p.pack_unit;
  if(cards)list.append(h("div",{class:"pc"+(sel?" on":"")+(a.out?" out":"")},img(p),h("div",{class:"pn"},(p.brand?p.brand+" · ":"")+p.name),h("div",{class:"muted"},pack),
   h("div",{},p.rating?"⭐"+p.rating+" · ":"",h("b",{},money(p.price))),h("small",{class:a.substitute&&!sel?"err":"muted"},lab),
   h("div",{},a.out?"":sel?(line?h("span",{},h("button",{class:"alt",onclick:()=>setN(line.packs-1)},"−")," ",line.packs," ",h("button",{class:"alt",onclick:()=>setN(line.packs+1)},"+")):"✓ Selected"):h("button",{onclick:()=>pick(a)},"Select"))));
  else list.append(h("label",{style:"display:block;margin:4px 0;"+(a.out?"opacity:.5":"")},h("input",{type:"radio",name:rid,style:"width:auto",disabled:a.out,checked:sel,onchange:()=>pick(a)})," "+pk(p)+(lab?" · "+lab:"")))});
 if(open)c.append(list);
 if(chosen.length)c.append(h("button",{class:"alt","aria-expanded":String(!!S.more[rid]),onclick:()=>{S.more[rid]=!S.more[rid];renderProds()}},S.more[rid]?"Hide alternatives":`Show ${opts.length-1>0?opts.length-1:"other"} alternative${opts.length-1===1?"":"s"}`));
 else if(opts.length>lim)c.append(h("small",{class:"muted"},`Showing ${lim} of ${opts.length} options`));
 if(it.status==="ok"){const s=h("div",{class:"sel"},h("b",{},"You'll buy: "),it.selection.map(l=>`${l.product.pack_label||l.product.pack_quantity+" "+l.product.pack_unit} × ${l.packs} = ${money(l.line_total)}`).join(" + "));
  s.append(h("div",{},it.unverified?"Quantity estimate unavailable: the recipe amount can't be compared with the pack, so 1 pack is assumed.":it.purchased!=null?`Purchased ${amt(it.purchased,it.purchased_unit||r.unit)} · ${it.estimated?"≈ ":""}Leftover ${amt(it.excess||0,it.purchased_unit||r.unit)}${it.estimated?" (estimated conversion, rounded)":""}`:"Quantity not specified by recipe · 1 pack selected"));
  if(!cards&&it.selection.length===1)s.append(h("div",{},"Packs: ",h("input",{type:"number",min:1,max:20,value:it.selection[0].packs,style:"width:70px",onchange:e=>setN(+e.target.value||1)})));
  s.append(h("small",{},it.reasons.map(x=>x.startsWith("⚠")?x:"✓ "+x).join("  ")));c.append(s)}
 return c}
const totals=()=>{const lines=((S.opt&&S.opt.items)||[]).flatMap(i=>i.selection.map(l=>({...l,r:i.requirement,ex:i.excess,unv:i.unverified,est:i.estimated,pu:i.purchased_unit,m:i.selected_match,qs:i.quantity_state}))).filter(l=>!S.rm[l.r.requirement_id]);
 return{lines,tot:lines.reduce((a,l)=>a+l.line_total,0)+extraTot(),k:lines.length+(S.extra||[]).length}};
function updateBar(){const b=$("bar");b.classList.remove("hide");const t=totals(),cov=S.opt&&S.opt.coverage,n=cov&&cov.counts;
 $("barsum").textContent=S.step===1?(S.extracted?`${S.ings.length} ingredients ready · set servings, budget and pantry, then continue`:"Extract a recipe to begin"):
  `${n?n.selected+"/"+n.to_buy+" selected · "+n.unresolved+" unresolved · ":""}${t.k} product${t.k===1?"":"s"} · ${money(t.tot)}${S.budget?" of ₹"+S.budget+" budget":""}`;
 $("back").classList.toggle("hide",S.step===1);$("next").classList.toggle("hide",S.step===3);$("next").textContent=S.step===1?"Continue to products →":"Continue to review →";
 document.querySelectorAll("#stepper button").forEach(x=>{const i=+x.dataset.go;x.setAttribute("aria-label","Step "+i+": "+(x.dataset.label||"")+(i<S.step?" (completed)":i===S.step?" (current)":""));if(i===S.step)x.setAttribute("aria-current","step");else x.removeAttribute("aria-current");x.classList.toggle("done",i<S.step||(i===2&&!!S.opt&&S.step!==2))})}
function problem(msg,focusId){$("err").textContent=msg;const f=focusId&&document.getElementById(focusId);if(f&&f.scrollIntoView){f.scrollIntoView({block:"center"});if(f.focus)f.focus()}return false}
async function goStep(n){$("err").replaceChildren();
 if(n>=2){if(!S.extracted||!S.ings.length)return problem("Enter a dish, recipe or video link and press “Extract recipe” first.","q");
  if(S.mode==="swiggy"&&!S.addrOk)return problem("Choose your delivery address first (Step 1).","addrbox")}
 if(n>=2&&(S.dirty||!S.opt)){S.step=2;applyStep();await refresh(false)}
 if(n>=3){const t=totals();if(!t.k)return problem("Nothing is selected to add yet. Pick a product for at least one ingredient (or go back and adjust the recipe).")}
 S.step=n;applyStep();if(n===3)await renderBasket();updateBar()}
function applyStep(){document.querySelectorAll("[data-step]").forEach(e=>e.classList.toggle("off",+e.dataset.step!==S.step));
 const hd=S.step===1?$("h1a"):S.step===2?$("h3a"):$("h4a");window.scrollTo({top:0});if(hd&&hd.focus)hd.focus({preventScroll:true});updateBar()}
function setSync(t){$("sync").textContent=t||""}
function diagTxt(r){const d=r.diagnostic;if(!d)return"";const m=(d.missing||[]).slice(0,4).map(x=>`${safe(x.name)||"item"}: wanted ${x.wanted}, live cart has ${x.found}`).join("; ");return` (Wanted ${safe(d.wanted_items)} item(s); live cart has ${safe(d.live_items)}.${m?" Missing: "+m+".":""})`}
function billEl(b){if(!b||!(b.lines||[]).length&&!b.to_pay)return null;return h("div",{class:"muted"},h("b",{},"Live bill from Instamart (includes any fees it lists): "),...(b.lines||[]).map(l=>h("div",{},`${safe(l.label)}: ${safe(l.value)}`)),b.to_pay?h("div",{},h("b",{},`To pay: ${safe(b.to_pay)}`)):null)}
async function done(r){const ok=r.status==="CONFIRMED"&&r.verified===true;setSync(ok?"✓ "+safe(r.message||"Instamart cart verified")+(r.operation==="clear"?"":" Order placement is disabled."):"⚠ Cart update NOT verified: "+safe(r.message||"The live cart could not be confirmed.")+diagTxt(r));
 if(ok&&r.delivery_address)setSync($("sync").textContent+` Saved to the Instamart cart for: ${safe(r.delivery_address)}. In the Swiggy app, open Instamart with this same delivery address and pull to refresh: Swiggy carts are per address, so a different app location shows an empty cart.`);
 if(r.cart_address_matches===false)setSync($("sync").textContent+" ⚠ Swiggy reports the live cart under a different address than the one selected here.");
 if(r.adjustments){const a=r.adjustments;setSync($("sync").textContent+" ⚠ Swiggy adjusted your cart:"+(a.removed.length?` removed out-of-stock: ${a.removed.map(safe).join(", ")}.`:"")+(a.reduced.length?` reduced quantity: ${a.reduced.map(x=>`${safe(x.name)} (${safe(x.requested)}→${safe(x.capped)}${x.reason?", "+safe(x.reason):""})`).join("; ")}.`:""))}
 if(r.budget_warning)setSync($("sync").textContent+" ⚠ "+r.budget_warning);
 if(r.price_changes&&r.price_changes.length)setSync($("sync").textContent+" Cart updated because one or more live Instamart prices changed.");await renderBasket()}
async function renderBasket(){S.cart=await api("/api/instamart/cart");
 const lines=S.opt.items.flatMap(i=>i.selection.map(l=>({...l,r:i.requirement,ex:i.excess,unv:i.unverified,est:i.estimated,pu:i.purchased_unit,m:i.selected_match,qs:i.quantity_state}))).filter(l=>!S.rm[l.r.requirement_id]);
 const xlines=S.extra.map(x=>({product:x.product,packs:x.packs,line_total:+(x.product.price*x.packs).toFixed(2),extra:true,m:"EXACT_MATCH",qs:"none",r:{ingredient_name:"Additional item"}}));
 const rtot=lines.reduce((a,l)=>a+l.line_total,0),xtot=xlines.reduce((a,l)=>a+l.line_total,0),tot=rtot+xtot,over=S.budget&&tot>S.budget,cov=S.opt.coverage,k=lines.length+xlines.length;window._ob=h("input",{type:"checkbox",style:"width:auto"});
 $("barsum").textContent=`${cov&&cov.counts?cov.counts.selected+"/"+cov.counts.to_buy+" selected · "+(cov.counts.exact||0)+" exact"+((cov.counts.alternative||0)+(cov.counts.approved||0)?" · "+((cov.counts.alternative||0)+(cov.counts.approved||0))+" alt":"")+((cov.counts.needs_review||0)+(cov.counts.unavailable||0)?" · "+((cov.counts.needs_review||0)+(cov.counts.unavailable||0))+" need attention":"")+" · ":""}${k} product${k===1?"":"s"} · ${money(tot)}`;$("bar").classList.remove("hide");
 const plan=lines.map(l=>h("div",{class:"card plan"},img(l.product,"thumb"),h("div",{},h("b",{},l.r.ingredient_name),h("div",{},(l.product.brand?l.product.brand+" · ":"")+l.product.name),
  h("div",{class:"muted"},`${l.product.pack_label||l.product.pack_quantity+" "+l.product.pack_unit} × ${l.packs}`),
  h("small",{},l.r.required_quantity==null?"Quantity not specified by recipe":(l.unv?`⚠ 1 pack assumed: can't verify it covers ${l.r.original||l.r.source_text||amt(l.r.required_quantity,l.r.unit)}`:`✓ Covers recipe need of ${l.r.original||l.r.source_text||amt(l.r.required_quantity,l.r.unit)}`+(l.ex!=null?` · ${l.est?"≈ ":""}leftover ${amt(l.ex,l.pu||l.r.unit)}${l.est?" (estimated conversion, rounded)":""}`:""))),
  h("div",{},h("button",{class:"lnk","aria-label":"Remove "+l.r.ingredient_name,onclick:()=>{S.pantry[l.r.ingredient_name]="skip";run(()=>refresh(false))}},"Remove"))),h("div",{class:"tot"},money(l.line_total))));
 const cur=S.cart.items.length?S.cart.items.map(i=>h("li",{},`${i.name} × ${i.packs}`)):[h("li",{class:"muted"},"Your Instamart cart is empty.")];
 const clear=h("button",{class:"alt",disabled:!S.cart.items.length,onclick:async()=>{if(S.cartBusy)return;if(!await ask("Clear your Instamart cart?\n\nThis will remove all items currently in your Swiggy Instamart cart. This action cannot be undone."))return;
  if(S.cartBusy)return;S.cartBusy=true;run(async()=>{try{setSync("⟳ Clearing Instamart cart…");const r=await api("/api/instamart/cart/clear",{confirm:true,idempotency_key:crypto.randomUUID()});setSync("⟳ Confirming live cart…");await done(r)}finally{S.cartBusy=false}})}},"Clear Cart");
 const row=(l,v,cls)=>h("div",{class:"srow"+(cls?" "+cls:"")},h("span",{},l),h("b",{},v));
 const bill=S.cart.bill,bl=bill&&(bill.lines||[]).length?bill.lines.map(x=>row(safe(x.label),safe(x.value))):[];
 const sumCard=h("div",{class:"summary"},h("h3",{},"Cost summary"),
  h("div",{class:"muted"},"Estimated recipe cost (this recipe only)"),row(`Recipe ingredients: ${lines.length} product${lines.length===1?"":"s"}, estimated from live prices, before any fees`,money(rtot)),xlines.length?row(`Additional items: ${xlines.length} product${xlines.length===1?"":"s"}`,money(xtot)):null,xlines.length?row("Estimated products total",money(tot)):null,
  S.budget?row("Your budget",money(S.budget)+(over?` · over by ${money(tot-S.budget)}`:" · within budget"),over?"bad":"ok"):null,
  bl.length?h("div",{class:"bill"},h("div",{class:"muted"},"Verified live cart bill from Instamart (everything in your cart, fees exactly as Instamart lists them)"),...bl,bill.to_pay?row("To pay (live cart)",safe(bill.to_pay)):null):h("p",{class:"muted"},S.cart.cart_total!=null&&S.cart.items.length?`Live cart item total: ${money(S.cart.cart_total)}. `:"","Delivery and handling fees appear here once Instamart returns a bill for your cart. They are not estimated."),
  over?h("div",{class:"warnbox"},"Over budget. ",h("button",{class:"alt",onclick:()=>{S.optmode="cheapest";$("optmode").value="cheapest";S.over={};S.packs={};run(()=>refresh(false))}},"Switch to Cheapest"),h("label",{class:"inl"},window._ob," Add anyway (over budget)")):null,
  (S.opt.coverage&&S.opt.coverage.counts&&S.opt.coverage.counts.unresolved)?h("div",{class:"warnbox"},`${S.opt.coverage.counts.unresolved} ingredient${S.opt.coverage.counts.unresolved===1?" is":"s are"} unresolved and won't be added. The recipe may be incomplete.`):null,
  h("div",{class:"cta"},h("button",{disabled:!k||S.cartBusy,"aria-haspopup":"dialog",onclick:e=>cartDialog([...lines,...xlines],tot,e.currentTarget)},"Add to Instamart Cart"),h("small",{},"Opens a confirmation. Nothing changes in your cart until you confirm; nothing is checked out or paid.")));
 const xplan=xlines.map(l=>{const id=l.product.product_id;return h("div",{class:"card plan"},img(l.product,"thumb"),h("div",{},h("small",{class:"tag"},"Additional item"),h("div",{},h("b",{},(l.product.brand?l.product.brand+" · ":"")+l.product.name)),h("div",{class:"muted"},`${pkl(l.product)} × ${l.packs} · ${money(l.product.price)} each`),
  h("div",{},h("button",{class:"alt","aria-label":"Decrease quantity of "+l.product.name,onclick:()=>xSet(id,l.packs-1)},"−")," ",String(l.packs)," ",h("button",{class:"alt","aria-label":"Increase quantity of "+l.product.name,onclick:()=>xSet(id,l.packs+1)},"+")," ",h("button",{class:"lnk","aria-label":"Remove "+l.product.name,onclick:()=>xSet(id,0)},"Remove"))),h("div",{class:"tot"},money(l.line_total)))});
 $("basket").replaceChildren(h("h3",{},"Recipe ingredients"),coverEl(),...(plan.length?plan:[h("p",{class:"muted"},"No recipe products selected.")]),xplan.length?h("h3",{},"Additional items"):null,...xplan,sumCard,
  h("h3",{},"Already in your Instamart cart (live)"),h("div",{class:"card"},h("ul",{class:"cur"},...cur),clear,h("p",{class:"muted"},"Read-only view of your live cart. Items already there at the needed quantity are left as they are. Clear Cart is separate and asks for its own confirmation.")));show("s4")}
function renderInfo(d){const v=d.visual,k=[];if(v)k.push(h("p",{},`Visual analysis complete: ${v.total} ingredients detected · ${v.confirmed} confirmed · ${v.estimated} estimated · ${v.uncertain} uncertain`));
 if(d.partial)k.push(h("p",{class:"err"},"Recipe partially reconstructed. Some ingredients or steps were not visible in the video."));
 if((d.suggested_missing||[]).length){k.push(h("p",{class:"err"},"⚠ This extraction may be incomplete. Please confirm these likely-missing ingredients (nothing is added unless you do):"));
  d.suggested_missing.forEach(m=>{const row=h("div",{class:"card"},h("b",{},m.name)," · "+m.reason+" ",h("button",{class:"alt",onclick:()=>run(async()=>{const amt=await ask(`How much ${m.name} does the recipe need? (e.g. 500 g, 2 cups)`,{input:true,ph:"e.g. 500 g"});if(!amt||!amt.trim())return;
   const p=(await api("/api/normalize",{lines:[amt.trim()+" "+m.name]})).ingredients[0];if(!p)throw new Error("Couldn't read that amount.");S.ings.push(p);{const f=(S.bs||1)/(S.sv||1),sc=v=>v==null?v:+(v*f).toFixed(2);S.base.push({...p,quantity:sc(p.quantity),source_quantity:sc(p.source_quantity)})}S.pantry[p.name]="buy";S.dirty=true;row.remove();updateBar()})},"Add it…")," ",h("button",{class:"alt",onclick:()=>row.remove()},"It's not needed"));k.push(row)})}
 if(d.steps&&d.steps.length)k.push(h("h3",{},"Recipe steps"),h("ol",{},...d.steps.map(s=>h("li",{},s))));$("info").replaceChildren(...k)}
$("go").onclick=()=>run(async()=>{if(S.mode==="swiggy"&&!S.addrOk)return problem("Choose your delivery address first, then extract the recipe.","addrbox");const v=$("q").value.trim();if(!v){problem("Type a dish name, paste a recipe, or paste a video link first.","q");return}
 $("status").textContent=/^(https?:\/\/|www\.|youtu)/i.test(v)?"Analyzing link… videos can take up to a minute":"Working on your recipe…";
 let d;try{d=await api("/api/extract",{input:v})}catch(e){$("status").textContent="";S.extracted=false;throw e}
 S.base=d.ingredients;S.ings=d.ingredients;S.bs=S.sv=d.servings;$("serv").value=d.servings;
 S.pantry={};d.ingredients.forEach(i=>S.pantry[i.name]=/^((warm|hot|cold|ice|boiling|lukewarm|tap)\s+)?water$/i.test(i.name.trim())?"have":(i.quantity==null||i.confidence==="uncertain")?"skip":"buy");
 $("title").textContent=(d.visual?"Visual recipe analysis: ":"Recipe: ")+d.title+" (source: "+d.source+")"+(d.warning?" · Note: "+d.warning:"");
 S.pantryItems=d.pantry||[];S.budget=d.budget||null;$("budget").value=S.budget||"";S.opt=null;S.extracted=true;S.dirty=true;S.rm={};S.over={};S.packs={};S.appr=[];S.more={};renderInfo(d);renderPantry();show("s2");$("status").textContent="✓ Recipe ready: "+d.ingredients.length+" ingredients. Check servings, budget and pantry, then press Continue.";updateBar()});
$("serv").onchange=()=>run(async()=>{const n=+$("serv").value;S.ings=(await api("/api/scale",{ingredients:S.base,from_servings:S.bs,to_servings:n})).ingredients;S.packs={};S.dirty=true;if(S.step>1)await refresh(false);updateBar()});
async function refresh(reset){if(S.mode==="swiggy"&&!S.addrOk){$("err").textContent="Choose your delivery address first.";return}
 if(reset){S.over={};S.packs={};S.appr=[];S.more={}}
 $("prods").replaceChildren(...[0,1,2].map(()=>h("div",{class:"card skel"},"Finding live Instamart products…")));
 const rq=await api("/api/shopping-requirements",{ingredients:S.ings,pantry:S.pantry,pantry_items:S.pantryItems});S.reqs=rq.requirements;S.have=rq.have;S.skipped=rq.skipped;renderPantry();
 if(S.reqs.length)await optimize();else{S.opt={items:[],estimated_total:0};renderProds()}S.dirty=false}
function coverEl(){const c=S.opt.coverage;if(!c)return null;const n=c.counts||{},bad=c.rows.filter(r=>!["have","covered","substituted","have_unknown","assumed","skipped"].includes(r.state));
 const L={missing:"no suitable product found after retries",unavailable:"only out-of-stock listings found",substitution_pending:"a possible substitute needs your approval",search_failed:"search failed, try again",partial:"the selected pack covers only part of the amount"};
 const st=(v,l,cls)=>h("span",{class:"stat"+(cls?" "+cls:"")},h("b",{},String(v||0))," "+l),pl=(k,w)=>k===1?w:w+"s";
 const alt=(n.alternative||0),ap=n.approved||0;
 return h("div",{class:"cov"},h("b",{},`Products selected for ${n.selected!=null?n.selected:c.covered} of ${n.to_buy!=null?n.to_buy:c.total} ingredients`),
  h("div",{class:"stats","aria-label":"Match quality"},st(n.exact,"exact match"),alt?st(alt,pl(alt,"acceptable alternative")):null,ap?st(ap,"approved by you"):null,n.needs_review?st(n.needs_review,"need review","warn"):null,n.unavailable?st(n.unavailable,"unavailable","bad"):null),
  h("div",{class:"stats","aria-label":"Quantity confidence"},st(n.qty_verified,"amount"+(n.qty_verified===1?"":"s")+" verified"),st(n.qty_estimated,"amount"+(n.qty_estimated===1?"":"s")+" estimated"),n.qty_unverified?st(n.qty_unverified,pl(n.qty_unverified,"amount")+" unverified (1 pack assumed)","warn"):null,st(n.pantry,"in pantry"),st(n.skipped,"skipped")),
  bad.length?h("details",{class:"issues",open:bad.length<=2},h("summary",{},`${bad.length} ingredient${bad.length===1?"":"s"} need${bad.length===1?"s":""} attention`),...bad.map(r=>h("div",{class:"issue err"},`⚠ ${r.name}: ${L[r.state]||r.state}`))):null)}
function renderPantry(){$("pantrylist").replaceChildren(...S.pantryItems.map((p,i)=>h("span",{class:"card",style:"display:inline-block;margin:2px;padding:2px 8px"},p.name+(p.quantity!=null?` ${p.quantity} ${p.unit||""}`:" (amount not stated)")+" ",h("a",{href:"#",onclick:e=>{e.preventDefault();S.pantryItems.splice(i,1);S.dirty=true;renderPantry();if(S.step>1)run(()=>refresh(false))}},"✕"))))}
$("padd").onclick=()=>run(async()=>{const t=$("pname").value.trim();if(!t)return;const p=(await api("/api/normalize",{lines:[t]})).ingredients[0];if(!p)throw new Error("Couldn't read that pantry item.");
 S.pantryItems.push({name:p.name,quantity:p.quantity,unit:p.unit});$("pname").value="";S.dirty=true;renderPantry();if(S.step>1&&S.ings.length)await refresh(false)});
$("budget").onchange=()=>{S.budget=+$("budget").value||null;S.dirty=true;if(S.step>1&&S.ings.length)run(()=>refresh(false));updateBar()};
$("optmode").onchange=()=>{S.optmode=$("optmode").value;S.over={};S.packs={};S.dirty=true;if(S.step>1&&S.ings.length)run(()=>refresh(false))};
const connectBtn=()=>h("button",{onclick:()=>run(async()=>{const t=(await api("/api/swiggy/login-start",{})).ticket;location.href=API+"/api/swiggy/login?ticket="+encodeURIComponent(t)})},"Connect Swiggy account");
const discBtn=()=>h("button",{class:"alt",onclick:()=>run(async()=>{await api("/api/swiggy/logout",{});location.reload()})},"Disconnect Swiggy");
function addrForm(){const f={},inp=(k,ph,req=true)=>{const i=h("input",{placeholder:ph+(req?"":" (optional)"),style:"display:block;margin:2px 0;width:100%"});f[k]=i;return i};
 const cat=h("select",{},...["HOME","WORK","OFFICE","FRIENDS_AND_FAMILY","OTHER"].map(v=>h("option",{value:v},v.replace(/_/g," ").toLowerCase())));
 const box=h("div",{class:"card",style:"display:none"},h("b",{},"Add a new delivery address (saved to your Swiggy account)"),inp("fullAddress","Full address"),inp("addressLine","House / building / street"),inp("addressLine2","Apartment / floor / wing (blank if none)",false),inp("locality","Area / locality",false),inp("city","City"),inp("postalCode","Postal code"),cat,inp("addressTag","Label, e.g. My Home",false),inp("userName","Your name (as on your Swiggy account)"),inp("userPhone","Your phone number (as on your Swiggy account)"),
  h("button",{onclick:()=>run(async()=>{const b={confirm:true,addressCategory:cat.value};for(const[k,i]of Object.entries(f)){const v=i.value.trim();if(v||k==="addressLine2")b[k]=v}
   if(!await ask("Save this address to your Swiggy account?"))return;const r=await api("/api/instamart/address/create",b);S.addr=r.address_id;S.addrOk=true;await loadAddresses();S.dirty=true})},"Save address")," ",h("button",{class:"alt",onclick:()=>{box.style.display="none"}},"Cancel"));
 return[h("button",{class:"alt",onclick:()=>{box.style.display="block"}},"＋ Add a new address"),box]}
function chip(label){const c=$("addrchip");S.addrLabel=label||"";if(!label){c.classList.add("hide");return}c.classList.remove("hide");
 c.title=label;c.replaceChildren(h("span",{"aria-hidden":"true"},"📍"),h("span",{class:"txt"},"Deliver to: "+label),h("button",{type:"button",onclick:()=>run(()=>goStep(1)).then(()=>$("addrbox").scrollIntoView({block:"center"}))},"Change"))}
async function loadAddresses(){const d=await api("/api/instamart/addresses");
 if(S.mode==="swiggy"){$("banner").className="pill";$("banner").replaceChildren(h("span",{class:"dot"}),"LIVE SWIGGY INSTAMART · live products & prices",discBtn())}  // only after a real MCP call succeeded
 if(!d.addresses.length){$("addrbox").replaceChildren(h("p",{class:"err"},"No saved delivery address found. Add one below or in the Swiggy app."),...addrForm());return}
 const choose=async id=>{await api("/api/instamart/address",{address_id:id});S.addr=id;S.addrOk=true;$("err").textContent="";chip((d.addresses.find(a=>a.id===id)||{}).label);S.dirty=true;if(S.step>1&&S.ings.length)await refresh(false)};
 if(S.mode!=="swiggy"){await choose(d.addresses[0].id);return}
 S.addrOk=!!d.selected;S.addr=d.selected||null;chip((d.addresses.find(a=>a.id===d.selected)||{}).label);
 $("addrbox").replaceChildren(h("div",{role:"radiogroup","aria-label":"Delivery address"},...d.addresses.map(a=>h("label",{style:"display:block;margin:4px 0"},h("input",{type:"radio",name:"addr",style:"width:auto",checked:a.id===d.selected,onchange:()=>run(()=>choose(a.id))})," "+a.label))),...addrForm())}
run(async()=>{const hl=await api("/api/health");S.mode=hl.mode;
 $("banner").className="pill warn";$("banner").title=hl.label||"";$("banner").replaceChildren(h("span",{class:"dot"}),hl.mode==="local"?"DEMO MODE · mock catalog, not real prices":"SWIGGY INSTAMART: Not connected");
 if(hl.mode==="swiggy"&&!(await api("/api/swiggy/status")).logged_in){$("banner").append(connectBtn());return}
 await loadAddresses()});

document.querySelectorAll("#stepper button").forEach(b=>b.onclick=()=>run(()=>goStep(+b.dataset.go)));
$("next").onclick=()=>run(()=>goStep(S.step+1));$("back").onclick=()=>run(()=>goStep(S.step-1));
document.addEventListener("keydown",e=>{if(e.key==="Escape"){const d=document.getElementById("dlg");if(d)d.querySelector("button.alt").click()}});
applyStep();
(()=>{const m=document.querySelector('meta[name="app-version"]');if(!m||m.content!=="18")$("err").textContent="index.html and app.js are different versions. Replace BOTH files from the same zip, then press Ctrl+F5."})();
document.querySelectorAll("#sugg button").forEach(b=>b.onclick=()=>{$("q").value=b.textContent;$("q").focus()});

function cartDialog(lines,tot,opener){
 if(S.cartBusy||document.getElementById("cdlg"))return;
 const key=crypto.randomUUID(),have={};S.cart.items.forEach(i=>have[i.product_id]=i.packs);
 const LB={EXACT_MATCH:"Exact match",VALID_VARIANT:"Acceptable alternative",POSSIBLE_ALTERNATIVE:"Needs review",USER_ACCEPTED_SUBSTITUTION:"Approved by you"},
  QL={verified:"amount verified",estimated:"amount estimated",unverified:"amount unverified (1 pack assumed)",none:"no amount in recipe"};
 const rows=lines.map(l=>({l,unc:l.m!=="EXACT_MATCH"||l.qs==="unverified",has:(have[l.product.product_id]||0)>=l.packs,inc:true}));
 const cv=S.opt.coverage||{rows:[],counts:{}},n=cv.counts||{};
 const NL={missing:"Unavailable: no suitable product found",unavailable:"Unavailable: only out-of-stock listings",search_failed:"Search failed: not added",substitution_pending:"Needs review: a possible alternative was not approved",partial:"Needs review: the selected pack covers only part"};
 const nope=cv.rows.filter(r=>NL[r.state]);
 let busy=false,prev=opener||document.activeElement;
 const st=h("p",{class:"muted",role:"status","aria-live":"polite"},"Nothing changes until you press Confirm cart update. No checkout or payment is made."),
  est=h("b",{}),okb=h("button",{type:"button"},"Confirm cart update"),cb=h("button",{type:"button",class:"alt"},"Cancel");
 const upd=()=>{const on=rows.filter(x=>x.inc),t=on.reduce((a,x)=>a+x.l.line_total,0);est.textContent=`${money(t)} for ${on.length} product${on.length===1?"":"s"}`;okb.disabled=busy||!on.length};
 const close=()=>{if(busy)return;ov.remove();document.removeEventListener("keydown",key_);try{prev&&prev.focus()}catch(_){}};
 const key_=e=>{if(!document.getElementById("cdlg"))return;if(e.key==="Escape"){close();return}
  if(e.key==="Tab"){const f=[...ov.querySelectorAll("button:not([disabled]),input:not([disabled])")];if(!f.length)return;const a=f[0],z=f[f.length-1];if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus()}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus()}}};
 const list=rows.map(x=>{const l=x.l,cb2=x.unc?h("input",{type:"checkbox",checked:true,"aria-label":"Include "+l.r.ingredient_name,onchange:e=>{x.inc=e.target.checked;upd()}}):null;
  return h("li",{class:"cd-row"},cb2," ",h("b",{},l.r.ingredient_name),": "+(l.product.brand?l.product.brand+" ":"")+l.product.name+` (${l.product.pack_label||l.product.pack_quantity+" "+l.product.pack_unit}) × ${l.packs} · ${money(l.line_total)}`,
   h("small",{},(l.extra?"Additional item":`${LB[l.m]||"Needs review"} · ${QL[l.qs]||""}`)+(x.has?" · already in your cart, no change needed":"")+(x.unc?" · untick to skip":"")))});
 const kept=S.cart.items.length?S.cart.items.map(i=>h("li",{},`${i.name} × ${i.packs}`)):[h("li",{class:"muted"},"Your cart is empty.")];
 const bill=S.cart.bill&&(S.cart.bill.lines||[]).length;
 const ov=h("div",{id:"cdlg",class:"ov",role:"dialog","aria-modal":"true","aria-labelledby":"cdt",onclick:e=>{if(e.target===ov)close()}},
  h("div",{class:"dlgbox"},h("h3",{id:"cdt"},"Review before updating your Instamart cart"),st,
   h("div",{class:"stats"},h("span",{class:"stat"},h("b",{},String(n.exact||0))," exact"),h("span",{class:"stat"},h("b",{},String(n.alternative||0))," acceptable alternative"),h("span",{class:"stat"+(n.needs_review?" warn":"")},h("b",{},String(n.needs_review||0))," need review"),h("span",{class:"stat"+(n.unavailable?" bad":"")},h("b",{},String(n.unavailable||0))," unavailable"),h("span",{class:"stat"+(n.qty_unverified?" warn":"")},h("b",{},String(n.qty_unverified||0))," amount unverified")),
   h("h4",{},"Will be added or kept at this quantity"),h("ul",{class:"cd"},...list),
   nope.length?h("div",{class:"warnbox"},h("b",{},"Not added:"),h("ul",{},...nope.map(r=>h("li",{},`${r.name}: ${NL[r.state]}`)))):null,
   h("p",{},"Estimated recipe cost (live prices, before fees): ",est,". Verified totals and any fees come from Instamart's live cart bill after the update."),
   bill?h("p",{class:"muted"},"Current live bill: "+(S.cart.bill.to_pay?safe(S.cart.bill.to_pay):"see cost summary")):(S.cart.cart_total!=null?h("p",{class:"muted"},"Current live cart item total: "+money(S.cart.cart_total)):null),
   h("h4",{},"Already in your cart (preserved, never removed)"),h("ul",{class:"cd"},...kept),
   h("div",{class:"foot"},cb,okb)));
 cb.onclick=close;
 okb.onclick=()=>{if(busy||S.cartBusy)return;const on=rows.filter(x=>x.inc);if(!on.length)return;
  busy=S.cartBusy=true;okb.disabled=cb.disabled=true;okb.textContent="Updating cart…";st.textContent="Updating your Instamart cart, then re-checking the live cart. Please keep this open.";
  run(async()=>{try{
    const body=()=>({items:on.map(x=>({product_id:x.l.product.product_id,packs:x.l.packs,source:x.l.extra?"Additional item":x.l.r.ingredient_name})),confirm:true,expected_cart_hash:S.cart.hash,idempotency_key:key,address_id:S.addr,budget:S.budget,allow_over_budget:!!(window._ob&&window._ob.checked)});
    let r;try{r=await api("/api/instamart/cart",body())}catch(e){if(e.data)throw e;st.textContent="Connection problem: re-checking the live cart before anything else happens…";r=await api("/api/instamart/cart",body())}  // same idempotency key: the server only re-verifies if the first call already arrived, it never mutates twice
    setSync("⟳ Confirming live cart…");busy=false;S.cartBusy=false;ov.remove();document.removeEventListener("keydown",key_);await done(r)
   }finally{busy=false;S.cartBusy=false;if(document.getElementById("cdlg"))ov.remove();document.removeEventListener("keydown",key_)}})};
 document.body.append(ov);document.addEventListener("keydown",key_);upd();cb.focus()}

// ---- Search & Add Additional Items: one shared cart state (S.extra) used by Step 2, Step 3 and the final cart update
S.extra=(()=>{try{const a=JSON.parse(sessionStorage.getItem("c2c_extra")||"[]");return Array.isArray(a)?a.filter(x=>x&&x.product&&x.product.product_id&&x.packs>0&&isFinite(+x.product.price)):[]}catch(_){return[]}})();
Object.assign(S,{xq:"",xres:null,xstate:"idle",xseq:0,xerr:"",xlast:""});
function extraTot(){return(S.extra||[]).reduce((a,x)=>a+x.product.price*x.packs,0)}
function pkl(p){return p.pack_label||(p.pack_quantity?p.pack_quantity+" "+(p.pack_unit||""):"pack size unavailable")}
function saveX(){try{sessionStorage.setItem("c2c_extra",JSON.stringify(S.extra))}catch(_){}}
function xSet(id,n){const x=S.extra.find(y=>y.product.product_id===id);if(!x)return;if(n<=0)S.extra=S.extra.filter(y=>y!==x);else x.packs=Math.min(20,n);saveX();renderExtra();updateBar();if(S.step===3)run(()=>renderBasket())}
function xAdd(p){const x=S.extra.find(y=>y.product.product_id===p.product_id);if(x)x.packs=Math.min(20,x.packs+1);else S.extra.push({product:p,packs:1});saveX();renderExtra();updateBar()}
async function xRefresh(){for(const x of S.extra.slice()){const d=await api("/api/instamart/products?q="+encodeURIComponent(x.product.name.slice(0,80))+(S.addr?"&address_id="+encodeURIComponent(S.addr):"")),f=(d.products||[]).find(p=>p.product_id===x.product.product_id);
  if(f&&f.availability&&f.price!=null)x.product=f;else S.extra=S.extra.filter(y=>y!==x)}saveX();renderExtra();updateBar()}  // price/stock re-check; a product that vanished is dropped, not guessed
async function xSearch(){const q=S.xq.trim();if(q.length<2){S.xstate="short";renderExtra();return}
 if(S.mode==="swiggy"&&!S.addrOk){S.xstate="error";S.xerr="Choose your delivery address first.";renderExtra();return}
 const key=q.toLowerCase()+"|"+(S.addr||"");if(key===S.xlast&&S.xstate==="ok")return;  // identical search: no new request
 const seq=++S.xseq;S.xstate="loading";renderExtra();
 try{const d=await api("/api/instamart/products?q="+encodeURIComponent(q)+(S.addr?"&address_id="+encodeURIComponent(S.addr):""));if(seq!==S.xseq)return;  // a newer search owns the screen
  const seen=new Set();S.xres=(d.products||[]).filter(p=>p&&p.product_id&&p.name&&!seen.has(p.product_id)&&seen.add(p.product_id));S.xstate=S.xres.length?"ok":"empty";S.xlast=key}
 catch(e){if(seq!==S.xseq)return;S.xstate="error";S.xerr=safe(e.message)||"Search failed."}
 renderExtra()}
function renderExtra(){const el=$("extrasec");if(!el)return;
 const inp=h("input",{id:"xq",type:"search",placeholder:"Search milk, eggs, bread, snacks, fruits...","aria-label":"Search Instamart for additional items",maxLength:100,value:S.xq,oninput:e=>{S.xq=e.target.value},onkeydown:e=>{if(e.key==="Enter"){e.preventDefault();xSearch()}}});
 const recipeSel={},cand={};((S.opt&&S.opt.items)||[]).forEach(it=>{it.selection.forEach(l=>recipeSel[l.product.product_id]={rid:it.requirement.requirement_id,name:it.requirement.ingredient_name,packs:l.packs});it.candidates.forEach(c=>{if(!(c.product.product_id in cand))cand[c.product.product_id]={rid:it.requirement.requirement_id,name:it.requirement.ingredient_name,sel:it.selection.length>0}})});
 const card=p=>{const id=p.product_id,x=S.extra.find(y=>y.product.product_id===id),rs=recipeSel[id],cd=cand[id],out=p.availability===false;
  return h("div",{class:"pc"+(x?" on":"")+(out?" out":"")},img(p),h("div",{class:"pn"},(p.brand?p.brand+" · ":"")+p.name),h("div",{class:"muted"},pkl(p)),h("div",{},p.rating?"⭐"+p.rating+" · ":"",h("b",{},money(p.price))),
   h("small",{class:out?"err":"muted"},out?"Out of stock":"In stock"),
   rs?h("div",{},h("small",{},`Already selected for recipe ingredient "${safe(rs.name)}" (${rs.packs} pack${rs.packs===1?"":"s"}). `),h("button",{class:"alt",onclick:()=>run(async()=>{S.packs[rs.rid]=Math.min(20,rs.packs+1);await optimize();renderExtra()})},"Add one more pack there")):
   (cd&&cd.sel?h("div",{},h("small",{},`Could also fulfil "${safe(cd.name)}", which already has a selection. `),h("button",{class:"alt",onclick:()=>run(async()=>{S.over[cd.rid]=id;delete S.packs[cd.rid];await optimize();renderExtra()})},"Use for "+safe(cd.name))):null),
   out?null:x?h("div",{},h("button",{class:"alt","aria-label":"Decrease quantity of "+p.name,onclick:()=>xSet(id,x.packs-1)},"−")," ",String(x.packs)," ",h("button",{class:"alt","aria-label":"Increase quantity of "+p.name,onclick:()=>xSet(id,x.packs+1)},"+")," ",h("button",{class:"lnk",onclick:()=>xSet(id,0)},"Remove")):
    (rs?null:h("button",{onclick:()=>xAdd(p)},"Add as additional item")))};
 const body=S.xstate==="loading"?h("p",{class:"muted",role:"status"},"Searching Instamart…"):S.xstate==="short"?h("p",{class:"muted"},"Type at least 2 characters."):
  S.xstate==="empty"?h("p",{class:"muted",role:"status"},`No products found for "${S.xq.trim()}". Try another word.`):
  S.xstate==="error"?h("p",{class:"err",role:"alert"},S.xerr+" ",h("button",{class:"alt",onclick:()=>{S.xlast="";xSearch()}},"Retry")):
  S.xstate==="ok"?h("div",{class:"xres"},...(S.xres||[]).slice(0,12).map(card)):null;
 const added=S.extra.length?h("div",{class:"sel"},h("b",{},`Additional items in your cart list (${S.extra.length}): `),S.extra.map(x=>`${x.product.name} × ${x.packs}`).join(" · ")+" · "+money(extraTot())):null;
 el.replaceChildren(h("div",{class:"card xbox"},h("h3",{style:"margin:0 0 4px"},"+ Add additional items"),h("p",{class:"muted",style:"margin:0 0 8px"},"Looking for something else? Search Instamart and add it to your cart."),
  h("div",{class:"xrow"},h("label",{for:"xq",class:"sr"},"Search Instamart"),inp,h("button",{type:"button",onclick:xSearch,disabled:S.xstate==="loading"},"Search"),S.xq||S.xres?h("button",{type:"button",class:"alt",onclick:()=>{S.xseq++;S.xq="";S.xres=null;S.xstate="idle";S.xlast="";renderExtra()}},"Clear"):null),body,added))}
renderExtra();

{const _rp=renderProds;renderProds=function(){const r=_rp.apply(this,arguments);renderExtra();return r}}  // duplicate hints stay in sync with recipe selections
