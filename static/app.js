let state={market:[],limited:[],hold:[],hist:{},limited_hist:{},balance:0,next_stock:0,next_price:0,server_time:0},sel=null,selType='market',serverOffset=0
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
  d.dataset.type='market'
  d.style.animationDelay=`${i*0.05}s`
  d.innerHTML=`<div class="card-head"><div class="card-name"></div><div class="card-rarity"></div></div><div class="card-price-row"><div class="card-price"></div><div class="card-price-cd">⏱ <span class="card-price-timer">10s</span></div></div><div class="card-meta"><span class="card-stock"></span><span class="card-pct"></span></div><canvas class="card-chart" width="220" height="40"></canvas><div class="card-news"></div><div class="card-news card-news2"></div>`
  d.onclick=()=>select(m.id,'market')
  return d
}

const limitedCard=(m,i)=>{
  let d=el('div','card limited-card')
  d.dataset.id=m.id
  d.dataset.type='limited'
  d.style.animationDelay=`${i*0.05}s`
  d.innerHTML=`<div class="card-head"><div class="card-name"></div><div class="card-rarity"></div></div><div class="limited-badge">⭐ LIMITED EDITION</div><div class="card-price-row"><div class="card-price"></div><div class="card-price-cd">⏱ <span class="card-price-timer">10s</span></div></div><div class="card-meta"><span class="card-stock"></span><span class="card-pct"></span></div><canvas class="card-chart" width="220" height="40"></canvas>`
  d.onclick=()=>select(m.id,'limited')
  return d
}

const holdCard=(m,i)=>{
  let d=el('div','card hold-card')
  d.dataset.id=m.id
  d.style.animationDelay=`${i*0.05}s`
  d.innerHTML=`<div class="card-head"><div class="card-name"></div><div class="card-rarity"></div></div><div class="card-qty"></div>`
  return d
}

const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),5000)}

const act=async(type,id,qty)=>{
  let r=await fetch('/'+type,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,qty:parseInt(qty)})})
  if(r.ok){let j=await r.json();if(j.ok){toast(type==='buy'?`Bought ${qty} shoe(s)!`:`Sold ${qty} shoe(s)!`);fetchState()}else toast(j.error||'Failed','error')}else toast('Request failed','error')
}

const actLimited=async(type,id,qty)=>{
  let r=await fetch('/'+type,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,qty:parseInt(qty)})})
  if(r.ok){let j=await r.json();if(j.ok){toast(`Bought ${qty} limited shoe(s)!`);fetchState()}else toast(j.error||'Failed','error')}else toast('Request failed','error')
}

const select=(id,type='market')=>{sel=parseInt(id);selType=type;updSidebar();$$('.card').forEach(c=>c.classList.toggle('active',parseInt(c.dataset.id)===sel&&c.dataset.type===selType))}

const updSidebar=()=>{
  if(sel===null)return
  let i=selType==='limited'?state.limited.find(x=>parseInt(x.id)===parseInt(sel)):state.market.find(x=>parseInt(x.id)===parseInt(sel))
  if(!i){$('#sidebar-empty').classList.remove('hidden');$('#sidebar-content').classList.add('hidden');return}
  $('#sidebar-empty').classList.add('hidden');$('#sidebar-content').classList.remove('hidden')
  $('#s-rarity').textContent=i.rarity.toUpperCase();$('#s-rarity').className='shoe-rarity-badge '+rarClass(i.rarity)
  $('#s-name').textContent=i.name;$('#s-price').textContent='$'+money(i.price)
  let p=pct(i.price,i.base);$('#s-pct-wrap').className='price-change '+(p>=0?'up':'down');$('#s-pct').textContent=(p>=0?'+':'')+p.toFixed(2)+'%'
  $('#s-base').textContent='$'+money(i.base);$('#s-stock').textContent=i.stock
  if(selType==='limited'){
    let nw=$('#s-news-wrap');nw.classList.add('no-news');$('#s-news').textContent='Limited edition — no news'
    let pnlEl=$('#s-pnl');if(pnlEl)pnlEl.style.display='none'
    let trendEl=$('#s-trend');if(trendEl)trendEl.style.display='none'
    let feeNote=$('#s-fee-note');if(feeNote)feeNote.style.display='none'
  }else{
    let nw=$('#s-news-wrap'),nt=$('#s-news')
    let newsArr=Array.isArray(i.news)?i.news:i.news?[i.news]:[]
    if(newsArr.length){nw.classList.remove('no-news');nt.classList.add('active');nt.innerHTML=newsArr.map(n=>'<div class="news-item">📰 '+n+'</div>').join('')}else{nw.classList.add('no-news');nt.classList.remove('active');nt.textContent='No current news'}
    let pnlEl=$('#s-pnl')
    if(pnlEl){let h=state.hold.find(x=>parseInt(x.id)===parseInt(sel));if(h&&h.cost_basis>0){let cp=((i.sell_price-h.cost_basis)/h.cost_basis*100);pnlEl.innerHTML=`<span class="pnl-label">P/L from buy:</span> <span class="pnl-val ${cp>=0?'up':'down'}">${cp>=0?'+':''}${cp.toFixed(2)}%</span> <span class="pnl-basis">(avg $${money(h.cost_basis)})</span>`;pnlEl.style.display=''}else{pnlEl.style.display='none'}}
    let trendEl=$('#s-trend')
    if(trendEl&&i.trend!==undefined){let t=i.trend;if(Math.abs(t)>0.01){let dir=t>0?'↑ Trending Up':'↓ Trending Down';trendEl.textContent=dir;trendEl.className='trend-indicator '+(t>0?'trend-up':'trend-down');trendEl.style.display=''}else{trendEl.style.display='none'}}
    let feeNote=$('#s-fee-note');if(feeNote){let h=state.hold.find(x=>parseInt(x.id)===parseInt(sel));feeNote.style.display=h&&h.qty>0?'':'none'}
  }
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
    let newsArr=Array.isArray(i.news)?i.news:i.news?[i.news]:[]
    let nw=d.querySelector('.card-news');let nw2=d.querySelector('.card-news2')
    if(newsArr.length>0){nw.textContent='📰 '+newsArr[0];nw.className='card-news has-news'}else{nw.textContent='No news';nw.className='card-news'}
    if(newsArr.length>1&&nw2){nw2.textContent='📰 '+newsArr[1];nw2.className='card-news card-news2 has-news';nw2.style.display=''}else if(nw2){nw2.textContent='';nw2.className='card-news card-news2';nw2.style.display='none'}
    d.classList.toggle('active',parseInt(i.id)===sel);if(!m.contains(d))m.append(d)
  })
  let ids=state.market.map(x=>parseInt(x.id));[...m.children].forEach(c=>{if(!ids.includes(parseInt(c.dataset.id)))c.remove()})
  // Limited shoes
  let lg=$('#limited'),le=$('#limited-empty')
  if(state.limited&&state.limited.length){
    le.classList.add('hidden')
    state.limited.forEach((i,idx)=>{
      let d=lg.querySelector(`[data-id='${i.id}']`)||limitedCard(i,idx)
      d.querySelector('.card-name').textContent=i.name
      let rb=d.querySelector('.card-rarity');rb.textContent=i.rarity.toUpperCase();rb.className='card-rarity '+rarClass(i.rarity)
      d.querySelector('.card-price').textContent='$'+money(i.price);d.querySelector('.card-stock').textContent='Stock: '+i.stock
      let p=pct(i.price,i.base),pc=d.querySelector('.card-pct');pc.textContent=(p>=0?'+':'')+p.toFixed(2)+'%';pc.className='card-pct '+(p>=0?'up':'down')
      if(state.limited_hist&&state.limited_hist[i.id])draw(d.querySelector('canvas'),state.limited_hist[i.id])
      d.classList.toggle('active',parseInt(i.id)===sel&&selType==='limited');if(!lg.contains(d))lg.append(d)
    })
    let lids=state.limited.map(x=>parseInt(x.id));[...lg.children].forEach(c=>{if(!lids.includes(parseInt(c.dataset.id)))c.remove()})
  }else{
    le.classList.remove('hidden');lg.innerHTML=''
  }
  let h=$('#hold'),he=$('#hold-empty'),hc=$('#hold-count');h.innerHTML=''
  if(state.hold.length){he.classList.add('hidden');hc.textContent=state.hold.length+' shoe'+(state.hold.length>1?'s':'')+' owned'
    state.hold.forEach((i,idx)=>{let d=holdCard(i,idx);d.querySelector('.card-name').textContent=i.name;let rb=d.querySelector('.card-rarity');rb.textContent=i.rarity.toUpperCase();rb.className='card-rarity '+rarClass(i.rarity);d.querySelector('.card-qty').textContent='×'+i.qty;h.append(d)})
  }else{he.classList.remove('hidden');hc.textContent='0 shoes owned'}
  if(sel!==null)updSidebar();updPriceTimers()
}

let lastHash=''
const stateHash=(s)=>JSON.stringify([s.balance,s.market.map(m=>[m.id,m.stock,m.price]),s.hold.map(h=>[h.id,h.qty]),s.limited?(s.limited.map(l=>[l.id,l.stock,l.price])):[]])
const fetchState=async()=>{let r=await fetch('/api/state');if(r.ok){let ns=await r.json();serverOffset=ns.server_time-Math.floor(Date.now()/1000);let h=stateHash(ns);let changed=h!==lastHash;state=ns;if(changed){lastHash=h;upd()}updTimer();if(ns.wheel)handleWheel(ns.wheel)}}
setInterval(fetchState,3000)

$('#btn-buy').onclick=()=>{if(sel!==null){if(selType==='limited')actLimited('buy-limited',sel,$('#s-qty').value);else act('buy',sel,$('#s-qty').value)}}
$('#btn-sell').onclick=()=>{if(sel!==null&&selType!=='limited')act('sell',sel,$('#s-qty').value)}
$('#btn-details').onclick=()=>{if(sel!==null){if(selType==='limited')location.href='/limited/'+sel;else location.href='/shoe/'+sel}}
$('#qty-dec').onclick=()=>{let q=$('#s-qty');q.value=Math.max(1,parseInt(q.value)-1)}
$('#qty-inc').onclick=()=>{let q=$('#s-qty');q.value=Math.min(parseInt(q.max)||99,parseInt(q.value)+1)}
$('#qty-max').onclick=()=>{let q=$('#s-qty');q.value=q.max||1}
if($('#sidebar-close'))$('#sidebar-close').onclick=()=>{sel=null;$('#sidebar-empty').classList.remove('hidden');$('#sidebar-content').classList.add('hidden');$$('.card').forEach(c=>c.classList.remove('active'))}

const updBadge=async()=>{let r=await fetch('/api/trade-count');if(r.ok){let j=await r.json(),b=$('#trade-badge');if(j.count>0){b.textContent=j.count;b.classList.remove('hidden')}else{b.classList.add('hidden')}}}
const fetchNotifs=async()=>{let r=await fetch('/api/notifications');if(r.ok){let n=await r.json();n.forEach((x,i)=>setTimeout(()=>toast(x.message,'info'),i*5500))}}
const fetchAnn=async()=>{let r=await fetch('/api/announcements');if(r.ok){let a=await r.json(),bar=$('#announcement-bar');if(bar){if(a.length){bar.innerHTML=a.map(x=>`<div class="announcement"><span class="ann-icon">📢</span><span class="ann-text">${x.message}</span></div>`).join('');bar.classList.add('show');document.body.classList.add('has-announcement')}else{bar.classList.remove('show');document.body.classList.remove('has-announcement')}}}}
const checkHanging=async()=>{let r=await fetch('/api/hanging');if(r.ok){let h=await r.json();if(h.active&&!location.pathname.includes('/hanging')){location.href='/hanging/'+h.victim}}}

// ─── Piñata Event ─────────────────────────────
let pinataActive=false,pinataHitting=false
const confettiEmojis=['🎉','🎊','✨','💰','⭐','🌟','💎','🪅','🎈','🎁']

const spawnConfetti=()=>{
  for(let i=0;i<30;i++){
    let c=document.createElement('div')
    c.className='pinata-confetti'
    c.textContent=confettiEmojis[Math.floor(Math.random()*confettiEmojis.length)]
    c.style.left=Math.random()*100+'vw'
    c.style.top=Math.random()*40+'vh'
    c.style.animationDelay=Math.random()*0.5+'s'
    c.style.animationDuration=(1+Math.random()*1.5)+'s'
    document.body.appendChild(c)
    setTimeout(()=>c.remove(),2500)
  }
}

const checkPinata=async()=>{
  let r=await fetch('/api/pinata')
  if(!r.ok)return
  let p=await r.json()
  let overlay=$('#pinata-overlay')
  if(p.active){
    if(!pinataActive){pinataActive=true;overlay.classList.remove('hidden')}
    $('#pinata-reward-display').textContent=p.reward.toLocaleString()
    $('#pinata-hits-cur').textContent=p.hits
    $('#pinata-hits-max').textContent=p.hits_needed
    let pct=Math.min(100,Math.round(p.hits/p.hits_needed*100))
    $('#pinata-fill').style.width=pct+'%'
    $('#pinata-player-count').textContent=p.participants
    $('#pinata-my-hits').textContent=p.my_hits
  }else{
    if(pinataActive){pinataActive=false;overlay.classList.add('hidden')}
  }
}

const hitPinata=async()=>{
  if(pinataHitting||!pinataActive)return
  pinataHitting=true
  let emoji=$('#pinata-emoji')
  emoji.classList.remove('hit')
  void emoji.offsetWidth
  emoji.classList.add('hit')
  setTimeout(()=>emoji.classList.remove('hit'),300)
  try{
    let r=await fetch('/api/pinata/hit',{method:'POST'})
    if(!r.ok){pinataHitting=false;return}
    let j=await r.json()
    if(j.ok){
      if(j.broken){
        emoji.classList.add('broken')
        spawnConfetti()
        toast('💥 '+j.msg,'info')
        setTimeout(()=>{
          pinataActive=false
          $('#pinata-overlay').classList.add('hidden')
          emoji.classList.remove('broken')
        },1500)
      }else{
        $('#pinata-hits-cur').textContent=j.hits
        let pct=Math.min(100,Math.round(j.hits/j.hits_needed*100))
        $('#pinata-fill').style.width=pct+'%'
        $('#pinata-my-hits').textContent=j.my_hits
      }
    }
  }catch(e){}
  setTimeout(()=>{pinataHitting=false},200)
}

if($('#pinata-target'))$('#pinata-target').onclick=hitPinata

let wheelShowing=false,wheelSpinning=false,wheelAngle=0,wheelAnimId=null,wheelDoneId=0

const drawWheel=(canvas,outcomes,angle)=>{
  let ctx=canvas.getContext('2d'),cx=canvas.width/2,cy=canvas.height/2,r=cx-10
  let n=outcomes.length,arc=Math.PI*2/n
  ctx.clearRect(0,0,canvas.width,canvas.height)
  for(let i=0;i<n;i++){
    let a=angle+i*arc
    ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,r,a,a+arc);ctx.closePath()
    ctx.fillStyle=outcomes[i].color;ctx.fill()
    ctx.strokeStyle='rgba(10,10,15,0.6)';ctx.lineWidth=2;ctx.stroke()
    ctx.save();ctx.translate(cx,cy);ctx.rotate(a+arc/2)
    ctx.fillStyle='#fff';ctx.font='bold 13px Orbitron, sans-serif';ctx.textAlign='center';ctx.textBaseline='middle'
    ctx.shadowColor='rgba(0,0,0,0.8)';ctx.shadowBlur=4
    ctx.fillText(outcomes[i].emoji,r*0.55,-1)
    ctx.font='bold 10px Orbitron, sans-serif'
    ctx.fillText(outcomes[i].label,r*0.55,13)
    ctx.restore()
  }
  ctx.beginPath();ctx.arc(cx,cy,22,0,Math.PI*2);ctx.fillStyle='#1a1a26';ctx.fill()
  ctx.strokeStyle='var(--yellow)';ctx.lineWidth=2;ctx.stroke()
  ctx.fillStyle='#ffd700';ctx.font='16px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText('🎰',cx,cy)
}

const spinWheelTo=(canvas,outcomes,targetIdx,onDone)=>{
  if(wheelSpinning)return
  wheelSpinning=true
  let n=outcomes.length,arc=Math.PI*2/n
  let landAngle=-Math.PI/2-targetIdx*arc-arc/2+(Math.random()-0.5)*arc*0.3
  landAngle=((landAngle%(Math.PI*2))+(Math.PI*2))%(Math.PI*2)
  let extra=landAngle-((wheelAngle%(Math.PI*2))+(Math.PI*2))%(Math.PI*2)
  if(extra<=0)extra+=Math.PI*2
  let totalRotation=6*Math.PI*2+extra
  let startAngle=wheelAngle
  let duration=5000,startTime=performance.now()
  const easeOut=(t)=>1-Math.pow(1-t,4)
  const animate=(now)=>{
    let elapsed=now-startTime
    let t=Math.min(1,elapsed/duration)
    wheelAngle=startAngle+totalRotation*easeOut(t)
    drawWheel(canvas,outcomes,wheelAngle)
    if(t<1){wheelAnimId=requestAnimationFrame(animate)}
    else{wheelSpinning=false;if(onDone)onDone()}
  }
  wheelAnimId=requestAnimationFrame(animate)
}

let wheelSeenId=0,wheelBusy=false
const handleWheel=(w)=>{
  let overlay=$('#wheel-overlay')
  if(!overlay)return
  if(w&&w.active&&w.started!==wheelSeenId&&!wheelBusy&&!wheelSpinning){
    wheelSeenId=w.started
    wheelBusy=true
    wheelShowing=true
    overlay.classList.remove('hidden')
    $('#wheel-target-user').textContent=w.username
    $('#wheel-result').classList.add('hidden')
    let canvas=$('#wheel-canvas')
    wheelAngle=Math.random()*Math.PI*2
    drawWheel(canvas,w.outcomes,wheelAngle)
    setTimeout(()=>{
      spinWheelTo(canvas,w.outcomes,w.outcome_idx,()=>{
        let out=w.outcomes[w.outcome_idx]
        let res=$('#wheel-result')
        res.textContent=out.emoji+' '+out.label
        res.classList.remove('hidden')
        setTimeout(()=>{
          overlay.classList.add('hidden')
          wheelShowing=false
          wheelBusy=false
        },5000)
      })
    },800)
  }
}

fetchState()
updBadge()
fetchNotifs()
fetchAnn()
checkHanging()
checkPinata()
setInterval(updBadge,10000)
setInterval(fetchNotifs,10000)
setInterval(fetchAnn,5000)
setInterval(checkHanging,3000)
setInterval(checkPinata,3000)

// Tab switching
$$('.market-tab').forEach(tab=>{
  tab.onclick=()=>{
    $$('.market-tab').forEach(t=>t.classList.remove('active'))
    tab.classList.add('active')
    let target=tab.dataset.tab
    $('#tab-market').classList.toggle('hidden',target!=='market')
    $('#tab-limited').classList.toggle('hidden',target!=='limited')
    sel=null;selType=target;$('#sidebar-empty').classList.remove('hidden');$('#sidebar-content').classList.add('hidden');$$('.card').forEach(c=>c.classList.remove('active'))
  }
})