const $=q=>document.querySelector(q)
const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),2500)}

const loadUsers=async()=>{
    let r=await fetch('/api/admin/users')
    if(r.ok){
        let users=await r.json()
        $('#users-list').innerHTML=users.map(u=>`
            <div class="admin-user">
                <span class="admin-user-name">${u.username}</span>
                <div class="admin-user-stats">
                    <span class="admin-user-stat">💰 <span class="admin-user-val">$${u.balance.toFixed(2)}</span></span>
                    <span class="admin-user-stat">👟 <span class="admin-user-val">${u.shoes}</span></span>
                    <span class="admin-user-stat">⭐ <span class="admin-user-val">${u.appraised}</span></span>
                </div>
            </div>
        `).join('')
    }
}

const loadShoes=async()=>{
    let r=await fetch('/api/admin/shoes')
    if(r.ok){
        let shoes=await r.json()
        $('#shoe-select').innerHTML=shoes.map(s=>`<option value="${s.id}">[${s.rarity}] ${s.name} ($${s.base})</option>`).join('')
    }
}

window.giveMoney=async()=>{
    let user=$('#money-user').value.trim()
    let amount=parseFloat($('#money-amount').value)||0
    if(!user){toast('Enter username','error');return}
    let r=await fetch('/api/admin/money',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,amount})})
    let j=await r.json()
    if(j.ok){toast(`${amount>=0?'Gave':'Took'} $${Math.abs(amount)} ${amount>=0?'to':'from'} ${user}`);loadUsers();$('#money-user').value='';$('#money-amount').value=''}
    else toast(j.error||'Failed','error')
}

window.giveShoe=async()=>{
    let user=$('#shoe-user').value.trim()
    let shoe_id=parseInt($('#shoe-select').value)
    let qty=parseInt($('#shoe-qty').value)||1
    if(!user){toast('Enter username','error');return}
    let r=await fetch('/api/admin/shoe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,shoe_id,qty,action:'give'})})
    let j=await r.json()
    if(j.ok){toast(`Gave ${qty}x shoe to ${user}`);loadUsers()}
    else toast(j.error||'Failed','error')
}

window.takeShoe=async()=>{
    let user=$('#shoe-user').value.trim()
    let shoe_id=parseInt($('#shoe-select').value)
    let qty=parseInt($('#shoe-qty').value)||1
    if(!user){toast('Enter username','error');return}
    let r=await fetch('/api/admin/shoe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,shoe_id,qty,action:'take'})})
    let j=await r.json()
    if(j.ok){toast(`Took ${qty}x shoe from ${user}`);loadUsers()}
    else toast(j.error||'Failed','error')
}

window.resetStock=async()=>{
    let r=await fetch('/api/admin/refresh',{method:'POST'})
    let j=await r.json()
    if(j.ok)toast('Stock refreshed!')
    else toast(j.error||'Failed','error')
}

window.banUser=async()=>{
    let user=$('#ban-user').value.trim()
    let duration=$('#ban-duration').value
    if(!user){toast('Enter a username','error');return}
    if(duration==='perm'){
        if(!confirm(`PERMANENTLY ban and DELETE ${user}? This cannot be undone!`))return
    }
    let r=await fetch('/api/admin/ban',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,duration})})
    let j=await r.json()
    if(j.ok){toast(j.msg||'Banned');loadUsers();$('#ban-user').value=''}
    else toast(j.error,'error')
}

const fetchBalance=async()=>{
    let r=await fetch('/api/state')
    if(r.ok){let s=await r.json();$('#bal').textContent=s.balance.toFixed(2)}
}

loadUsers()
loadShoes()
fetchBalance()
