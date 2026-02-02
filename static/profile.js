let profile=null,myShoes=[],theirShoes=[],offerShoes=[],wantShoes=[]
const $=q=>document.querySelector(q),$$=q=>document.querySelectorAll(q)
const money=v=>v.toFixed(2)
const rarClass=r=>({common:'rar-common',uncommon:'rar-uncommon',rare:'rar-rare',epic:'rar-epic',legendary:'rar-legendary',mythic:'rar-mythic',secret:'rar-secret',dexies:'rar-dexies',lebos:'rar-lebos'}[r]||'rar-common')

const toast=(msg,type='success')=>{
  let t=$('#toast')
  t.textContent=msg
  t.className='toast show '+type
  setTimeout(()=>t.classList.remove('show'),2500)
}

const formatDate=(ts)=>{
  if(!ts)return '-'
  let d=new Date(ts*1000)
  return d.toLocaleDateString()
}

const render=()=>{
  if(!profile)return
  $('#p-name').textContent=profile.username
  $('#p-balance').textContent='$'+money(profile.balance)
  $('#p-shoes').textContent=profile.shoes
  $('#p-joined').textContent=formatDate(profile.joined)
  
  if(profile.is_me)$('#btn-trade').classList.add('hidden')
  
  let grid=$('#shoes-grid'),empty=$('#shoes-empty')
  let allShoes=[...profile.hold,...profile.appraised.map(a=>({...a,qty:1,appraised:true}))]
  
  if(allShoes.length){
    grid.innerHTML=allShoes.map(s=>`
      <div class="shoe-item">
        <div class="shoe-item-name">${s.name}</div>
        <div class="shoe-item-rarity ${rarClass(s.rarity)}">${s.rarity.toUpperCase()}</div>
        <div class="shoe-item-qty">${s.appraised?'⭐ '+s.rating.toFixed(1):'×'+s.qty}</div>
      </div>
    `).join('')
    empty.classList.add('hidden')
  }else{
    grid.innerHTML=''
    empty.classList.remove('hidden')
  }
}

const getKey=(s)=>s.appraised?'a_'+s.appraisal_id:'h_'+s.id

const calcTotals=()=>{
  let offerTotal=(parseFloat($('#offer-cash').value)||0)
  offerShoes.forEach(s=>{
    let shoe=myShoes.find(x=>getKey(x)===s.key)
    if(shoe)offerTotal+=(shoe.price||0)*s.qty
  })
  let wantTotal=(parseFloat($('#want-cash').value)||0)
  wantShoes.forEach(s=>{
    let shoe=theirShoes.find(x=>getKey(x)===s.key)
    if(shoe)wantTotal+=(shoe.price||0)*s.qty
  })
  let ot=$('#offer-total')
  let wt=$('#want-total')
  if(ot)ot.textContent='$'+money(offerTotal)
  if(wt)wt.textContent='$'+money(wantTotal)
}

const renderTradeModal=()=>{
  let yourGrid=$('#your-shoes')
  let theirGrid=$('#their-shoes')
  
  yourGrid.innerHTML=myShoes.map(s=>{
    let key=getKey(s)
    let sel=offerShoes.find(x=>x.key===key)
    let label=s.appraised?`⭐${s.rating.toFixed(1)} ${s.name}`:s.name
    return `<div class="shoe-select-item${sel?' selected':''}" data-key="${key}">
      <div class="shoe-select-name">${label}</div>
      <span class="shoe-price">$${money(s.price||0)}</span>
      <small>${s.appraised?'Appraised':'Own: '+s.qty}</small>
      ${sel?`<div class="shoe-qty-select">
        <button class="qty-btn" data-key="${key}" data-action="offer-dec">-</button>
        <span>${sel.qty}</span>
        <button class="qty-btn" data-key="${key}" data-action="offer-inc">+</button>
      </div>`:''}
    </div>`
  }).join('')
  
  theirGrid.innerHTML=theirShoes.map(s=>{
    let key=getKey(s)
    let sel=wantShoes.find(x=>x.key===key)
    let label=s.appraised?`⭐${s.rating.toFixed(1)} ${s.name}`:s.name
    return `<div class="shoe-select-item${sel?' selected':''}" data-key="${key}">
      <div class="shoe-select-name">${label}</div>
      <span class="shoe-price">$${money(s.price||0)}</span>
      <small>${s.appraised?'Appraised':'Has: '+s.qty}</small>
      ${sel?`<div class="shoe-qty-select">
        <button class="qty-btn" data-key="${key}" data-action="want-dec">-</button>
        <span>${sel.qty}</span>
        <button class="qty-btn" data-key="${key}" data-action="want-inc">+</button>
      </div>`:''}
    </div>`
  }).join('')
  
  $('#offer-selected').innerHTML=offerShoes.map(s=>`<span class="selected-shoe">${s.name}${s.qty>1?' ×'+s.qty:''}</span>`).join('')
  $('#want-selected').innerHTML=wantShoes.map(s=>`<span class="selected-shoe">${s.name}${s.qty>1?' ×'+s.qty:''}</span>`).join('')
  calcTotals()
  
  yourGrid.querySelectorAll('.shoe-select-item').forEach(el=>{
    el.onclick=(e)=>{
      if(e.target.classList.contains('qty-btn'))return
      let key=el.dataset.key
      let shoe=myShoes.find(x=>getKey(x)===key)
      if(!shoe)return
      let idx=offerShoes.findIndex(x=>x.key===key)
      if(idx>=0)offerShoes.splice(idx,1)
      else offerShoes.push({key,id:shoe.id,name:shoe.name,qty:1,max:shoe.qty,appraised:shoe.appraised,appraisal_id:shoe.appraisal_id})
      renderTradeModal()
    }
  })
  
  theirGrid.querySelectorAll('.shoe-select-item').forEach(el=>{
    el.onclick=(e)=>{
      if(e.target.classList.contains('qty-btn'))return
      let key=el.dataset.key
      let shoe=theirShoes.find(x=>getKey(x)===key)
      if(!shoe)return
      let idx=wantShoes.findIndex(x=>x.key===key)
      if(idx>=0)wantShoes.splice(idx,1)
      else wantShoes.push({key,id:shoe.id,name:shoe.name,qty:1,max:shoe.qty,appraised:shoe.appraised,appraisal_id:shoe.appraisal_id})
      renderTradeModal()
    }
  })
  
  document.querySelectorAll('.qty-btn').forEach(btn=>{
    btn.onclick=(e)=>{
      e.stopPropagation()
      let key=btn.dataset.key
      let action=btn.dataset.action
      if(action==='offer-dec'){
        let s=offerShoes.find(x=>x.key===key)
        if(s&&s.qty>1){s.qty--;renderTradeModal()}
      }else if(action==='offer-inc'){
        let s=offerShoes.find(x=>x.key===key)
        let shoe=myShoes.find(x=>getKey(x)===key)
        if(s&&shoe&&s.qty<shoe.qty){s.qty++;renderTradeModal()}
      }else if(action==='want-dec'){
        let s=wantShoes.find(x=>x.key===key)
        if(s&&s.qty>1){s.qty--;renderTradeModal()}
      }else if(action==='want-inc'){
        let s=wantShoes.find(x=>x.key===key)
        let shoe=theirShoes.find(x=>getKey(x)===key)
        if(s&&shoe&&s.qty<shoe.qty){s.qty++;renderTradeModal()}
      }
    }
  })
}

const openTradeModal=async()=>{
  let[r1,r2]=await Promise.all([
    fetch('/api/my-shoes'),
    fetch('/api/user-shoes/'+window.PROFILE_USER)
  ])
  if(r1.ok)myShoes=await r1.json()
  if(r2.ok)theirShoes=await r2.json()
  offerShoes=[]
  wantShoes=[]
  $('#offer-cash').value=0
  $('#want-cash').value=0
  renderTradeModal()
  $('#trade-modal').classList.remove('hidden')
}

const submitTrade=async()=>{
  let offerCash=parseFloat($('#offer-cash').value)||0
  let wantCash=parseFloat($('#want-cash').value)||0
  
  if(offerShoes.length===0&&wantShoes.length===0&&offerCash===0&&wantCash===0){
    toast('Add something to trade','error')
    return
  }
  
  let r=await fetch('/api/trade/create',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      to_user:window.PROFILE_USER,
      offer_shoes:offerShoes.map(s=>({id:s.id,qty:s.qty,appraised:s.appraised,appraisal_id:s.appraisal_id})),
      offer_cash:offerCash,
      want_shoes:wantShoes.map(s=>({id:s.id,qty:s.qty,appraised:s.appraised,appraisal_id:s.appraisal_id})),
      want_cash:wantCash
    })
  })
  
  if(r.ok){
    let j=await r.json()
    if(j.ok){
      toast('Trade request sent!')
      $('#trade-modal').classList.add('hidden')
    }else toast(j.error||'Failed','error')
  }else toast('Request failed','error')
}

const fetchProfile=async()=>{
  let r=await fetch('/api/user/'+window.PROFILE_USER)
  if(r.ok){profile=await r.json();render()}
  else{$('#p-name').textContent='User not found'}
}

const fetchBalance=async()=>{
  let r=await fetch('/api/state')
  if(r.ok){let s=await r.json();$('#bal').textContent=money(s.balance)}
}

const updBadge=async()=>{
  let r=await fetch('/api/trade-count')
  if(r.ok){
    let j=await r.json()
    let b=$('#trade-badge')
    if(b){
      if(j.count>0){b.textContent=j.count;b.classList.remove('hidden')}
      else{b.classList.add('hidden')}
    }
  }
}

$('#btn-trade').onclick=openTradeModal
$('#modal-close').onclick=()=>$('#trade-modal').classList.add('hidden')
$('#trade-modal').onclick=(e)=>{if(e.target.id==='trade-modal')$('#trade-modal').classList.add('hidden')}
$('#submit-trade').onclick=submitTrade
$('#offer-cash').oninput=calcTotals
$('#want-cash').oninput=calcTotals

fetchProfile()
fetchBalance()
updBadge()
setInterval(updBadge,10000)
