const $=q=>document.querySelector(q)
const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),3000)}

const loadUsers=async()=>{
    let r=await fetch('/api/admin/users')
    if(r.ok){
        let users=await r.json()
        $('#users-list').innerHTML=users.map(u=>`
            <div class="admin-user">
                <span class="admin-user-name">${u.username}</span>
                <div class="admin-user-stats">
                    <span class="admin-user-stat">💰 $${u.balance.toFixed(0)}</span>
                    <span class="admin-user-stat">👟 ${u.shoes}</span>
                    <span class="admin-user-stat">⭐ ${u.appraised}</span>
                </div>
            </div>
        `).join('')
    }
}

const loadShoes=async()=>{
    let r=await fetch('/api/admin/shoes')
    if(r.ok){
        let shoes=await r.json()
        $('#shoe-select').innerHTML=shoes.map(s=>`<option value="${s.id}">[${s.rarity}] ${s.name}</option>`).join('')
    }
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
    if(!user){toast('Enter username','error');return}
    let r=await fetch('/api/admin/shoe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,shoe_id,qty,action:'give'})})
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
    if(!user){toast('Enter a username','error');return}
    if(duration==='perm'&&!confirm(`PERMANENTLY ban and DELETE ${user}?`))return
    let r=await fetch('/api/admin/ban',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,duration})})
    let j=await r.json()
    if(j.ok){toast(j.msg);loadUsers();$('#ban-user').value=''}
    else toast(j.error,'error')
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
    if(!message){toast('Enter a message','error');return}
    let r=await fetch('/api/admin/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,duration})})
    let j=await r.json()
    if(j.ok){toast('📢 '+j.msg);$('#broadcast-msg').value=''}
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
    if(r.ok){let s=await r.json();$('#bal').textContent=s.balance.toFixed(2)}
}

loadUsers()
loadShoes()
fetchBalance()
checkCourtStatus()
setInterval(checkCourtStatus,5000)