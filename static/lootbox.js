const $=q=>document.querySelector(q)
const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),2500)}
const checkCourt=async()=>{let r=await fetch('/api/court/state');if(r.ok){let s=await r.json();if(s.active)window.location.href='/court'}}
checkCourt();setInterval(checkCourt,5000)

const presets=document.querySelectorAll('.preset-btn')
const amtInput=$('#amount')
presets.forEach(b=>b.addEventListener('click',()=>{
    presets.forEach(p=>p.classList.remove('active'))
    b.classList.add('active')
    amtInput.value=b.dataset.amt
}))
amtInput.addEventListener('input',()=>presets.forEach(p=>p.classList.remove('active')))

const fetchBal=async()=>{let r=await fetch('/api/state');if(r.ok){let s=await r.json();$('#bal').textContent=s.balance.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}}

const openBox=async()=>{
    let amount=parseInt(amtInput.value)||0
    if(amount<1000||amount>100000){toast('Amount must be $1,000-$100,000','error');return}
    $('#box-idle').classList.add('hidden')
    $('#box-result').classList.add('hidden')
    $('#box-opening').classList.remove('hidden')
    $('#open-btn').disabled=true
    let r=await fetch('/api/lootbox',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})})
    let j=await r.json()
    setTimeout(()=>{
        $('#box-opening').classList.add('hidden')
        if(!j.ok){toast(j.error||'Failed','error');$('#box-idle').classList.remove('hidden');$('#open-btn').disabled=false;return}
        showResult(j)
        fetchBal()
    },1200)
}

const showResult=(data)=>{
    $('#result-rarity').textContent=data.shoe.rarity
    $('#result-rarity').className='result-rarity rarity-'+data.shoe.rarity
    $('#result-name').textContent=data.shoe.name
    let ratingClass=data.rating>=6?'rating-positive':data.rating>=4?'rating-neutral':'rating-negative'
    let sign=data.multiplier>=1?'+':''
    let pct=((data.multiplier-1)*100).toFixed(0)
    $('#result-rating').textContent=`${data.rating}/10 (${sign}${pct}%)`
    $('#result-rating').className='result-rating '+ratingClass
    $('#result-paid').textContent='$'+data.paid.toLocaleString()
    $('#result-price').textContent='$'+data.price.toLocaleString()
    $('#result-value').textContent='$'+Math.round(data.value).toLocaleString()
    let diff=data.value-data.paid
    if(diff>=0){
        $('#result-verdict').textContent='WIN +$'+Math.round(diff).toLocaleString()
        $('#result-verdict').className='result-verdict verdict-win'
    }else{
        $('#result-verdict').textContent='LOSS -$'+Math.round(Math.abs(diff)).toLocaleString()
        $('#result-verdict').className='result-verdict verdict-loss'
    }
    $('#box-result').classList.remove('hidden')
    $('#open-btn').disabled=false
}

const fetchNotifs=async()=>{let r=await fetch('/api/notifications');if(r.ok){let n=await r.json();n.forEach(x=>toast(x.message,'info'))}}
const fetchAnn=async()=>{let r=await fetch('/api/announcements');if(r.ok){let a=await r.json(),bar=document.getElementById('announcement-bar');if(bar){if(a.length){bar.innerHTML=a.map(x=>`<div class="announcement"><span class="ann-icon">📢</span><span class="ann-text">${x.message}</span></div>`).join('');bar.classList.add('show');document.body.classList.add('has-announcement')}else{bar.classList.remove('show');document.body.classList.remove('has-announcement')}}}}
const checkHanging=async()=>{let r=await fetch('/api/hanging');if(r.ok){let h=await r.json();if(h.active&&!location.pathname.includes('/hanging')){location.href='/hanging/'+h.victim}}}

$('#open-btn').addEventListener('click',openBox)
fetchBal()
fetchNotifs()
fetchAnn()
checkHanging()
setInterval(fetchNotifs,10000)
setInterval(fetchAnn,5000)
setInterval(checkHanging,3000)