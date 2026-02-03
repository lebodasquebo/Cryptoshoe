let state={market:[],hold:[],appraised:[],hist:{},balance:0,next_stock:0,server_time:0},serverOffset=0
const $=q=>document.querySelector(q),$$=q=>document.querySelectorAll(q)
const el=(t,c)=>{let e=document.createElement(t);if(c)e.className=c;return e}
const money=v=>v.toFixed(2)
const rarClass=r=>({common:'rar-common',uncommon:'rar-uncommon',rare:'rar-rare',epic:'rar-epic',legendary:'rar-legendary',mythic:'rar-mythic',secret:'rar-secret',dexies:'rar-dexies',lebos:'rar-lebos'}[r]||'rar-common')

const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),2500)}

const card=(h,i)=>{
  let d=el('div','appraise-card')
  d.dataset.id=h.id
  d.style.animationDelay=`${i*0.05}s`
  d.innerHTML=`<div class="appraise-card-head"><div class="appraise-card-name"></div><div class="appraise-card-rarity"></div></div><div class="appraise-card-qty"></div><div class="appraise-card-price"></div><div class="appraise-card-cost"></div><div class="appraise-qty-select"><label>Appraise:</label><div class="appraise-qty-wrap"><button class="qty-btn qty-dec">−</button><input type="number" class="appraise-qty" min="1" value="1"><button class="qty-btn qty-inc">+</button></div><button class="qty-max-btn">MAX</button></div><button class="appraise-btn">🔍 APPRAISE</button>`
  let input=d.querySelector('.appraise-qty')
  d.querySelector('.qty-dec').onclick=(e)=>{e.stopPropagation();input.value=Math.max(1,parseInt(input.value)-1);updCost(d,h)}
  d.querySelector('.qty-inc').onclick=(e)=>{e.stopPropagation();input.value=Math.min(h.qty,parseInt(input.value)+1);updCost(d,h)}
  d.querySelector('.qty-max-btn').onclick=(e)=>{e.stopPropagation();input.value=h.qty;updCost(d,h)}
  input.oninput=()=>updCost(d,h)
  d.querySelector('.appraise-btn').onclick=(e)=>{e.stopPropagation();appraise(h.id,parseInt(input.value)||1)}
  return d
}

const updCost=(d,h)=>{let qty=parseInt(d.querySelector('.appraise-qty').value)||1;qty=Math.min(qty,h.qty);let price=h.sell_price||h.base;let cost=price*0.05*qty;d.querySelector('.appraise-card-cost').textContent=`Cost: $${money(cost)} (${qty}×$${money(price*0.05)})`}

const appraise=async(id,qty)=>{
  let r=await fetch('/api/appraise',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,qty})})
  if(r.ok){let j=await r.json();if(j.ok){showResults(j);fetchState()}else toast(j.error||'Failed','error')}else toast('Request failed','error')
}

const showResults=(res)=>{
  let m=$('#appraise-modal'),content=$('#modal-results')
  content.innerHTML=''
  if(res.qty===1){
    let r=res.results[0]
    content.innerHTML=`<div class="single-result"><div class="modal-rating ${r.rating_class}">${r.rating.toFixed(1)}</div><div class="modal-comment">${r.comment}</div><div class="modal-mult ${r.multiplier>=1?'up':'down'}">${r.multiplier>=1?'+':''}${((r.multiplier-1)*100).toFixed(0)}% value</div></div>`
  }else{
    let html='<div class="multi-results"><div class="results-grid">'
    res.results.forEach((r,i)=>{html+=`<div class="result-item ${r.rating_class}"><div class="result-num">#${i+1}</div><div class="result-rating">${r.rating.toFixed(1)}</div><div class="result-mult ${r.multiplier>=1?'up':'down'}">${r.multiplier>=1?'+':''}${((r.multiplier-1)*100).toFixed(0)}%</div></div>`})
    html+=`</div><div class="best-result"><div class="best-label">BEST RESULT</div><div class="best-rating ${res.best.rating_class}">${res.best.rating.toFixed(1)}</div><div class="best-comment">${res.best.comment}</div></div></div>`
    content.innerHTML=html
  }
  m.classList.toggle('has-perfect',res.results.some(r=>r.perfect))
  m.classList.remove('hidden')
}

$('#modal-close').onclick=()=>$('#appraise-modal').classList.add('hidden')
$('#modal-btn').onclick=()=>$('#appraise-modal').classList.add('hidden')
$('#appraise-modal').onclick=(e)=>{if(e.target.id==='appraise-modal')$('#appraise-modal').classList.add('hidden')}

const upd=()=>{
  $('#bal').textContent=money(state.balance)
  let grid=$('#shoe-grid'),empty=$('#appraise-empty'),cnt=$('#shoe-count')
  if(state.hold.length){
    empty.classList.add('hidden');grid.classList.remove('hidden');cnt.textContent=state.hold.length+' shoe type'+(state.hold.length>1?'s':'')+' to appraise';grid.innerHTML=''
    state.hold.forEach((h,idx)=>{
      let d=card(h,idx),price=h.sell_price||h.base
      d.querySelector('.appraise-card-name').textContent=h.name
      let rb=d.querySelector('.appraise-card-rarity');rb.textContent=h.rarity.toUpperCase();rb.className='appraise-card-rarity '+rarClass(h.rarity)
      d.querySelector('.appraise-card-qty').textContent='You own: ×'+h.qty+' unappraised'
      d.querySelector('.appraise-card-price').textContent='Value: $'+money(price)+' ea'
      d.querySelector('.appraise-qty').max=h.qty;d.querySelector('.appraise-qty').value=1;updCost(d,h);grid.append(d)
    })
  }else{empty.classList.remove('hidden');grid.classList.add('hidden');grid.innerHTML='';cnt.textContent='0 shoes to appraise'}
}

const fetchState=async()=>{let r=await fetch('/api/state');if(r.ok){state=await r.json();serverOffset=state.server_time-Math.floor(Date.now()/1000);upd()}}
setInterval(fetchState,3000)
fetchState()
