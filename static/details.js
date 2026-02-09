let data=null,span=86400,balance=0,nextPrice=0,serverOffset=0
const $=q=>document.querySelector(q),$$=q=>document.querySelectorAll(q)
const checkCourt=async()=>{let r=await fetch('/api/court/state');if(r.ok){let s=await r.json();if(s.active)window.location.href='/court'}}
checkCourt();setInterval(checkCourt,5000)
const money=v=>v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})
const pct=(p,b)=>((p-b)/b*100)
const rarClass=r=>({common:'rar-common',uncommon:'rar-uncommon',rare:'rar-rare',epic:'rar-epic',legendary:'rar-legendary',mythic:'rar-mythic',godly:'rar-godly',divine:'rar-divine',grails:'rar-grails',heavenly:'rar-heavenly'}[r]||'rar-common')

const toast=(msg,type='success')=>{
  let t=document.createElement('div')
  t.className='toast show '+type
  t.textContent=msg
  t.style.cssText='position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:14px 24px;background:#1a1a26;border:1px solid '+(type==='success'?'#00ff88':'#ff4466')+';border-radius:12px;color:'+(type==='success'?'#00ff88':'#ff4466')+';z-index:1000'
  document.body.append(t)
  setTimeout(()=>t.remove(),2500)
}

const updPriceTimer=()=>{
  if(!nextPrice)return
  let now=Math.floor(Date.now()/1000)+serverOffset
  let left=Math.max(0,nextPrice-now)
  let t=$('#price-timer')
  if(t)t.textContent=left+'s'
}
setInterval(updPriceTimer,200)

const draw=(c,arr)=>{
  let rect=c.getBoundingClientRect()
  c.width=rect.width*2
  c.height=rect.height*2
  let ctx=c.getContext('2d')
  ctx.scale(2,2)
  let w=rect.width,h=rect.height
  ctx.clearRect(0,0,w,h)
  if(!arr||arr.length<2)return
  let min=Math.min(...arr),max=Math.max(...arr)
  if(min==max){min*=0.95;max*=1.05}
  let trend=arr[arr.length-1]>=arr[0]
  let color=trend?'#00ff88':'#ff4466'
  let colorFade=trend?'rgba(0,255,136,':'rgba(255,68,102,'
  ctx.strokeStyle='rgba(255,255,255,0.05)'
  ctx.lineWidth=1
  for(let i=1;i<4;i++){
    let y=h*i/4
    ctx.beginPath()
    ctx.moveTo(0,y)
    ctx.lineTo(w,y)
    ctx.stroke()
  }
  let grad=ctx.createLinearGradient(0,0,0,h)
  grad.addColorStop(0,colorFade+'0.3)')
  grad.addColorStop(1,colorFade+'0)')
  ctx.beginPath()
  ctx.moveTo(0,h)
  arr.forEach((v,i)=>{let x=i*(w/(arr.length-1)),y=h-((v-min)/(max-min))*h;ctx.lineTo(x,y)})
  ctx.lineTo(w,h)
  ctx.closePath()
  ctx.fillStyle=grad
  ctx.fill()
  ctx.beginPath()
  arr.forEach((v,i)=>{let x=i*(w/(arr.length-1)),y=h-((v-min)/(max-min))*h;i?ctx.lineTo(x,y):ctx.moveTo(x,y)})
  ctx.strokeStyle=color
  ctx.lineWidth=2
  ctx.lineCap='round'
  ctx.lineJoin='round'
  ctx.stroke()
  ctx.setLineDash([5,5])
  ctx.strokeStyle='rgba(0,240,255,0.3)'
  ctx.lineWidth=1
  let baseY=h-((data.base-min)/(max-min))*h
  ctx.beginPath()
  ctx.moveTo(0,baseY)
  ctx.lineTo(w,baseY)
  ctx.stroke()
  $('#chart-high').textContent='$'+money(max)
  $('#chart-low').textContent='$'+money(min)
}

const updBuyTotal=()=>{
  if(!data)return
  let qty=parseInt($('#buy-qty').value)||1
  $('#buy-total').textContent='$'+money(data.price*qty)
}

const updSellTotal=()=>{
  if(!data)return
  let qty=parseInt($('#sell-qty').value)||1
  let price=data.in_market?data.price:data.price*0.9
  $('#sell-total').textContent='$'+money(price*qty)
}

const updTrade=()=>{
  if(!data)return
  let buyPanel=$('#buy-panel'),sellPanel=$('#sell-panel')
  $('#trade-owned').innerHTML=data.owned>0?`<span class="owned-badge">You own: ${data.owned}</span>`:''
  if(data.in_market&&data.stock>0){
    buyPanel.classList.remove('disabled-panel')
    $('#btn-buy').disabled=false
    $('#buy-qty').max=data.stock
    $('#buy-qty').value=Math.min(parseInt($('#buy-qty').value)||1,data.stock)
    $('#buy-status').textContent=''
  }else if(data.in_market){
    buyPanel.classList.add('disabled-panel')
    $('#btn-buy').disabled=true
    $('#buy-status').textContent='Out of stock'
  }else{
    buyPanel.classList.add('disabled-panel')
    $('#btn-buy').disabled=true
    $('#buy-status').textContent='Not in market'
  }
  if(data.owned>0){
    sellPanel.classList.remove('hidden')
    sellPanel.classList.remove('disabled-panel')
    $('#btn-sell').disabled=false
    $('#sell-qty').max=data.owned
    $('#sell-qty').value=Math.min(parseInt($('#sell-qty').value)||1,data.owned)
    $('#sell-status').textContent=data.in_market?'':'(-5% off-market)'
  }else{
    sellPanel.classList.add('hidden')
  }
  updBuyTotal()
  updSellTotal()
}

const render=()=>{
  if(!data)return
  $('#d-rarity').textContent=data.rarity.toUpperCase()
  $('#d-rarity').className='hero-badge '+rarClass(data.rarity)
  $('#d-name').textContent=data.name
  $('#d-price').textContent='$'+money(data.price)
  let p=pct(data.price,data.base)
  let pw=$('#d-pct-wrap')
  pw.className='hero-change '+(p>=0?'up':'down')
  $('#d-pct').textContent=(p>=0?'+':'')+p.toFixed(2)+'%'
  $('#d-base').textContent=money(data.base)
  $('#d-rarity2').textContent=data.rarity
  $('#d-base2').textContent='$'+money(data.base)
  $('#d-stock').textContent=data.stock>0?data.stock:'Out of stock'
  let nc=$('#d-news'),ni=$('#d-impact')
  if(data.news){
    nc.innerHTML='<div class="active-news">'+data.news+'</div>'
    ni.textContent='⚡ This news is actively affecting the price'
    ni.classList.add('show')
  }else{
    nc.innerHTML='<div class="no-news">No news affecting this shoe</div>'
    ni.classList.remove('show')
  }
  let now=Math.floor(Date.now()/1000)
  let arr=data.history.filter(x=>x.ts>=now-span).map(x=>x.price)
  draw($('#d-chart'),arr)
  if(arr.length){
    let hi=Math.max(...arr),lo=Math.min(...arr),avg=arr.reduce((a,b)=>a+b,0)/arr.length
    let vol=((hi-lo)/avg*100)
    $('#stat-high').textContent='$'+money(hi)
    $('#stat-low').textContent='$'+money(lo)
    $('#stat-avg').textContent='$'+money(avg)
    $('#stat-vol').textContent=vol.toFixed(1)+'%'
  }
  updTrade()
}

const buy=async()=>{
  if(!data||!data.in_market||data.stock<1)return
  let qty=parseInt($('#buy-qty').value)||1
  let r=await fetch('/buy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:data.id,qty})})
  if(r.ok){
    let j=await r.json()
    if(j.ok){toast(`Bought ${qty} shoe(s)!`);fetchData()}
    else toast(j.error||'Failed','error')
  }else toast('Request failed','error')
}

const sell=async()=>{
  if(!data||data.owned<1)return
  let qty=parseInt($('#sell-qty').value)||1
  let r=await fetch('/sell',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:data.id,qty})})
  if(r.ok){
    let j=await r.json()
    if(j.ok){toast(`Sold ${qty} shoe(s) for $${money(j.total)}!`);fetchData()}
    else toast(j.error||'Failed','error')
  }else toast('Request failed','error')
}

const fetchData=async()=>{
  let r=await fetch('/api/shoe/'+window.SHOE_ID);if(r.ok){data=await r.json();render()}
  let s=await fetch('/api/state');if(s.ok){
    let st=await s.json()
    balance=st.balance
    nextPrice=st.next_price
    serverOffset=st.server_time-Math.floor(Date.now()/1000)
    $('#bal').textContent=money(st.balance)
  }
}

$$('.chart-spans button').forEach(b=>{
  b.onclick=()=>{
    $$('.chart-spans button').forEach(x=>x.classList.remove('active'))
    b.classList.add('active')
    span=parseInt(b.dataset.span)
    render()
  }
})

$('#buy-dec').onclick=()=>{let q=$('#buy-qty');q.value=Math.max(1,parseInt(q.value)-1);updBuyTotal()}
$('#buy-inc').onclick=()=>{let q=$('#buy-qty');q.value=Math.min(parseInt(q.max)||99,parseInt(q.value)+1);updBuyTotal()}
$('#buy-max').onclick=()=>{let q=$('#buy-qty');q.value=q.max||1;updBuyTotal()}
$('#buy-qty').oninput=updBuyTotal
$('#btn-buy').onclick=buy

$('#sell-dec').onclick=()=>{let q=$('#sell-qty');q.value=Math.max(1,parseInt(q.value)-1);updSellTotal()}
$('#sell-inc').onclick=()=>{let q=$('#sell-qty');q.value=Math.min(parseInt(q.max)||99,parseInt(q.value)+1);updSellTotal()}
$('#sell-max').onclick=()=>{let q=$('#sell-qty');q.value=q.max||1;updSellTotal()}
$('#sell-qty').oninput=updSellTotal
$('#btn-sell').onclick=sell

window.addEventListener('resize',()=>data&&render())
setInterval(fetchData,2000)
fetchData()

const updBadge=async()=>{
  let r=await fetch('/api/trade-count')
  if(r.ok){
    let j=await r.json()
    let b=document.querySelector('#trade-badge')
    if(b){
      if(j.count>0){b.textContent=j.count;b.classList.remove('hidden')}
      else{b.classList.add('hidden')}
    }
  }
}
const fetchNotifs=async()=>{let r=await fetch('/api/notifications');if(r.ok){let n=await r.json();n.forEach(x=>toast(x.message,'info'))}}
const fetchAnn=async()=>{let r=await fetch('/api/announcements');if(r.ok){let a=await r.json(),bar=document.getElementById('announcement-bar');if(bar){if(a.length){bar.innerHTML=a.map(x=>`<div class="announcement"><span class="ann-icon">📢</span><span class="ann-text">${x.message}</span></div>`).join('');bar.classList.add('show');document.body.classList.add('has-announcement')}else{bar.classList.remove('show');document.body.classList.remove('has-announcement')}}}}
const checkHanging=async()=>{let r=await fetch('/api/hanging');if(r.ok){let h=await r.json();if(h.active&&!location.pathname.includes('/hanging')){location.href='/hanging/'+h.victim}}}
updBadge()
fetchNotifs()
fetchAnn()
checkHanging()
setInterval(updBadge,10000)
setInterval(fetchNotifs,10000)
setInterval(fetchAnn,5000)
setInterval(checkHanging,3000)
