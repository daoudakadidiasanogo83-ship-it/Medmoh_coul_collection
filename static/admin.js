var L = [];
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function charger(){
  fetch("/api/admin/produits").then(function(r){if(!r.ok){location.href="/admin/logout";return []}return r.json()}).then(function(d){
    L = d;
    t.innerHTML = d.map(function(p){
      return '<tr><td>'+(p.img?'<img src="'+esc(p.img)+'" alt="">':'<div class="sw" style="background:'+esc(p.c)+'"></div>')+'</td>'+
      '<td><strong>'+esc(p.nom)+'</strong><br><small>'+esc(p.cat)+(p.actif?'':' · masqué')+(p.vendeur&&ME.role==='gerant'?' · '+esc(p.vendeur):'')+'</small></td>'+
      '<td>'+p.prix.toLocaleString("fr-FR")+' FCFA</td>'+
      '<td><button data-e="'+p.id+'">Modifier</button> <button data-d="'+p.id+'">Supprimer</button></td></tr>';
    }).join("") || '<tr><td>Aucun produit. Ajoutez le premier ci-dessus.</td></tr>';
  });
}
function vider(){ f.reset(); f.elements.pid.value=""; annuler.hidden=true; ok.textContent="Ajouter le produit"; }
f.onsubmit = function(e){
  e.preventDefault();
  fetch("/api/admin/produits",{method:"POST",body:new FormData(f)}).then(function(r){
    if(!r.ok){ alert("Vérifiez les champs (photo en JPG, PNG ou WEBP, 5 Mo maximum)."); return; }
    vider(); charger();
  });
};
annuler.onclick = vider;
document.addEventListener("click", function(e){
  var b = e.target;
  if(b.dataset.e){
    var p = L.filter(function(x){return x.id==b.dataset.e})[0], el = f.elements;
    el.pid.value=p.id; el.nom.value=p.nom; el.description.value=p.description||""; el.tailles.value=p.tailles||""; el.cat.value=p.cat; el.prix.value=p.prix; el.c.value=p.c; el.actif.checked=!!p.actif;
    annuler.hidden=false; ok.textContent="Enregistrer les changements"; scrollTo(0,0);
  }
  if(b.dataset.d && confirm("Supprimer ce produit définitivement ?")){
    fetch("/api/admin/produits/"+b.dataset.d,{method:"DELETE"}).then(charger);
  }
});
var ME = {};
function chargerEquipe(){
  fetch("/api/admin/vendeurs").then(function(r){return r.json()}).then(function(d){
    tv.innerHTML = d.map(function(v){
      var g = v.role==="gerant", agir = !g || ME.proprio;
      return '<tr><td><strong>'+esc(v.nom)+'</strong> <small>('+(g?'gérant':'vendeur')+')</small><br><small>'+esc(v.email)+'</small></td><td>'+(agir?'<button data-m="'+v.id+'">Nouveau mot de passe</button> <button data-r="'+v.id+'">Retirer</button>':'')+'</td></tr>';
    }).join("") || '<tr><td>Personne d\'autre pour le moment.</td></tr>';
  });
}
fv.onsubmit = function(e){
  e.preventDefault();
  fetch("/api/admin/vendeurs",{method:"POST",body:new FormData(fv)}).then(function(r){
    if(r.status===409){ alert("Cet email est déjà utilisé."); return; }
    if(!r.ok){ alert("Vérifiez le nom, l'email et le mot de passe (8 caractères minimum)."); return; }
    fv.reset(); chargerEquipe();
  });
};
document.addEventListener("click", function(e){
  var b = e.target;
  if(b.dataset.r && confirm("Retirer cette personne de l'équipe ? Ses produits restent sur le site.")){
    fetch("/api/admin/vendeurs/"+b.dataset.r,{method:"DELETE"}).then(function(){ chargerEquipe(); charger(); });
  }
  if(b.dataset.m){
    var m = prompt("Nouveau mot de passe (8 caractères minimum) :");
    if(m){ var d = new FormData(); d.append("mdp", m);
      fetch("/api/admin/vendeurs/"+b.dataset.m+"/mdp",{method:"POST",body:d}).then(function(r){ alert(r.ok ? "Mot de passe changé." : "Mot de passe trop court."); }); }
  }
});
fetch("/api/admin/moi").then(function(r){ if(!r.ok){ location.href="/admin/logout"; throw 0; } return r.json(); }).then(function(m){
  ME = m; fv.elements.role.hidden = !m.proprio; moi.textContent = "Connecté : "+m.nom+(m.role==="gerant"?" (gérant)":" (vendeur)");
  if(m.role==="gerant"){ eq.hidden = false; chargerEquipe(); }
  charger();
});

fm.onsubmit = function(e){
  e.preventDefault();
  fetch("/api/admin/mon-mdp",{method:"POST",body:new FormData(fm)}).then(function(r){
    if(r.status===401){ alert("Mot de passe actuel incorrect."); return; }
    if(r.status===429){ alert("Trop de tentatives, réessayez plus tard."); return; }
    if(!r.ok){ alert("Le nouveau mot de passe doit faire 8 à 128 caractères."); return; }
    fm.reset(); alert("Mot de passe changé.");
  });
};
