const $=q=>document.querySelector(q)
const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),2500)}

const presets=document.querySelectorAll('.preset-btn')
const amtInput=$('#amount')
presets.forEach(b=>b.addEventListener('click',()=>{
    presets.forEach(p=>p.classList.remove('active'))
    b.classList.add('active')
    amtInput.value=b.dataset.amt
}))
amtInput.addEventListener('input',()=>presets.forEach(p=>p.classList.remove('active')))

const fetchBal=async()=>{let r=await fetch('/api/state');if(r.ok){let s=await r.json();$('#bal').textContent=s.balance.toFixed(2)}}

const openBox=async()=>{
    let amount=parseInt(amtInput.value)||0
    if(amount<1000||amount>100000){toast('Amount must be $1,000-$100,000','error');return}
    $('#box-closed').classList.add('hidden')
    $('#box-result').classList.add('hidden')
    $('#box-opening').classList.remove('hidden')
    $('#open-btn').disabled=true
    let r=await fetch('/api/lootbox',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})})
    let j=await r.json()
    setTimeout(()=>{
        $('#box-opening').classList.add('hidden')
        if(!j.ok){toast(j.error||'Failed','error');$('#box-closed').classList.remove('hidden');$('#open-btn').disabled=false;return}
        showResult(j)
        fetchBal()
    },1500)
}

const showResult=(data)=>{
    let rarity=data.shoe.rarity
    $('#result-rarity').textContent=rarity
    $('#result-rarity').className='result-rarity rarity-'+rarity
    $('#result-name').textContent=data.shoe.name
    let ratingClass=data.rating>=6?'rating-positive':data.rating>=4?'rating-neutral':'rating-negative'
    let sign=data.multiplier>=1?'+':''
    let pct=((data.multiplier-1)*100).toFixed(0)
    $('#result-rating').textContent=`${data.rating}/10 (${sign}${pct}%)`
    $('#result-rating').className='rating-val '+ratingClass
    $('#result-paid').textContent='$'+data.paid.toLocaleString()
    $('#result-value').textContent='$'+data.value.toLocaleString()
    let diff=data.value-data.paid
    if(diff>=0){
        $('#result-verdict').textContent='WIN +$'+diff.toLocaleString()
        $('#result-verdict').className='result-verdict verdict-win'
        $('#box-result').style.borderColor='#00ff88'
    }else{
        $('#result-verdict').textContent='LOSS -$'+Math.abs(diff).toLocaleString()
        $('#result-verdict').className='result-verdict verdict-loss'
        $('#box-result').style.borderColor='#ff4444'
    }
    $('#box-result').classList.remove('hidden')
    $('#open-btn').disabled=false
}

$('#lootbox').addEventListener('click',openBox)
$('#open-btn').addEventListener('click',openBox)
$('#open-another').addEventListener('click',(e)=>{e.stopPropagation();$('#box-result').classList.add('hidden');$('#box-closed').classList.remove('hidden')})

fetchBal()
