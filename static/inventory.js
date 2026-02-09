let state={market:[],hold:[],appraised:[],hist:{},balance:0,next_stock:0,next_price:0,server_time:0},sel=null,selType=null,serverOffset=0
const $=q=>document.querySelector(q),$$=q=>document.querySelectorAll(q)
const checkCourt=async()=>{let r=await fetch('/api/court/state');if(r.ok){let s=await r.json();if(s.active)window.location.href='/court'}}
checkCourt();setInterval(checkCourt,5000)
const el=(t,c)=>{let e=document.createElement(t);if(c)e.className=c;return e}
const money=v=>v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})
const pct=(p,b)=>((p-b)/b*100)
const rarClass=r=>({common:'rar-common',uncommon:'rar-uncommon',rare:'rar-rare',epic:'rar-epic',legendary:'rar-legendary',mythic:'rar-mythic',godly:'rar-godly',divine:'rar-divine',grails:'rar-grails',heavenly:'rar-heavenly'}[r]||'rar-common')

const updTimer=()=>{
  if(!state.next_stock)return
  let now=Math.floor(Date.now()/1000)+serverOffset
  let left=state.next_stock-now
  if(left<0)left=0
  let m=Math.floor(left/60),s=left%60
  let t=$('#stock-timer')
  t.textContent=m+':'+(s<10?'0':'')+s
  t.classList.toggle('urgent',left<30)
}
const updPriceTimer=()=>{
  if(!state.next_price)return
  let now=Math.floor(Date.now()/1000)+serverOffset
  let left=Math.max(0,state.next_price-now)
  let t=$('#price-timer')
  if(t)t.textContent=left+'s'
}
setInterval(updTimer,1000)
setInterval(updPriceTimer,200)

const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),2500)}

const invCard=(h,i)=>{
  let d=el('div','inv-card')
  d.dataset.id=h.id
  d.dataset.type='hold'
  d.style.animationDelay=i*0.05+'s'
  d.innerHTML=`<div class="inv-card-head"><div class="inv-card-rarity"></div><div class="inv-card-qty"></div><button class="fav-btn" title="Favorite (protected from Sell All)">★</button></div><div class="inv-card-name"></div><div class="inv-card-status"></div><div class="inv-card-price"></div><div class="inv-card-value"></div>`
  d.onclick=(e)=>{if(!e.target.classList.contains('fav-btn'))select(h.id,'hold')}
  d.querySelector('.fav-btn').onclick=(e)=>{e.stopPropagation();toggleFav(h.id,0)}
  return d
}

const appraisedCard=(a,i)=>{
  let d=el('div','inv-card appraised-card')
  d.dataset.id=a.appraisal_id
  d.dataset.type='appraised'
  d.style.animationDelay=i*0.05+'s'
  d.innerHTML=`<div class="inv-card-head"><div class="inv-card-rarity"></div><div class="appraisal-badge"></div><button class="fav-btn" title="Favorite (protected from Sell All)">★</button></div><div class="inv-card-name"></div><div class="appraisal-rating"></div><div class="inv-card-price"></div><div class="inv-card-value"></div>`
  d.onclick=(e)=>{if(!e.target.classList.contains('fav-btn'))select(a.appraisal_id,'appraised')}
  d.querySelector('.fav-btn').onclick=(e)=>{e.stopPropagation();toggleFav(a.id,a.appraisal_id)}
  return d
}

const toggleFav=async(shoeId,appraisalId)=>{
  let r=await fetch('/api/favorite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shoe_id:shoeId,appraisal_id:appraisalId})})
  if(r.ok){let j=await r.json();toast(j.favorited?'⭐ Favorited! Protected from Sell All':'Unfavorited');fetchState()}
}

const select=(id,type)=>{sel=parseInt(id);selType=type;updSidebar();$$('.inv-card').forEach(c=>{let isActive=(c.dataset.type===type&&parseInt(c.dataset.id)===sel);c.classList.toggle('active',isActive)})}
const getSelected=()=>{if(sel===null)return null;if(selType==='hold')return state.hold.find(x=>parseInt(x.id)===sel);if(selType==='appraised')return state.appraised.find(x=>parseInt(x.appraisal_id)===sel);return null}

const updSidebar=()=>{
  let item=getSelected()
  if(!item){$('#sidebar-empty').classList.remove('hidden');$('#sidebar-content').classList.add('hidden');return}
  $('#sidebar-empty').classList.add('hidden');$('#sidebar-content').classList.remove('hidden')
  $('#s-rarity').textContent=item.rarity.toUpperCase();$('#s-rarity').className='shoe-rarity-badge '+rarClass(item.rarity)
  $('#s-name').textContent=item.name
  let price=item.sell_price||item.base,base=item.base
  $('#s-price').textContent='$'+money(price)
  if(!item.in_market&&!item.appraised)$('#s-price').textContent+=' (off-market)'
  let p=base?pct(price,base):0;$('#s-pct-wrap').className='price-change '+(p>=0?'up':'down');$('#s-pct').textContent=(p>=0?'+':'')+p.toFixed(2)+'%'
  if(item.appraised){$('#s-owned').textContent=item.variant?'1 ('+item.variant.toUpperCase()+')':'1 (Appraised)';$('#s-total').textContent='$'+money(price);$('#s-qty').max=1;$('#s-qty').value=1;$('#s-qty').disabled=true}
  else{$('#s-owned').textContent=item.qty;$('#s-total').textContent='$'+money(price*item.qty);$('#s-qty').max=item.qty;$('#s-qty').value=Math.min(parseInt($('#s-qty').value)||1,item.qty);$('#s-qty').disabled=false}
  updSellPreview()
}

const updSellPreview=()=>{let item=getSelected();if(!item)return;let qty=item.appraised?1:(parseInt($('#s-qty').value)||1);let price=item.sell_price||item.base;$('#sell-preview').textContent='$'+money(price*qty)}

const act=async()=>{
  let item=getSelected();if(!item)return
  let body=item.appraised?{appraisal_id:item.appraisal_id,id:item.id,qty:1}:{id:item.id,qty:parseInt($('#s-qty').value)||1}
  let r=await fetch('/sell',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  if(r.ok){let j=await r.json();if(j.ok){toast('Sold for $'+money(j.total)+'!');sel=null;selType=null;fetchState()}else toast(j.error||'Failed','error')}else toast('Request failed','error')
}

const sellAll=async()=>{
  if(!confirm('Sell ALL shoes? (⭐ Favorited shoes are protected)'))return
  let r=await fetch('/sell-all',{method:'POST'})
  if(r.ok){let j=await r.json();if(j.ok){toast('Sold all for $'+money(j.total)+'!');sel=null;selType=null;fetchState()}else toast(j.error||'Failed','error')}else toast('Request failed','error')
}

const upd=()=>{
  $('#bal').textContent=money(state.balance)
  let inv=$('#inventory'),empty=$('#inv-empty'),cnt=$('#inv-count')
  let totalVal=0,totalBase=0,totalCount=0
  state.hold.forEach(h=>{let price=h.sell_price||h.base;totalVal+=price*h.qty;totalBase+=h.base*h.qty;totalCount+=h.qty})
  state.appraised.forEach(a=>{let price=a.sell_price||a.base;totalVal+=price;totalBase+=a.base;totalCount+=1})
  let pnl=totalVal-totalBase
  $('#inv-value').textContent='$'+money(totalVal);$('#inv-pnl').textContent=(pnl>=0?'+':'')+money(pnl);$('#inv-pnl').className='inv-stat-val '+(pnl>=0?'up':'down');$('#inv-worth').textContent='$'+money(state.balance+totalVal)
  if(totalCount>0){
    empty.classList.add('hidden');inv.classList.remove('hidden');cnt.textContent=totalCount+' shoe'+(totalCount>1?'s':'')+' owned';inv.innerHTML=''
    state.appraised.forEach((a,idx)=>{
      let d=appraisedCard(a,idx),rb=d.querySelector('.inv-card-rarity');rb.textContent=a.rarity.toUpperCase();rb.className='inv-card-rarity '+rarClass(a.rarity)
      let badge=d.querySelector('.appraisal-badge');badge.textContent=a.rating.toFixed(1);badge.className='appraisal-badge badge-'+a.rating_class
      d.querySelector('.inv-card-name').textContent=a.name
      if(a.variant){let vb=document.createElement('div');vb.className='variant-badge '+a.variant;vb.textContent=a.variant==='rainbow'?'🌈 RAINBOW':'✨ SHINY';d.querySelector('.inv-card-name').before(vb)}
      let rat=d.querySelector('.appraisal-rating'),pctVal=((a.multiplier-1)*100).toFixed(0);rat.innerHTML='<span class="'+(a.multiplier>=1?'up':'down')+'">'+(a.multiplier>=1?'+':'')+pctVal+'% value</span>'
      d.querySelector('.inv-card-price').textContent='$'+money(a.sell_price)+' ea';d.querySelector('.inv-card-value').textContent='Value: $'+money(a.sell_price)
      d.classList.add('rating-'+a.rating_class);if(a.variant)d.classList.add('variant-'+a.variant);d.classList.toggle('active',selType==='appraised'&&sel===parseInt(a.appraisal_id))
      d.classList.toggle('favorited',a.favorited);d.querySelector('.fav-btn').classList.toggle('active',a.favorited);inv.append(d)
    })
    state.hold.forEach((h,idx)=>{
      let d=invCard(h,idx+state.appraised.length),price=h.sell_price||h.base,rb=d.querySelector('.inv-card-rarity');rb.textContent=h.rarity.toUpperCase();rb.className='inv-card-rarity '+rarClass(h.rarity)
      d.querySelector('.inv-card-qty').textContent='x'+h.qty;d.querySelector('.inv-card-name').textContent=h.name
      let st=d.querySelector('.inv-card-status');st.textContent=h.in_market?'In Market':'Off-Market (-5%)';st.className='inv-card-status'+(h.in_market?' in-market':' off-market')
      d.querySelector('.inv-card-price').textContent='$'+money(price)+' ea';d.querySelector('.inv-card-value').textContent='Value: $'+money(price*h.qty)
      d.classList.toggle('active',selType==='hold'&&sel===parseInt(h.id));d.classList.toggle('off-market',!h.in_market)
      d.classList.toggle('favorited',h.favorited);d.querySelector('.fav-btn').classList.toggle('active',h.favorited);inv.append(d)
    })
  }else{empty.classList.remove('hidden');inv.classList.add('hidden');inv.innerHTML='';cnt.textContent='0 shoes owned'}
  if(sel!==null)updSidebar()
}

let lastHash=''
const stateHash=(s)=>JSON.stringify([s.balance,s.hold.map(h=>[h.id,h.qty,h.sell_price,h.favorited]),s.appraised.map(a=>[a.appraisal_id,a.rating,a.sell_price,a.favorited])])
const fetchState=async()=>{let r=await fetch('/api/state');if(r.ok){let ns=await r.json();serverOffset=ns.server_time-Math.floor(Date.now()/1000);let h=stateHash(ns);let changed=h!==lastHash;state=ns;if(changed){lastHash=h;upd()}updTimer()}}
setInterval(fetchState,3000)

const updBadge=async()=>{let r=await fetch('/api/trade-count');if(r.ok){let j=await r.json(),b=$('#trade-badge');if(b){if(j.count>0){b.textContent=j.count;b.classList.remove('hidden')}else{b.classList.add('hidden')}}}}

$('#btn-sell').onclick=act
$('#btn-details').onclick=()=>{let item=getSelected();if(item)location.href='/shoe/'+item.id}
$('#qty-dec').onclick=()=>{let q=$('#s-qty');q.value=Math.max(1,parseInt(q.value)-1);updSellPreview()}
$('#qty-inc').onclick=()=>{let q=$('#s-qty');q.value=Math.min(parseInt(q.max)||99,parseInt(q.value)+1);updSellPreview()}
$('#qty-max').onclick=()=>{let q=$('#s-qty');q.value=q.max||1;updSellPreview()}
$('#s-qty').oninput=updSellPreview
$('#sell-all').onclick=sellAll

const fetchNotifs=async()=>{let r=await fetch('/api/notifications');if(r.ok){let n=await r.json();n.forEach(x=>toast(x.message,'info'))}}
const fetchAnn=async()=>{let r=await fetch('/api/announcements');if(r.ok){let a=await r.json(),bar=document.getElementById('announcement-bar');if(bar){if(a.length){bar.innerHTML=a.map(x=>`<div class="announcement"><span class="ann-icon">📢</span><span class="ann-text">${x.message}</span></div>`).join('');bar.classList.add('show');document.body.classList.add('has-announcement')}else{bar.classList.remove('show');document.body.classList.remove('has-announcement')}}}}
const checkHanging=async()=>{let r=await fetch('/api/hanging');if(r.ok){let h=await r.json();if(h.active&&!location.pathname.includes('/hanging')){location.href='/hanging/'+h.victim}}}

fetchState()
updBadge()
fetchNotifs()
fetchAnn()
checkHanging()
setInterval(updBadge,10000)
setInterval(fetchNotifs,10000)
setInterval(fetchAnn,5000)
setInterval(checkHanging,3000)