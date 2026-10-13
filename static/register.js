f.onsubmit = function(e){
  e.preventDefault(); msg.textContent = "";
  if(f.mdp.value !== mdp2.value){ msg.textContent = "Les deux mots de passe ne sont pas identiques."; return; }
  fetch("/api/register",{method:"POST",body:new FormData(f)}).then(function(r){
    if(r.ok){ location.href = "/admin"; return; }
    msg.textContent = r.status===401 ? "Code d'installation incorrect." : r.status===403 ? "Un compte gérant existe déjà. Connectez-vous sur /admin." : "Vérifiez le nom, l'adresse e-mail et le mot de passe (8 caractères minimum).";
  });
};
