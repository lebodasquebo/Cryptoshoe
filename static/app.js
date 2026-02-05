let state={market:[],hold:[],hist:{},balance:0,next_stock:0,next_price:0,server_time:0},sel=null,serverOffset=0
const $=q=>document.querySelector(q),$$=q=>document.querySelectorAll(q)
const checkCourt=async()=>{if(window.IS_ADMIN)return;let r=await fetch('/api/court/state');if(r.ok){let s=await r.json();if(s.active)window.location.href='/court'}}
checkCourt();setInterval(checkCourt,5000)
const el=(t,c)=>{let e=document.createElement(t);if(c)e.className=c;return e}
const money=v=>v.toFixed(2)
const pct=(p,b)=>((p-b)/b*100)
const rarClass=r=>({common:'rar-common',uncommon:'rar-uncommon',rare:'rar-rare',epic:'rar-epic',legendary:'rar-legendary',mythic:'rar-mythic',secret:'rar-secret',dexies:'rar-dexies',lebos:'rar-lebos'}[r]||'rar-common')

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

const updPriceTimers=()=>{
  if(!state.next_price)return
  let now=Math.floor(Date.now()/1000)+serverOffset
  let left=Math.max(0,state.next_price-now)
  $$('.card-price-timer').forEach(t=>t.textContent=left+'s')
}
setInterval(updTimer,1000)
setInterval(updPriceTimers,200)

const draw=(c,hist)=>{
  let w=c.width,h=c.height,ctx=c.getContext('2d')
  ctx.clearRect(0,0,w,h)
  if(!hist||hist.length<2)return
  let a=hist.map(x=>typeof x==='object'?x.price:x)
  let min=Math.min(...a),max=Math.max(...a)
  if(min==max){min*=.95;max*=1.05}
  let trend=a[a.length-1]>=a[0]
  let color=trend?'#00ff88':'#ff4466'
  let colorFade=trend?'rgba(0,255,136,':'rgba(255,68,102,'
  ctx.strokeStyle='rgba(255,255,255,0.05)'
  ctx.lineWidth=1
  for(let i=1;i<4;i++){let y=h*i/4;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke()}
  let grad=ctx.createLinearGradient(0,0,0,h)
  grad.addColorStop(0,colorFade+'0.4)')
  grad.addColorStop(1,colorFade+'0)')
  ctx.beginPath()
  ctx.moveTo(0,h)
  a.forEach((v,i)=>{let x=i*(w/(a.length-1)),y=h-((v-min)/(max-min))*h;ctx.lineTo(x,y)})
  ctx.lineTo(w,h)
  ctx.closePath()
  ctx.fillStyle=grad
  ctx.fill()
  ctx.beginPath()
  a.forEach((v,i)=>{let x=i*(w/(a.length-1)),y=h-((v-min)/(max-min))*h;i?ctx.lineTo(x,y):ctx.moveTo(x,y)})
  ctx.strokeStyle=color
  ctx.lineWidth=2
  ctx.lineCap='round'
  ctx.lineJoin='round'
  ctx.stroke()
  let lastY=h-((a[a.length-1]-min)/(max-min))*h
  ctx.beginPath();ctx.arc(w,lastY,3,0,Math.PI*2);ctx.fillStyle=color;ctx.fill()
  ctx.beginPath();ctx.arc(w,lastY,5,0,Math.PI*2);ctx.strokeStyle=color;ctx.lineWidth=1;ctx.stroke()
}

const card=(m,i)=>{
  let d=el('div','card')
  d.dataset.id=m.id
  d.style.animationDelay=`${i*0.05}s`
  d.innerHTML=`<div class="card-head"><div class="card-name"></div><div class="card-rarity"></div></div><div class="card-price-row"><div class="card-price"></div><div class="card-price-cd">⏱ <span class="card-price-timer">10s</span></div></div><div class="card-meta"><span class="card-stock"></span><span class="card-pct"></span></div><canvas class="card-chart" width="220" height="40"></canvas><div class="card-news"></div>`
  d.onclick=()=>select(m.id)
  return d
}

const holdCard=(m,i)=>{
  let d=el('div','card hold-card')
  d.dataset.id=m.id
  d.style.animationDelay=`${i*0.05}s`
  d.innerHTML=`<div class="card-head"><div class="card-name"></div><div class="card-rarity"></div></div><div class="card-qty"></div>`
  return d
}

const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),2500)}

const act=async(type,id,qty)=>{
  let r=await fetch('/'+type,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,qty:parseInt(qty)})})
  if(r.ok){let j=await r.json();if(j.ok){toast(type==='buy'?`Bought ${qty} shoe(s)!`:`Sold ${qty} shoe(s)!`);fetchState()}else toast(j.error||'Failed','error')}else toast('Request failed','error')
}

const select=id=>{sel=parseInt(id);updSidebar();$$('.card').forEach(c=>c.classList.toggle('active',parseInt(c.dataset.id)===sel))}

const updSidebar=()=>{
  if(sel===null)return
  let i=state.market.find(x=>parseInt(x.id)===parseInt(sel))
  if(!i){$('#sidebar-empty').classList.remove('hidden');$('#sidebar-content').classList.add('hidden');return}
  $('#sidebar-empty').classList.add('hidden');$('#sidebar-content').classList.remove('hidden')
  $('#s-rarity').textContent=i.rarity.toUpperCase();$('#s-rarity').className='shoe-rarity-badge '+rarClass(i.rarity)
  $('#s-name').textContent=i.name;$('#s-price').textContent='$'+money(i.price)
  let p=pct(i.price,i.base);$('#s-pct-wrap').className='price-change '+(p>=0?'up':'down');$('#s-pct').textContent=(p>=0?'+':'')+p.toFixed(2)+'%'
  $('#s-base').textContent='$'+money(i.base);$('#s-stock').textContent=i.stock
  let nw=$('#s-news-wrap'),nt=$('#s-news')
  if(i.news){nw.classList.remove('no-news');nt.classList.add('active');nt.textContent=i.news}else{nw.classList.add('no-news');nt.classList.remove('active');nt.textContent='No current news'}
  $('#s-qty').max=i.stock;$('#s-qty').value=Math.min(parseInt($('#s-qty').value)||1,i.stock||1)
}

const upd=()=>{
  $('#bal').textContent=money(state.balance)
  let m=$('#market')
  state.market.forEach((i,idx)=>{
    let d=m.querySelector(`[data-id='${i.id}']`)||card(i,idx)
    d.querySelector('.card-name').textContent=i.name
    let rb=d.querySelector('.card-rarity');rb.textContent=i.rarity.toUpperCase();rb.className='card-rarity '+rarClass(i.rarity)
    d.querySelector('.card-price').textContent='$'+money(i.price);d.querySelector('.card-stock').textContent='Stock: '+i.stock
    let p=pct(i.price,i.base),pc=d.querySelector('.card-pct');pc.textContent=(p>=0?'+':'')+p.toFixed(2)+'%';pc.className='card-pct '+(p>=0?'up':'down')
    if(state.hist[i.id])draw(d.querySelector('canvas'),state.hist[i.id])
    let nw=d.querySelector('.card-news');nw.textContent=i.news?'📰 '+i.news:'No news';nw.className='card-news'+(i.news?' has-news':'')
    d.classList.toggle('active',parseInt(i.id)===sel);if(!m.contains(d))m.append(d)
  })
  let ids=state.market.map(x=>parseInt(x.id));[...m.children].forEach(c=>{if(!ids.includes(parseInt(c.dataset.id)))c.remove()})
  let h=$('#hold'),he=$('#hold-empty'),hc=$('#hold-count');h.innerHTML=''
  if(state.hold.length){he.classList.add('hidden');hc.textContent=state.hold.length+' shoe'+(state.hold.length>1?'s':'')+' owned'
    state.hold.forEach((i,idx)=>{let d=holdCard(i,idx);d.querySelector('.card-name').textContent=i.name;let rb=d.querySelector('.card-rarity');rb.textContent=i.rarity.toUpperCase();rb.className='card-rarity '+rarClass(i.rarity);d.querySelector('.card-qty').textContent='×'+i.qty;h.append(d)})
  }else{he.classList.remove('hidden');hc.textContent='0 shoes owned'}
  if(sel!==null)updSidebar();updPriceTimers()
}

const fetchState=async()=>{let r=await fetch('/api/state');if(r.ok){state=await r.json();serverOffset=state.server_time-Math.floor(Date.now()/1000);upd();updTimer()}}
setInterval(fetchState,3000)

$('#btn-buy').onclick=()=>{if(sel!==null)act('buy',sel,$('#s-qty').value)}
$('#btn-sell').onclick=()=>{if(sel!==null)act('sell',sel,$('#s-qty').value)}
$('#btn-details').onclick=()=>{if(sel!==null)location.href='/shoe/'+sel}
$('#qty-dec').onclick=()=>{let q=$('#s-qty');q.value=Math.max(1,parseInt(q.value)-1)}
$('#qty-inc').onclick=()=>{let q=$('#s-qty');q.value=Math.min(parseInt(q.max)||99,parseInt(q.value)+1)}
$('#qty-max').onclick=()=>{let q=$('#s-qty');q.value=q.max||1}

const updBadge=async()=>{let r=await fetch('/api/trade-count');if(r.ok){let j=await r.json(),b=$('#trade-badge');if(j.count>0){b.textContent=j.count;b.classList.remove('hidden')}else{b.classList.add('hidden')}}}
const fetchNotifs=async()=>{let r=await fetch('/api/notifications');if(r.ok){let n=await r.json();n.forEach(x=>toast(x.message,'info'))}}
const fetchAnn=async()=>{let r=await fetch('/api/announcements');if(r.ok){let a=await r.json(),bar=$('#announcement-bar');if(a.length){bar.innerHTML=a.map(x=>`<div class="announcement"><span class="ann-icon">📢</span><span class="ann-text">${x.message}</span></div>`).join('');bar.classList.add('show');document.body.classList.add('has-announcement')}else{bar.classList.remove('show');document.body.classList.remove('has-announcement')}}}

fetchState()
updBadge()
fetchNotifs()
fetchAnn()
setInterval(updBadge,10000)
setInterval(fetchNotifs,10000)
setInterval(fetchAnn,5000)
