let users=[],trades={incoming:[],outgoing:[]},currentTrade=null,totalUsers=0,currentOffset=0,hasMore=false,currentQuery=''
const $=q=>document.querySelector(q),$$=q=>document.querySelectorAll(q)
const checkCourt=async()=>{let r=await fetch('/api/court/state');if(r.ok){let s=await r.json();if(s.active)window.location.href='/court'}}
checkCourt();setInterval(checkCourt,5000)
const money=v=>v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})
const rarClass=r=>({common:'rar-common',uncommon:'rar-uncommon',rare:'rar-rare',epic:'rar-epic',legendary:'rar-legendary',mythic:'rar-mythic',godly:'rar-godly',divine:'rar-divine',grails:'rar-grails',heavenly:'rar-heavenly'}[r]||'rar-common')
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]))
const avatarFor=u=>u.profile_picture&&u.profile_picture.trim()?u.profile_picture:`/avatar/${encodeURIComponent(u.username)}.svg`

const toast=(msg,type='success')=>{
  let t=$('#toast')
  t.textContent=msg
  t.className='toast show '+type
  setTimeout(()=>t.classList.remove('show'),5000)
}

const userCard=(u)=>`<div class="user-card${u.is_me?' is-me':''}${u.online?' online':''}">
  <div class="user-avatar-wrap"><img class="user-avatar" src="${esc(avatarFor(u))}" alt="${esc(u.username)} avatar" loading="lazy" decoding="async" onerror="this.onerror=null;this.src='/avatar/${encodeURIComponent(u.username)}.svg'" /></div>
  <div class="user-status ${u.online?'online':'offline'}">${u.online?'🟢 Online':'⚫ Offline'}</div>
  <div class="user-name">${esc(u.username)}${u.is_me?' (you)':''}</div>
  <div class="user-stats">
    <div class="user-stat"><span class="user-stat-val">$${money(u.balance)}</span><span>Balance</span></div>
    <div class="user-stat"><span class="user-stat-val">${u.shoes}</span><span>Shoes</span></div>
  </div>
  <div class="user-actions">
    <a href="/user/${encodeURIComponent(u.username)}" class="user-btn profile-btn">👤 Profile</a>
    ${!u.is_me?`<a href="/user/${encodeURIComponent(u.username)}" class="user-btn trade-btn">🤝 Trade</a>`:''}
  </div>
</div>`

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
    return `<div class="trade-item">
      <div class="trade-user">From: <strong>${t.from_username}</strong></div>
      <div class="trade-details">
        <div>📥 You get: <span class="val-green">$${money(offerVal)}</span></div>
        <div>📤 You give: <span class="val-red">$${money(wantVal)}</span></div>
      </div>
      <div class="trade-item-actions">
        <button class="trade-btn-sm view-btn" onclick="viewTrade(${t.id})">👁 View Details</button>
        <button class="trade-btn-sm accept-btn" onclick="acceptTrade(${t.id})">✓ Accept</button>
        <button class="trade-btn-sm decline-btn" onclick="declineTrade(${t.id})">✗ Decline</button>
      </div>
    </div>`
  }else{
    return `<div class="trade-item">
      <div class="trade-user">To: <strong>${t.to_username}</strong></div>
      <div class="trade-details">
        <div>📤 You offer: <span class="val-red">$${money(offerVal)}</span></div>
        <div>📥 You want: <span class="val-green">$${money(wantVal)}</span></div>
      </div>
      <div class="trade-item-actions">
        <button class="trade-btn-sm view-btn" onclick="viewOutgoing(${t.id})">👁 View Details</button>
        <button class="trade-btn-sm decline-btn" onclick="declineTrade(${t.id})">✗ Cancel</button>
      </div>
    </div>`
  }
}

const render=()=>{
  let grid=$('#users-grid'),empty=$('#users-empty')
  if(users.length){
    grid.innerHTML=users.map(u=>userCard(u)).join('')
    let btns='<div class="load-more-wrap">'
    if(currentOffset>0)btns+=`<button class="load-more-btn" onclick="showLess()">Show Less</button>`
    if(hasMore)btns+=`<button class="load-more-btn" onclick="loadMore()">Load More (${users.length}/${totalUsers})</button>`
    else if(totalUsers>0&&currentOffset===0)btns+=`<span class="users-count">Showing all ${totalUsers} users</span>`
    btns+='</div>'
    grid.innerHTML+=btns
    empty.classList.add('hidden')
  }
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
    let vc=s.variant?' variant-'+s.variant:''
    let vb=s.variant?`<div class="variant-badge ${s.variant}">${s.variant==='rainbow'?'🌈 RAINBOW':'✨ SHINY'}</div>`:''
    let ratingInfo=s.appraised&&s.rating?` ⭐${s.rating.toFixed(1)}`:''
    return `<div class="td-shoe${vc}">
      <div>${vb}<span class="td-shoe-name">${s.name}</span><div class="td-shoe-info">${s.rarity}${ratingInfo} ${s.qty>1?'×'+s.qty:''}</div></div>
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

const fetchUsers=async(q='',append=false)=>{
  currentQuery=q
  if(!append)currentOffset=0
  let url='/api/users?offset='+currentOffset+'&limit=50'+(q?'&q='+encodeURIComponent(q):'')
  try{
    let r=await fetch(url)
    if(r.ok){
      let data=await r.json()
      console.log('Users data:', data)
      if(append){users=users.concat(data.users)}else{users=data.users}
      totalUsers=data.total
      hasMore=data.has_more
      render()
    }else{console.error('Users fetch failed:', r.status)}
  }catch(e){console.error('Users fetch error:', e)}
}

window.loadMore=()=>{
  currentOffset+=50
  fetchUsers(currentQuery,true)
}

window.showLess=()=>{
  currentOffset=0
  fetchUsers(currentQuery)
}

const fetchSuggestions=async(q)=>{
  if(q.length<2){$('#suggestions').innerHTML='';return}
  let r=await fetch('/api/users/suggest?q='+encodeURIComponent(q))
  if(r.ok){
    let s=await r.json()
    let sg=$('#suggestions')
    if(s.length){
      sg.innerHTML=s.map(u=>`<div class="suggestion" onclick="selectSuggestion('${u}')">${u}</div>`).join('')
    }else{sg.innerHTML=''}
  }
}

window.selectSuggestion=(u)=>{
  $('#search').value=u
  $('#suggestions').innerHTML=''
  fetchUsers(u)
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
  searchTimeout=setTimeout(()=>{fetchUsers(e.target.value);fetchSuggestions(e.target.value)},300)
}
$('#search').onblur=()=>setTimeout(()=>$('#suggestions').innerHTML='',200)

const fetchNotifs=async()=>{let r=await fetch('/api/notifications');if(r.ok){let n=await r.json();n.forEach((x,i)=>setTimeout(()=>toast(x.message,'info'),i*5500))}}
const fetchAnn=async()=>{let r=await fetch('/api/announcements');if(r.ok){let a=await r.json(),bar=document.getElementById('announcement-bar');if(bar){if(a.length){bar.innerHTML=a.map(x=>`<div class="announcement"><span class="ann-icon">📢</span><span class="ann-text">${x.message}</span></div>`).join('');bar.classList.add('show');document.body.classList.add('has-announcement')}else{bar.classList.remove('show');document.body.classList.remove('has-announcement')}}}}
const checkHanging=async()=>{let r=await fetch('/api/hanging');if(r.ok){let h=await r.json();if(h.active&&!location.pathname.includes('/hanging')){location.href='/hanging/'+h.victim}}}

fetchUsers()
fetchTrades()
fetchBalance()
fetchNotifs()
fetchAnn()
checkHanging()
setInterval(()=>{
  let limit=currentOffset+50
  let url='/api/users?offset=0&limit='+limit+(currentQuery?'&q='+encodeURIComponent(currentQuery):'')
  fetch(url).then(r=>r.ok?r.json():null).then(data=>{
    if(data){users=data.users;totalUsers=data.total;hasMore=data.has_more;render()}
  })
},10000)
setInterval(fetchTrades,10000)
setInterval(fetchNotifs,10000)
setInterval(fetchAnn,5000)
setInterval(checkHanging,3000)
