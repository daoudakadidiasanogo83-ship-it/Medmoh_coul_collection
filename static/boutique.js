const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const RED=matchMedia("(prefers-reduced-motion:reduce)").matches;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const F=n=>n.toLocaleString("fr-FR")+" FCFA";
const ld=(k,d)=>{try{return JSON.parse(localStorage.getItem(k))||d}catch(e){return d}};
const sv=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}};
const ico=n=>`<svg class="i"><use href="#i-${n}"/></svg>`;
let P=[],cats=[],newest=new Set(),WA="22300000000",cart=ld("cart",{}),fav=ld("fav",{}),cat="Tout",mot="",tri="new",cur=null,qty=1,sz="";
const PAGE=12;let shown=PAGE,lastSig="",seen=ld("seen",[]);
/*DEMO*/
const pic=(p,cls,extra)=>`<div class="pic ${cls||""}" style="--c:${esc(p.c)}">${p.img?`<img src="${esc(p.img)}" alt="${esc(p.nom)}">`:`<span>${esc(p.nom[0])}</span>`}${extra||""}</div>`;
const card=p=>`<article class="card" tabindex="0" data-id="${p.id}">${pic(p,"",`${newest.has(p.id)?'<em class="new">Nouveau</em>':""}<button class="heart" data-h="${p.id}" aria-pressed="${!!fav[p.id]}" aria-label="Favori">${ico("heart")}</button><button class="quick" data-a="${p.id}" aria-label="Ajouter ${esc(p.nom)} au panier">${ico("plus")}</button>`)}<div class="ci"><h3>${esc(p.nom)}</h3><p>${esc(p.cat)}${p.vendeur?" · "+esc(p.vendeur):""}</p><b>${F(p.prix)}</b></div></article>`;
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target)}}),{threshold:.08});
function pills(){$("#pills").innerHTML=["Tout","♥ Favoris",...cats].map(c=>`<button class="pill" aria-pressed="${c===cat}" data-c="${esc(c)}">${esc(c)}</button>`).join("")}
function render(){
 const m=mot.trim().toLowerCase();
 const l=P.filter(p=>(cat==="Tout"||(cat==="♥ Favoris"?fav[p.id]:p.cat===cat))&&p.nom.toLowerCase().includes(m));
 l.sort((a,b)=>tri==="asc"?a.prix-b.prix:tri==="desc"?b.prix-a.prix:b.id-a.id);
 const sig=cat+"|"+m+"|"+tri;if(sig!==lastSig){shown=PAGE;lastSig=sig}
 $("#nb").textContent=l.length+" produit"+(l.length>1?"s":"");
 $("#moreW").innerHTML=l.length>shown?`<button class="pill more" id="more">Voir plus (${l.length-shown})</button>`:"";
 $("#grid").innerHTML=l.length?l.slice(0,shown).map(card).join(""):`<div class="empty"><p>${cat==="♥ Favoris"?"Touchez le cœur d'un produit pour le retrouver ici.":"Aucun produit ne correspond."}</p><button class="pill" id="raz">Effacer les filtres</button></div>`;
 $$(".card").forEach((c,i)=>{c.style.setProperty("--d",(i%4)*70+"ms");io.observe(c)});
}
function cartUI(){
 let t=0,n=0;
 const rows=Object.keys(cart).map(k=>{const [id,tl]=k.split("|");const p=P.find(x=>x.id==id);if(!p)return"";const q=cart[k];t+=p.prix*q;n+=q;
  return `<div class="ln">${pic(p,"mini")}<div><b>${esc(p.nom)}</b><small>${tl?"Taille "+esc(tl)+" · ":""}${F(p.prix)}</small></div><div class="st"><button data-m="${esc(k)}" aria-label="Retirer un">−</button><span>${q}</span><button data-p="${esc(k)}" aria-label="Ajouter un">+</button></div></div>`}).join("");
 $("#lines").innerHTML=rows||`<p class="mute">Votre panier est vide.<br>Touchez le + sur un produit pour l'ajouter.</p>`;
 countTo($("#tot"),t);$("#send").disabled=!n;
 $$(".cnt").forEach(e=>{e.textContent=n;e.hidden=!n});
}
function countTo(el,to){const from=+el.dataset.v||0;el.dataset.v=to;if(RED||from===to){el.textContent=F(to);return}const t0=performance.now();(function f(t){const k=Math.min(1,(t-t0)/400);el.textContent=F(Math.round(from+(to-from)*(1-Math.pow(1-k,3))));if(k<1)requestAnimationFrame(f)})(t0)}
function toast(m){const t=$("#toast");t.textContent=m;t.classList.add("on");clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove("on"),1800)}
function fly(a){
 const t=$$(".cartbtn").find(e=>e.offsetParent);if(RED||!a||!t)return;
 const r=a.getBoundingClientRect(),o=t.getBoundingClientRect(),d=document.createElement("i");
 d.className="fly";d.style.cssText=`left:${r.left+r.width/2-10}px;top:${r.top+r.height/2-10}px`;document.body.appendChild(d);
 d.animate([{transform:"scale(1)"},{transform:`translate(${o.left+o.width/2-r.left-r.width/2}px,${o.top+o.height/2-r.top-r.height/2}px) scale(.3)`,opacity:.5}],{duration:600,easing:"cubic-bezier(.5,-.2,.7,.4)"}).onfinish=()=>{d.remove();t.classList.remove("bump");void t.offsetWidth;t.classList.add("bump")};
}
function add(id,n,from,tl){const k=id+"|"+(tl||"");cart[k]=Math.min(20,(cart[k]||0)+n);sv("cart",cart);fly(from);cartUI();toast("Ajouté au panier")}
function chg(id,n){cart[id]+=n;if(cart[id]<=0)delete cart[id];sv("cart",cart);cartUI()}
function drawP(){const p=cur;$("#pdc").innerHTML=pic(p,"big",`<button class="x" data-close aria-label="Fermer">${ico("x")}</button>`)+`<div class="pbody"><p class="mute">${esc(p.cat)}${p.vendeur?" · Vendu par "+esc(p.vendeur):""}</p><h2>${esc(p.nom)}</h2><b class="pr">${F(p.prix)}</b>${p.description?`<p class="desc">${esc(p.description)}</p>`:""}${p.tailles?`<p class="lab">Taille${sz?"":" (à choisir)"}</p><div class="szs">${p.tailles.split(",").map(t=>`<button class="pill sz" data-sz="${esc(t)}" aria-pressed="${t===sz}">${esc(t)}</button>`).join("")}</div>`:""}<ul class="tr"><li>Paiement à la livraison</li><li>Livraison partout au Mali</li><li>Confirmation rapide sur WhatsApp</li></ul><div class="row"><div class="st"><button data-q="-1" aria-label="Moins">−</button><span>${qty}</span><button data-q="1" aria-label="Plus">+</button></div><button class="cta" data-addp ${p.tailles&&!sz?"disabled":""}>${p.tailles&&!sz?"Choisissez une taille":"Ajouter · "+F(p.prix*qty)}</button><button class="share" data-share aria-label="Partager">${ico("share")}</button></div></div>`}
function openP(id){cur=P.find(p=>p.id==id);if(!cur)return;qty=1;sz="";drawP();$("#pd").showModal();seen=[cur.id,...seen.filter(x=>x!==cur.id)].slice(0,8);sv("seen",seen);rvRender();try{history.replaceState(null,"","#p="+cur.id)}catch(e){}}
function openCart(){$("#ok").hidden=true;$("#form").hidden=false;$("#err").textContent="";cartUI();$("#cart").showModal()}
function go(w){
 if(w==="home")scrollTo({top:0});
 if(w==="shop")$("#catalogue").scrollIntoView();
 if(w==="fav"){cat="♥ Favoris";pills();render();$("#catalogue").scrollIntoView()}
 if(w==="cart")openCart();
}
document.addEventListener("click",e=>{
 const t=e.target,h=s=>t.closest(s);let el;
 if(el=h("[data-h]")){const id=el.dataset.h;if(fav[id])delete fav[id];else fav[id]=1;sv("fav",fav);if(cat==="♥ Favoris")render();else el.setAttribute("aria-pressed",!!fav[id]);return}
 if(el=h("[data-a]")){const p=P.find(x=>x.id==el.dataset.a);if(p&&p.tailles)openP(p.id);else add(el.dataset.a,1,el);return}
 if(el=h(".card")){openP(el.dataset.id);return}
 if(el=h("[data-hero]")){openP(el.dataset.hero);return}
 if(el=h("[data-c]")){cat=el.dataset.c;pills();render();return}
 if(h("#raz")){cat="Tout";mot="";$("#q").value="";pills();render();return}
 if(el=h("[data-m]"))chg(el.dataset.m,-1);
 if(el=h("[data-p]"))chg(el.dataset.p,1);
 if(h("#more")){shown+=PAGE;render();return}
 if(h("[data-share]")){const u=location.origin+location.pathname+"#p="+cur.id,tx=`${cur.nom} – ${F(cur.prix)} chez MEDMOHcoul collection`;if(navigator.share)navigator.share({title:cur.nom,text:tx,url:u}).catch(()=>{});else window.open("https://wa.me/?text="+encodeURIComponent(tx+"\n"+u),"_blank","noopener");return}
 if(el=h("[data-sz]")){sz=el.dataset.sz;drawP();return}
 if(el=h("[data-q]")){qty=Math.max(1,Math.min(20,qty+ +el.dataset.q));drawP()}
 if(el=h("[data-addp]")){add(cur.id,qty,el,sz);$("#pd").close()}
 if(h("[data-close]"))t.closest("dialog").close();
 if(el=h("[data-go]"))go(el.dataset.go);
 if(h("[data-cart]"))openCart();
 if(t.tagName==="DIALOG"){const r=t.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)t.close()}
});
document.addEventListener("keydown",e=>{if(e.key==="Enter"&&e.target.classList.contains("card"))openP(e.target.dataset.id);if(e.key==="/"&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)){e.preventDefault();$("#q").focus()}});
$("#q").oninput=e=>{mot=e.target.value;if(mot&&scrollY<300)$("#catalogue").scrollIntoView();render()};
$("#tri").onchange=e=>{tri=e.target.value;render()};
$("#pd").addEventListener("close",()=>{if(/^#p=/.test(location.hash))try{history.replaceState(null,"",location.pathname+location.search)}catch(e){}});
$("#send").onclick=()=>{
 const nom=$("#nom").value.trim(),adr=$("#adr").value.trim();
 if(!nom||!adr){$("#err").textContent="Indiquez votre nom et votre adresse de livraison.";(nom?$("#adr"):$("#nom")).focus();return}
 let t=0;const L=Object.keys(cart).map(k=>{const [id,tl]=k.split("|");const p=P.find(x=>x.id==id);if(!p)return"";t+=p.prix*cart[k];return`- ${cart[k]} x ${p.nom}${tl?" (taille "+tl+")":""} (${F(p.prix)})`}).filter(Boolean);
 window.open("https://wa.me/"+WA+"?text="+encodeURIComponent(`Bonjour, je souhaite commander :\n${L.join("\n")}\nTotal : ${F(t)}\nNom : ${nom}\nAdresse : ${adr}\nPaiement à la livraison.`),"_blank","noopener");
 cart={};sv("cart",cart);cartUI();$("#form").hidden=true;$("#ok").hidden=false;
};
function rvRender(){const l=seen.map(id=>P.find(p=>p.id==id)).filter(Boolean);$("#rv").hidden=!l.length;$("#rvr").innerHTML=l.map(p=>`<button data-hero="${p.id}">${pic(p)}<span class="n">${esc(p.nom)}</span></button>`).join("")}
function init(d){
 WA=d.wa;P=d.items;newest=new Set([...P].sort((a,b)=>b.id-a.id).slice(0,3).map(p=>p.id));
 cats=[...new Set(P.map(p=>p.cat))];pills();render();cartUI();rvRender();const hm=location.hash.match(/^#p=(\d+)$/);if(hm)openP(hm[1]);
 $("#wa").href=$("#wa2").href="https://wa.me/"+WA;
 $("#fcs").innerHTML=P.slice(0,3).map((p,i)=>`<button class="fc" data-hero="${p.id}" style="--c:${esc(p.c)};--rot:${[-7,0,7][i]}deg;${p.img?`background-image:linear-gradient(transparent 45%,rgba(0,0,0,.7)),url('${esc(p.img)}')`:""}"><span>${esc(p.nom)}</span><small>${F(p.prix)}</small></button>`).join("");
}
function fail(){$("#grid").innerHTML='<div class="empty">Impossible de charger les produits. Réessayez dans un instant.</div>'}
$("#mqi").innerHTML=$("#mqi").innerHTML.repeat(6);
if(!RED){
 const W=["boubous","robes","ensembles","accessoires"];let wi=0,r=$("#rot");
 setInterval(()=>{r.classList.add("out");setTimeout(()=>{wi=(wi+1)%W.length;r.textContent=W[wi];r.classList.remove("out")},260)},2400);
 const hero=$(".hero");hero.addEventListener("pointermove",e=>{const b=hero.getBoundingClientRect(),x=(e.clientX-b.left)/b.width-.5,y=(e.clientY-b.top)/b.height-.5;$$(".fc").forEach((c,i)=>c.style.translate=`${x*(16+i*10)}px ${y*(16+i*10)}px`)});
}
cartUI();
const root=document.documentElement;
try{const th=localStorage.getItem("theme");if(th)root.dataset.theme=th}catch(e){}
$("#tgl").onclick=()=>{const dark=root.dataset.theme?root.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;const n=dark?"light":"dark";root.dataset.theme=n;try{localStorage.setItem("theme",n)}catch(e){}};
addEventListener("scroll",()=>{const h=root.scrollHeight-innerHeight;$("#prog").style.width=(h>0?scrollY/h*100:0)+"%";$("#up").classList.toggle("on",scrollY>700)},{passive:true});
$("#up").onclick=()=>scrollTo({top:0});
addEventListener("offline",()=>toast("Vous êtes hors ligne"));
fetch("/api/produits").then(r=>r.json()).then(init).catch(fail);
