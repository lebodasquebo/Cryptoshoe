let users=[],trades={incoming:[],outgoing:[]},currentTrade=null
const $=q=>document.querySelector(q),$$=q=>document.querySelectorAll(q)
const money=v=>v.toFixed(2)
const rarClass=r=>({common:'rar-common',uncommon:'rar-uncommon',rare:'rar-rare',epic:'rar-epic',legendary:'rar-legendary',mythic:'rar-mythic',secret:'rar-secret'}[r]||'rar-common')

const toast=(msg,type='success')=>{
  let t=$('#toast')
  t.textContent=msg
  t.className='toast show '+type
  setTimeout(()=>t.classList.remove('show'),2500)
}

const userCard=(u)=>`<a href="/user/${u.username}" class="user-card${u.is_me?' is-me':''}">
  <div class="user-avatar">👤</div>
  <div class="user-name">${u.username}${u.is_me?' (you)':''}</div>
  <div class="user-stats">
    <div class="user-stat"><span class="user-stat-val">$${money(u.balance)}</span><span>Balance</span></div>
    <div class="user-stat"><span class="user-stat-val">${u.shoes}</span><span>Shoes</span></div>
  </div>
</a>`

const shoePreview=(shoes)=>{
  if(!shoes||!shoes.length)return ''
  return shoes.slice(0,2).map(s=>`${s.name}${s.qty>1?' ×'+s.qty:''}`).join(', ')+(shoes.length>2?` +${shoes.length-2} more`:'')
}

const tradeItem=(t,type)=>{
  let offer=t.offer_shoes||[]
  let want=t.want_shoes||[]
  let offerVal=(t.offer_cash||0)+offer.reduce((s,x)=>(x.price||0)*(x.qty||1)+s,0)
  let wantVal=(t.want_cash||0)+want.reduce((s,x)=>(x.price||0)*(x.qty||1)+s,0)
  
  if(type==='incoming'){
    return `<div class="trade-item" onclick="viewTrade(${t.id})">
      <div class="trade-user">From: ${t.from_username}</div>
      <div class="trade-details">
        <div>Offers: $${money(offerVal)} ${offer.length?'('+offer.length+' shoes)':''}</div>
        <div>Wants: $${money(wantVal)} ${want.length?'('+want.length+' shoes)':''}</div>
      </div>
      <div class="trade-preview">${shoePreview(offer)} → ${shoePreview(want)||'$'+money(t.want_cash||0)}</div>
    </div>`
  }else{
    return `<div class="trade-item" onclick="viewOutgoing(${t.id})">
      <div class="trade-user">To: ${t.to_username}</div>
      <div class="trade-details">
        <div>You offer: $${money(offerVal)}</div>
        <div>You want: $${money(wantVal)}</div>
      </div>
      <button class="trade-cancel" onclick="event.stopPropagation();declineTrade(${t.id})">Cancel</button>
    </div>`
  }
}

const render=()=>{
  let grid=$('#users-grid'),empty=$('#users-empty')
  if(users.length){grid.innerHTML=users.map(u=>userCard(u)).join('');empty.classList.add('hidden')}
  else{grid.innerHTML='';empty.classList.remove('hidden')}
  
  let inc=$('#incoming-trades'),incE=$('#incoming-empty')
  let out=$('#outgoing-trades'),outE=$('#outgoing-empty')
  
  if(trades.incoming.length){inc.innerHTML=trades.incoming.map(t=>tradeItem(t,'incoming')).join('');incE.classList.add('hidden')}
  else{inc.innerHTML='';incE.classList.remove('hidden')}
  
  if(trades.outgoing.length){out.innerHTML=trades.outgoing.map(t=>tradeItem(t,'outgoing')).join('');outE.classList.add('hidden')}
  else{out.innerHTML='';outE.classList.remove('hidden')}
}

const renderShoeList=(shoes,container)=>{
  if(!shoes||!shoes.length){container.innerHTML='<div class="td-shoe"><span style="color:var(--text3)">No shoes</span></div>';return 0}
  let total=0
  container.innerHTML=shoes.map(s=>{
    let val=(s.price||0)*(s.qty||1)
    total+=val
    return `<div class="td-shoe">
      <div><span class="td-shoe-name">${s.name}</span><div class="td-shoe-info">${s.rarity} ${s.qty>1?'×'+s.qty:''}</div></div>
      <span class="td-shoe-price">$${money(val)}</span>
    </div>`
  }).join('')
  return total
}

window.viewTrade=(id)=>{
  currentTrade=trades.incoming.find(t=>t.id===id)
  if(!currentTrade)return
  
  $('#td-from').textContent=currentTrade.from_username
  let offer=currentTrade.offer_shoes||[]
  let want=currentTrade.want_shoes||[]
  
  let getTotal=renderShoeList(offer,$('#td-get-shoes'))
  let giveTotal=renderShoeList(want,$('#td-give-shoes'))
  
  let getCash=currentTrade.offer_cash||0
  let giveCash=currentTrade.want_cash||0
  
  $('#td-get-cash').textContent=getCash>0?'+$'+money(getCash)+' cash':''
  $('#td-give-cash').textContent=giveCash>0?'-$'+money(giveCash)+' cash':''
  
  $('#td-get-total').textContent='$'+money(getTotal+getCash)
  $('#td-give-total').textContent='$'+money(giveTotal+giveCash)
  
  $('#trade-detail-modal').classList.remove('hidden')
}

window.viewOutgoing=(id)=>{
  let t=trades.outgoing.find(x=>x.id===id)
  if(!t)return
  currentTrade=t
  $('#td-from').textContent='You → '+t.to_username
  let offer=t.offer_shoes||[]
  let want=t.want_shoes||[]
  
  let giveTotal=renderShoeList(offer,$('#td-give-shoes'))
  let getTotal=renderShoeList(want,$('#td-get-shoes'))
  
  let giveCash=t.offer_cash||0
  let getCash=t.want_cash||0
  
  $('#td-give-cash').textContent=giveCash>0?'-$'+money(giveCash)+' cash':''
  $('#td-get-cash').textContent=getCash>0?'+$'+money(getCash)+' cash':''
  
  $('#td-give-total').textContent='$'+money(giveTotal+giveCash)
  $('#td-get-total').textContent='$'+money(getTotal+getCash)
  
  $('#td-accept').style.display='none'
  $('#td-counter').style.display='none'
  $('#trade-detail-modal').classList.remove('hidden')
}

window.closeTradeModal=()=>{
  $('#trade-detail-modal').classList.add('hidden')
  $('#td-accept').style.display=''
  $('#td-counter').style.display=''
  currentTrade=null
}

$('#td-accept').onclick=async()=>{
  if(!currentTrade)return
  let r=await fetch(`/api/trade/${currentTrade.id}/accept`,{method:'POST'})
  if(r.ok){
    let j=await r.json()
    if(j.ok){toast('Trade accepted!');closeTradeModal();fetchTrades();fetchBalance()}
    else toast(j.error||'Failed','error')
  }
}

$('#td-decline').onclick=async()=>{
  if(!currentTrade)return
  let r=await fetch(`/api/trade/${currentTrade.id}/decline`,{method:'POST'})
  if(r.ok){
    let j=await r.json()
    if(j.ok){toast('Trade declined');closeTradeModal();fetchTrades()}
    else toast(j.error||'Failed','error')
  }
}

$('#td-counter').onclick=()=>{
  if(!currentTrade)return
  let from=trades.incoming.find(t=>t.id===currentTrade.id)
  if(from)location.href='/user/'+from.from_username
}

$('#trade-detail-modal').onclick=(e)=>{if(e.target.id==='trade-detail-modal')closeTradeModal()}

const fetchUsers=async(q='')=>{
  let r=await fetch('/api/users'+(q?'?q='+encodeURIComponent(q):''))
  if(r.ok){users=await r.json();render()}
}

const fetchTrades=async()=>{
  let r=await fetch('/api/trades')
  if(r.ok){trades=await r.json();render()}
}

const fetchBalance=async()=>{
  let r=await fetch('/api/state')
  if(r.ok){let s=await r.json();$('#bal').textContent=money(s.balance)}
}

window.acceptTrade=async(id)=>{
  let r=await fetch(`/api/trade/${id}/accept`,{method:'POST'})
  if(r.ok){
    let j=await r.json()
    if(j.ok){toast('Trade accepted!');fetchTrades();fetchBalance()}
    else toast(j.error||'Failed','error')
  }
}

window.declineTrade=async(id)=>{
  let r=await fetch(`/api/trade/${id}/decline`,{method:'POST'})
  if(r.ok){
    let j=await r.json()
    if(j.ok){toast('Trade cancelled');fetchTrades()}
    else toast(j.error||'Failed','error')
  }
}

let searchTimeout
$('#search').oninput=(e)=>{
  clearTimeout(searchTimeout)
  searchTimeout=setTimeout(()=>fetchUsers(e.target.value),300)
}

fetchUsers()
fetchTrades()
fetchBalance()
setInterval(fetchTrades,10000)
