console.log('Admin JS loaded')
const $=q=>document.querySelector(q)
const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),3000)}

const loadUsers=async()=>{
    let r=await fetch('/api/admin/users')
    if(r.ok){
        let users=await r.json()
        $('#users-list').innerHTML=users.map(u=>{
            let banTag=''
            if(u.ban_active){
                let rem=u.ban_remaining
                let timeStr
                if(rem>86400)timeStr=Math.floor(rem/86400)+'d '+Math.floor((rem%86400)/3600)+'h'
                else if(rem>3600)timeStr=Math.floor(rem/3600)+'h '+Math.floor((rem%3600)/60)+'m'
                else timeStr=Math.floor(rem/60)+'m '+rem%60+'s'
                let reasonStr=u.ban_reason?' — '+u.ban_reason:''
                banTag=`<div class="admin-user-ban">⛔ Banned: ${timeStr} left${reasonStr}</div>`
            }
            return `
            <div class="admin-user${u.ban_active?' banned':''}">
                <span class="admin-user-name">${u.username}</span>
                <div class="admin-user-stats">
                    <span class="admin-user-stat">💰 $${u.balance.toFixed(0)}</span>
                    <span class="admin-user-stat">👟 ${u.shoes}</span>
                    <span class="admin-user-stat">⭐ ${u.appraised}</span>
                </div>
                ${banTag}
            </div>`
        }).join('')
    }
}

let allShoes=[]
const loadShoes=async()=>{
    let r=await fetch('/api/admin/shoes')
    if(r.ok){
        allShoes=await r.json()
        renderShoeSelects()
    }
}
const renderShoeSelects=(filter='')=>{
    let filtered=filter?allShoes.filter(s=>s.rarity===filter):allShoes
    $('#shoe-select').innerHTML=filtered.map(s=>`<option value="${s.id}">[${s.rarity.toUpperCase()}] ${s.name}</option>`).join('')
    let addSelect=$('#add-shoe-id')
    if(addSelect)addSelect.innerHTML='<option value="">Select Shoe...</option>'+filtered.map(s=>`<option value="${s.id}">[${s.rarity.toUpperCase()}] ${s.name} - $${Math.round(s.base).toLocaleString()}</option>`).join('')
}
window.filterRarity=()=>{renderShoeSelects($('#rarity-filter').value)}

window.addToStock=async()=>{
    let shoeId=$('#add-shoe-id').value
    let stock=parseInt($('#add-shoe-stock').value)||5
    let price=$('#add-shoe-price').value?parseFloat($('#add-shoe-price').value):null
    if(!shoeId){toast('Select a shoe','error');return}
    let body={shoe_id:parseInt(shoeId),stock}
    if(price)body.price=price
    let r=await fetch('/api/admin/add-to-stock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    let j=await r.json()
    if(j.ok){toast(`Added ${j.name} x${stock} to stock at $${j.price.toLocaleString()}`);$('#add-shoe-id').value=''}
    else toast(j.error,'error')
}

window.giveMoney=async()=>{
    let user=$('#money-user').value.trim()
    let amount=parseFloat($('#money-amount').value)||0
    if(!user){toast('Enter username','error');return}
    let r=await fetch('/api/admin/money',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,amount})})
    let j=await r.json()
    if(j.ok){toast(`${amount>=0?'Gave':'Took'} $${Math.abs(amount)} ${amount>=0?'to':'from'} ${user}`);loadUsers();$('#money-user').value='';$('#money-amount').value=''}
    else toast(j.error,'error')
}

window.giveShoe=async()=>{
    let user=$('#shoe-user').value.trim()
    let shoe_id=parseInt($('#shoe-select').value)
    let qty=parseInt($('#shoe-qty').value)||1
    let appraised=$('#shoe-appraised').checked
    let variant=$('#shoe-variant').value
    let rating=parseInt($('#shoe-rating').value)||null
    if(!user){toast('Enter username','error');return}
    let body={username:user,shoe_id,qty,action:'give'}
    if(appraised){
        body.appraised=true
        body.variant=variant
        if(rating)body.rating=rating
        if(rating)body.multiplier=rating/100
    }
    let r=await fetch('/api/admin/shoe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    let j=await r.json()
    if(j.ok){toast(`Gave ${qty}x shoe to ${user}`);loadUsers()}
    else toast(j.error,'error')
}

window.takeShoe=async()=>{
    let user=$('#shoe-user').value.trim()
    let shoe_id=parseInt($('#shoe-select').value)
    let qty=parseInt($('#shoe-qty').value)||1
    if(!user){toast('Enter username','error');return}
    let r=await fetch('/api/admin/shoe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,shoe_id,qty,action:'take'})})
    let j=await r.json()
    if(j.ok){toast(`Took ${qty}x shoe from ${user}`);loadUsers()}
    else toast(j.error,'error')
}

window.resetStock=async()=>{
    let r=await fetch('/api/admin/refresh',{method:'POST'})
    let j=await r.json()
    if(j.ok)toast('Stock refreshed!')
    else toast(j.error,'error')
}

window.banUser=async()=>{
    let user=$('#ban-user').value.trim()
    let duration=$('#ban-duration').value
    let customValue=parseInt($('#ban-custom-value')?.value)||0
    let customUnit=$('#ban-custom-unit')?.value||'h'
    let reason=$('#ban-reason')?.value.trim()||''
    if(!user){toast('Enter a username','error');return}
    if(duration==='perm'&&!confirm(`PERMANENTLY ban and DELETE ${user}?`))return
    let payload={username:user,duration,reason}
    if(customValue>0){
        payload.duration='custom'
        payload.custom_value=customValue
        payload.custom_unit=customUnit
    }
    let r=await fetch('/api/admin/ban',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    let j=await r.json()
    if(j.ok){toast(j.msg);loadUsers();$('#ban-user').value='';$('#ban-custom-value').value='';$('#ban-reason').value=''}
    else toast(j.error,'error')
}

window.unbanUser=async()=>{
    let user=$('#ban-user').value.trim()
    if(!user){toast('Enter a username','error');return}
    let r=await fetch('/api/admin/unban',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user})})
    let j=await r.json()
    if(j.ok){toast('🔓 '+j.msg);loadUsers();$('#ban-user').value=''}
    else toast(j.error,'error')
}

window.purgeBots=async()=>{
    if(!confirm('Delete all bot accounts and inactive accounts ($10k, 0 shoes)?'))return
    let r=await fetch('/api/admin/purge-bots',{method:'POST',headers:{'Content-Type':'application/json'}})
    let j=await r.json()
    if(j.ok){toast('🤖 '+j.msg);loadUsers()}
    else toast(j.error,'error')
}

window.clearChat=async()=>{
    if(!confirm('Delete ALL chat messages?'))return
    let r=await fetch('/api/admin/clear-chat',{method:'POST',headers:{'Content-Type':'application/json'}})
    let j=await r.json()
    if(j.ok)toast('💬 '+j.msg)
    else toast(j.error,'error')
}

window.banIP=async()=>{
    let user=$('#ip-ban-user').value.trim()
    let duration=$('#ip-ban-duration').value
    if(!user){toast('Enter username','error');return}
    if(!confirm(`Ban IP of ${user} for ${duration}?`))return
    let r=await fetch('/api/admin/ban-ip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,duration})})
    let j=await r.json()
    if(j.ok){toast('🌐 '+j.msg);$('#ip-ban-user').value=''}
    else toast(j.error,'error')
}

window.loadSuspicious=async()=>{
    let r=await fetch('/api/admin/suspicious')
    let j=await r.json()
    if(j.length===0){$('#suspicious-list').innerHTML='<em>No suspicious users found</em>';return}
    $('#suspicious-list').innerHTML=j.map(s=>`<div style="padding:4px 0;border-bottom:1px solid var(--border)"><strong>${s.username}</strong>: $${s.balance?.toLocaleString()||0} (earned $${s.earned_1h?.toLocaleString()||0} in 1h)</div>`).join('')
}

window.swapBalance=async()=>{
    let user1=$('#swap-bal-1').value.trim()
    let user2=$('#swap-bal-2').value.trim()
    if(!user1||!user2){toast('Enter both usernames','error');return}
    let r=await fetch('/api/admin/swap-balance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user1,user2})})
    let j=await r.json()
    if(j.ok){toast(j.msg);loadUsers();$('#swap-bal-1').value='';$('#swap-bal-2').value=''}
    else toast(j.error,'error')
}

window.swapInventory=async()=>{
    let user1=$('#swap-inv-1').value.trim()
    let user2=$('#swap-inv-2').value.trim()
    if(!user1||!user2){toast('Enter both usernames','error');return}
    if(!confirm(`Swap ALL shoes between ${user1} and ${user2}?`))return
    let r=await fetch('/api/admin/swap-inventory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user1,user2})})
    let j=await r.json()
    if(j.ok){toast(j.msg);loadUsers()}
    else toast(j.error,'error')
}

window.broadcast=async()=>{
    let message=$('#broadcast-msg').value.trim()
    let duration=parseInt($('#broadcast-duration')?.value)||60
    let customMins=parseInt($('#broadcast-custom-mins')?.value)||0
    if(customMins>0)duration=customMins*60
    if(!message){toast('Enter a message','error');return}
    let r=await fetch('/api/admin/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,duration})})
    let j=await r.json()
    if(j.ok){toast('📢 '+j.msg);$('#broadcast-msg').value='';if($('#broadcast-custom-mins'))$('#broadcast-custom-mins').value=''}
    else toast(j.error,'error')
}

window.removePfp=async()=>{
    let username=$('#pfp-user')?.value.trim()
    let reason=$('#pfp-reason')?.value.trim()
    if(!username){toast('Enter username','error');return}
    if(!reason){toast('Enter reason','error');return}
    let r=await fetch('/api/admin/remove-pfp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,reason})})
    let j=await r.json()
    if(j.ok){toast(j.msg);$('#pfp-user').value='';$('#pfp-reason').value=''}
    else toast(j.error,'error')
}

window.moneyRain=async()=>{
    let amount=parseInt($('#rain-amount').value)||0
    if(amount<1){toast('Enter an amount','error');return}
    if(!confirm(`Give $${amount.toLocaleString()} to ALL users?`))return
    let r=await fetch('/api/admin/rain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})})
    let j=await r.json()
    if(j.ok){toast(j.msg);loadUsers();$('#rain-amount').value=''}
    else toast(j.error,'error')
}

window.taxAll=async()=>{
    let percent=parseInt($('#tax-percent').value)||0
    if(percent<1||percent>100){toast('Enter 1-100%','error');return}
    if(!confirm(`Tax ${percent}% from ALL users?`))return
    let r=await fetch('/api/admin/tax',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({percent})})
    let j=await r.json()
    if(j.ok){toast(j.msg);loadUsers();$('#tax-percent').value=''}
    else toast(j.error,'error')
}

window.bankruptUser=async()=>{
    let username=$('#bankrupt-user').value.trim()
    if(!username){toast('Enter username','error');return}
    if(!confirm(`Set ${username}'s balance to $0?`))return
    let r=await fetch('/api/admin/bankrupt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username})})
    let j=await r.json()
    if(j.ok){toast(j.msg);loadUsers();$('#bankrupt-user').value=''}
    else toast(j.error,'error')
}

window.jackpot=async()=>{
    let amount=parseInt($('#jackpot-amount').value)||0
    if(amount<1){toast('Enter prize amount','error');return}
    let r=await fetch('/api/admin/jackpot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({amount})})
    let j=await r.json()
    if(j.ok){toast('🎉 '+j.msg);loadUsers();$('#jackpot-amount').value=''}
    else toast(j.error,'error')
}

window.doubleOrNothing=async()=>{
    let username=$('#double-user').value.trim()
    if(!username){toast('Enter username','error');return}
    let r=await fetch('/api/admin/double-or-nothing',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username})})
    let j=await r.json()
    if(j.ok){toast('🎲 '+j.msg);loadUsers();$('#double-user').value=''}
    else toast(j.error,'error')
}

window.shuffleShoes=async()=>{
    let username=$('#shuffle-user').value.trim()
    if(!username){toast('Enter username','error');return}
    if(!confirm(`Shuffle ALL of ${username}'s shoes to random users?`))return
    let r=await fetch('/api/admin/shuffle-shoes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username})})
    let j=await r.json()
    if(j.ok){toast('🌀 '+j.msg);loadUsers();$('#shuffle-user').value=''}
    else toast(j.error,'error')
}

window.giftBomb=async()=>{
    let username=$('#gift-user').value.trim()
    let count=parseInt($('#gift-count').value)||10
    if(!username){toast('Enter username','error');return}
    let r=await fetch('/api/admin/gift-bomb',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,count})})
    let j=await r.json()
    if(j.ok){toast('🎁 '+j.msg);loadUsers();$('#gift-user').value=''}
    else toast(j.error,'error')
}

window.fakeWin=async()=>{
    let username=$('#fake-user').value.trim()
    let amount=parseInt($('#fake-amount').value)||1000000
    if(!username){toast('Enter username','error');return}
    let r=await fetch('/api/admin/fake-win',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,amount})})
    let j=await r.json()
    if(j.ok){toast('😈 '+j.msg);$('#fake-user').value=''}
    else toast(j.error,'error')
}

window.wheelOfFortune=async()=>{
    let username=$('#wheel-user').value.trim()
    let r=await fetch('/api/admin/wheel-of-fortune',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username})})
    let j=await r.json()
    if(j.ok){
        toast('🎰 '+j.msg)
        $('#wheel-user').value=''
        // Show admin wheel overlay
        let overlay=$('#wheel-overlay')
        overlay.classList.remove('hidden')
        $('#wheel-target-user').textContent=j.username
        $('#wheel-result').classList.add('hidden')
        let canvas=$('#wheel-canvas')
        let angle=Math.random()*Math.PI*2
        _adminDrawWheel(canvas,j.outcomes,angle)
        setTimeout(()=>{
            _adminSpinWheel(canvas,j.outcomes,j.outcome_idx,angle,()=>{
                let out=j.outcomes[j.outcome_idx]
                let res=$('#wheel-result')
                res.textContent=out.emoji+' '+out.label
                res.classList.remove('hidden')
                loadUsers()
                setTimeout(()=>{overlay.classList.add('hidden')},5000)
            })
        },800)
    }
    else toast(j.error,'error')
}

// Admin wheel drawing functions
function _adminDrawWheel(canvas,outcomes,angle){
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
    ctx.strokeStyle='#ffd700';ctx.lineWidth=2;ctx.stroke()
    ctx.fillStyle='#ffd700';ctx.font='16px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText('🎰',cx,cy)
}
function _adminSpinWheel(canvas,outcomes,targetIdx,startAngle,onDone){
    let n=outcomes.length,arc=Math.PI*2/n
    let landAngle=-Math.PI/2-targetIdx*arc-arc/2+(Math.random()-0.5)*arc*0.3
    landAngle=((landAngle%(Math.PI*2))+(Math.PI*2))%(Math.PI*2)
    let extra=landAngle-((startAngle%(Math.PI*2))+(Math.PI*2))%(Math.PI*2)
    if(extra<=0)extra+=Math.PI*2
    let totalRotation=6*Math.PI*2+extra
    let duration=5000,startTime=performance.now()
    const easeOut=(t)=>1-Math.pow(1-t,4)
    const animate=(now)=>{
        let elapsed=now-startTime,t=Math.min(1,elapsed/duration)
        let cur=startAngle+totalRotation*easeOut(t)
        _adminDrawWheel(canvas,outcomes,cur)
        if(t<1)requestAnimationFrame(animate)
        else if(onDone)onDone()
    }
    requestAnimationFrame(animate)
}

window.dropPinata=async()=>{
    let reward=parseInt($('#pinata-reward').value)||0
    let hits=parseInt($('#pinata-hits').value)||50
    if(reward<100){toast('Reward must be at least $100','error');return}
    if(!confirm(`Drop piñata with $${reward.toLocaleString()} reward and ${hits} hits needed?`))return
    let r=await fetch('/api/admin/pinata',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reward,hits})})
    let j=await r.json()
    if(j.ok){toast('🪅 '+j.msg);checkPinataStatus()}
    else toast(j.error,'error')
}

window.cancelPinata=async()=>{
    if(!confirm('Cancel the active piñata?'))return
    let r=await fetch('/api/admin/pinata/cancel',{method:'POST'})
    let j=await r.json()
    if(j.ok){toast(j.msg);checkPinataStatus()}
    else toast(j.error,'error')
}

const checkPinataStatus=async()=>{
    let r=await fetch('/api/pinata')
    if(r.ok){
        let s=await r.json(),el=$('#pinata-status')
        if(s.active){
            let pct=Math.round(s.hits/s.hits_needed*100)
            el.innerHTML=`🪅 ACTIVE — ${s.hits}/${s.hits_needed} hits (${pct}%) — ${s.participants} player${s.participants!==1?'s':''} — $${s.reward.toLocaleString()} pool`
        }else{el.innerHTML='No active piñata'}
    }
}
setInterval(checkPinataStatus,3000)

window.startTrial=async()=>{
    let defendant=$('#court-defendant').value.trim()
    let accusation=$('#court-accusation').value.trim()||'unspecified crimes'
    if(!defendant){toast('Enter defendant username','error');return}
    let r=await fetch('/api/admin/court/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({defendant,accusation})})
    let j=await r.json()
    if(j.ok){toast('⚖️ '+j.msg);$('#court-defendant').value='';$('#court-accusation').value='';checkCourtStatus()}
    else toast(j.error,'error')
}

window.addCharge=async()=>{
    let accusation=$('#new-charge').value.trim()
    if(!accusation){toast('Enter accusation','error');return}
    let r=await fetch('/api/admin/court/accuse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({accusation})})
    let j=await r.json()
    if(j.ok){toast('Charge added');$('#new-charge').value=''}
    else toast(j.error,'error')
}

window.deliverVerdict=async()=>{
    let verdict=$('#verdict-choice').value
    let punishment=$('#verdict-punishment').value.trim()
    let r=await fetch('/api/admin/court/verdict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({verdict,punishment})})
    let j=await r.json()
    if(j.ok){toast('🔨 '+j.msg);$('#verdict-punishment').value='';checkCourtStatus()}
    else toast(j.error,'error')
}

window.endCourt=async()=>{
    if(!confirm('End court session and release everyone?'))return
    let r=await fetch('/api/admin/court/end',{method:'POST'})
    let j=await r.json()
    if(j.ok){toast(j.msg);checkCourtStatus()}
    else toast(j.error,'error')
}

const checkCourtStatus=async()=>{
    let r=await fetch('/api/court/state')
    if(r.ok){
        let s=await r.json()
        let el=$('#court-status')
        if(s.active){
            el.innerHTML=`<div class="court-active">🔴 COURT IN SESSION<br>Defendant: <strong>${s.defendant}</strong><br>Charge: ${s.accusation}<br>Votes: Guilty ${s.votes.guilty} | Innocent ${s.votes.innocent}</div>`
        }else{
            el.innerHTML='<div class="court-inactive">No active trial</div>'
        }
    }
}

const fetchBalance=async()=>{
    let r=await fetch('/api/state')
    if(r.ok){let s=await r.json();$('#bal').textContent=s.balance.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
}

window.createLimited=async()=>{
    let name=$('#ltd-name').value.trim()
    let rarity=$('#ltd-rarity').value
    let base=parseFloat($('#ltd-base').value)||0
    let stock=parseInt($('#ltd-stock').value)||1
    if(!name){toast('Enter a name','error');return}
    if(base<=0){toast('Enter a base price','error');return}
    let r=await fetch('/api/admin/limited',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,rarity,base,stock})})
    let j=await r.json()
    if(j.ok){toast(`Created limited shoe: ${name}`);$('#ltd-name').value='';$('#ltd-base').value='';loadLimited()}
    else toast(j.error,'error')
}

window.deleteLimited=async(id)=>{
    if(!confirm('Remove this limited shoe?'))return
    let r=await fetch('/api/admin/limited/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})})
    let j=await r.json()
    if(j.ok){toast(`Removed: ${j.name}`);loadLimited()}
    else toast(j.error,'error')
}

window.clearAllLimited=async()=>{
    if(!confirm('Clear ALL limited shoes from market AND remove them from the database? This will also remove holdings/appraisals of limited shoes.'))return
    let r=await fetch('/api/admin/limited/clear-all',{method:'POST',headers:{'Content-Type':'application/json'}})
    let j=await r.json()
    if(j.ok){toast(j.msg);loadLimited()}
    else toast(j.error,'error')
}

const loadLimited=async()=>{
    let r=await fetch('/api/admin/limited')
    if(r.ok){
        let items=await r.json()
        let list=$('#limited-list')
        if(!items.length){list.innerHTML='<div style="color:var(--text3)">No limited shoes</div>';return}
        list.innerHTML=items.map(i=>`<div style="display:flex;align-items:center;gap:8px;padding:6px;background:var(--bg3);border-radius:6px;margin-bottom:4px"><span style="flex:1"><strong>${i.name}</strong> [${i.rarity.toUpperCase()}] — $${Math.round(i.base).toLocaleString()} — Stock: ${i.stock}</span><button onclick="deleteLimited(${i.id})" class="ban-btn" style="padding:4px 8px;font-size:11px">Remove</button></div>`).join('')
    }
}

loadUsers()
loadShoes()
loadLimited()
fetchBalance()
checkCourtStatus()
setInterval(checkCourtStatus,5000)
setInterval(loadUsers,15000)