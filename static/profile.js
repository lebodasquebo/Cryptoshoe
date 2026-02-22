let profile=null,myShoes=[],theirShoes=[],offerShoes=[],wantShoes=[]
let editorOpen=false
const $=q=>document.querySelector(q),$$=q=>document.querySelectorAll(q)
const checkCourt=async()=>{let r=await fetch('/api/court/state');if(r.ok){let s=await r.json();if(s.active)window.location.href='/court'}}
checkCourt();setInterval(checkCourt,5000)
const money=v=>v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})
const rarClass=r=>({common:'rar-common',uncommon:'rar-uncommon',rare:'rar-rare',epic:'rar-epic',legendary:'rar-legendary',mythic:'rar-mythic',godly:'rar-godly',divine:'rar-divine',grails:'rar-grails',heavenly:'rar-heavenly'}[r]||'rar-common')
const avatarForProfile=()=>profile&&profile.profile_picture&&profile.profile_picture.trim()?profile.profile_picture:`/avatar/${encodeURIComponent(profile?.username||window.PROFILE_USER)}.svg`

const toast=(msg,type='success')=>{
  let t=$('#toast')
  t.textContent=msg
  t.className='toast show '+type
  setTimeout(()=>t.classList.remove('show'),5000)
}

const formatDate=(ts)=>{
  if(!ts)return '-'
  let d=new Date(ts*1000)
  return d.toLocaleDateString()
}

const render=()=>{
  if(!profile)return
  $('#p-name').textContent=profile.username
  $('#p-balance').textContent='$'+money(profile.balance)
  $('#p-shoes').textContent=profile.shoes
  $('#p-joined').textContent=formatDate(profile.joined)
  let avatar=$('#profile-avatar')
  if(avatar){
    avatar.src=avatarForProfile()
    avatar.onerror=()=>{avatar.onerror=null;avatar.src=`/avatar/${encodeURIComponent(profile.username)}.svg`}
  }
  
  const canEdit=!!(profile.can_edit||profile.is_me||window.IS_OWN_PROFILE)
  let editBtn=$('#btn-edit-profile')
  let editor=$('#profile-editor')
  if(canEdit){
    $('#btn-trade').classList.add('hidden')
    $('#btn-trade').style.display='none'
    if(editBtn){
      editBtn.classList.remove('hidden')
      editBtn.style.display=''
      editBtn.textContent=editorOpen?'✖ CLOSE EDITOR':'✏️ EDIT PROFILE'
    }
    if(editor){
      editor.classList.toggle('hidden',!editorOpen)
      editor.style.display=editorOpen?'block':'none'
    }
  }else{
    $('#btn-trade').classList.remove('hidden')
    $('#btn-trade').style.display=''
    if(editBtn){editBtn.classList.add('hidden');editBtn.style.display='none'}
    editorOpen=false
    if(editor){editor.classList.add('hidden');editor.style.display='none'}
  }
  
  let grid=$('#shoes-grid'),empty=$('#shoes-empty')
  let allShoes=[...profile.hold,...profile.appraised.map(a=>({...a,qty:1,appraised:true}))]
  
  if(allShoes.length){
    grid.innerHTML=allShoes.map(s=>`
      <div class="shoe-item${s.variant?' variant-'+s.variant:''}">
        ${s.variant?`<div class="variant-badge ${s.variant}">${s.variant==='rainbow'?'🌈 RAINBOW':'✨ SHINY'}</div>`:''}
        <div class="shoe-item-name">${s.name}</div>
        <div class="shoe-item-rarity ${rarClass(s.rarity)}">${s.rarity.toUpperCase()}</div>
        <div class="shoe-item-qty">${s.appraised?'⭐ '+s.rating.toFixed(1):'×'+s.qty}</div>
      </div>
    `).join('')
    empty.classList.add('hidden')
  }else{
    grid.innerHTML=''
    empty.classList.remove('hidden')
  }
}

const getKey=(s)=>s.appraised?'a_'+s.appraisal_id:'h_'+s.id

const calcTotals=()=>{
  let offerTotal=(parseFloat($('#offer-cash').value)||0)
  offerShoes.forEach(s=>{
    let shoe=myShoes.find(x=>getKey(x)===s.key)
    if(shoe)offerTotal+=(shoe.price||0)*s.qty
  })
  let wantTotal=(parseFloat($('#want-cash').value)||0)
  wantShoes.forEach(s=>{
    let shoe=theirShoes.find(x=>getKey(x)===s.key)
    if(shoe)wantTotal+=(shoe.price||0)*s.qty
  })
  let ot=$('#offer-total')
  let wt=$('#want-total')
  if(ot)ot.textContent='$'+money(offerTotal)
  if(wt)wt.textContent='$'+money(wantTotal)
}

const renderTradeModal=()=>{
  let yourGrid=$('#your-shoes')
  let theirGrid=$('#their-shoes')
  
  yourGrid.innerHTML=myShoes.map(s=>{
    let key=getKey(s)
    let sel=offerShoes.find(x=>x.key===key)
    let vc=s.variant?' variant-'+s.variant:''
    let vb=s.variant?`<div class="variant-badge ${s.variant}">${s.variant==='rainbow'?'🌈':'✨'}</div>`:''
    let label=s.appraised?`⭐${s.rating.toFixed(1)} ${s.name}`:s.name
    return `<div class="shoe-select-item${sel?' selected':''}${vc}" data-key="${key}">
      ${vb}
      <div class="shoe-select-name">${label}</div>
      <span class="shoe-price">$${money(s.price||0)}</span>
      <small>${s.appraised?'Appraised':'Own: '+s.qty}</small>
      ${sel?`<div class="shoe-qty-select">
        <button class="qty-btn" data-key="${key}" data-action="offer-dec">-</button>
        <span>${sel.qty}</span>
        <button class="qty-btn" data-key="${key}" data-action="offer-inc">+</button>
      </div>`:''}
    </div>`
  }).join('')
  
  theirGrid.innerHTML=theirShoes.map(s=>{
    let key=getKey(s)
    let sel=wantShoes.find(x=>x.key===key)
    let vc=s.variant?' variant-'+s.variant:''
    let vb=s.variant?`<div class="variant-badge ${s.variant}">${s.variant==='rainbow'?'🌈':'✨'}</div>`:''
    let label=s.appraised?`⭐${s.rating.toFixed(1)} ${s.name}`:s.name
    return `<div class="shoe-select-item${sel?' selected':''}${vc}" data-key="${key}">
      ${vb}
      <div class="shoe-select-name">${label}</div>
      <span class="shoe-price">$${money(s.price||0)}</span>
      <small>${s.appraised?'Appraised':'Has: '+s.qty}</small>
      ${sel?`<div class="shoe-qty-select">
        <button class="qty-btn" data-key="${key}" data-action="want-dec">-</button>
        <span>${sel.qty}</span>
        <button class="qty-btn" data-key="${key}" data-action="want-inc">+</button>
      </div>`:''}
    </div>`
  }).join('')
  
  $('#offer-selected').innerHTML=offerShoes.map(s=>{let shoe=myShoes.find(x=>getKey(x)===s.key);let vi=shoe&&shoe.variant?`${shoe.variant==='rainbow'?'🌈':'✨'} `:'';return `<span class="selected-shoe">${vi}${s.name}${s.qty>1?' ×'+s.qty:''}</span>`}).join('')
  $('#want-selected').innerHTML=wantShoes.map(s=>{let shoe=theirShoes.find(x=>getKey(x)===s.key);let vi=shoe&&shoe.variant?`${shoe.variant==='rainbow'?'🌈':'✨'} `:'';return `<span class="selected-shoe">${vi}${s.name}${s.qty>1?' ×'+s.qty:''}</span>`}).join('')
  calcTotals()
  
  yourGrid.querySelectorAll('.shoe-select-item').forEach(el=>{
    el.onclick=(e)=>{
      if(e.target.classList.contains('qty-btn'))return
      let key=el.dataset.key
      let shoe=myShoes.find(x=>getKey(x)===key)
      if(!shoe)return
      let idx=offerShoes.findIndex(x=>x.key===key)
      if(idx>=0)offerShoes.splice(idx,1)
      else offerShoes.push({key,id:shoe.id,name:shoe.name,qty:1,max:shoe.qty,appraised:shoe.appraised,appraisal_id:shoe.appraisal_id})
      renderTradeModal()
    }
  })
  
  theirGrid.querySelectorAll('.shoe-select-item').forEach(el=>{
    el.onclick=(e)=>{
      if(e.target.classList.contains('qty-btn'))return
      let key=el.dataset.key
      let shoe=theirShoes.find(x=>getKey(x)===key)
      if(!shoe)return
      let idx=wantShoes.findIndex(x=>x.key===key)
      if(idx>=0)wantShoes.splice(idx,1)
      else wantShoes.push({key,id:shoe.id,name:shoe.name,qty:1,max:shoe.qty,appraised:shoe.appraised,appraisal_id:shoe.appraisal_id})
      renderTradeModal()
    }
  })
  
  document.querySelectorAll('.qty-btn').forEach(btn=>{
    btn.onclick=(e)=>{
      e.stopPropagation()
      let key=btn.dataset.key
      let action=btn.dataset.action
      if(action==='offer-dec'){
        let s=offerShoes.find(x=>x.key===key)
        if(s&&s.qty>1){s.qty--;renderTradeModal()}
      }else if(action==='offer-inc'){
        let s=offerShoes.find(x=>x.key===key)
        let shoe=myShoes.find(x=>getKey(x)===key)
        if(s&&shoe&&s.qty<shoe.qty){s.qty++;renderTradeModal()}
      }else if(action==='want-dec'){
        let s=wantShoes.find(x=>x.key===key)
        if(s&&s.qty>1){s.qty--;renderTradeModal()}
      }else if(action==='want-inc'){
        let s=wantShoes.find(x=>x.key===key)
        let shoe=theirShoes.find(x=>getKey(x)===key)
        if(s&&shoe&&s.qty<shoe.qty){s.qty++;renderTradeModal()}
      }
    }
  })
}

const openTradeModal=async()=>{
  let[r1,r2]=await Promise.all([
    fetch('/api/my-shoes'),
    fetch('/api/user-shoes/'+encodeURIComponent(window.PROFILE_USER))
  ])
  if(r1.ok)myShoes=await r1.json()
  if(r2.ok)theirShoes=await r2.json()
  offerShoes=[]
  wantShoes=[]
  $('#offer-cash').value=0
  $('#want-cash').value=0
  renderTradeModal()
  $('#trade-modal').classList.remove('hidden')
}

const submitTrade=async()=>{
  let offerCash=parseFloat($('#offer-cash').value)||0
  let wantCash=parseFloat($('#want-cash').value)||0
  
  if(offerShoes.length===0&&wantShoes.length===0&&offerCash===0&&wantCash===0){
    toast('Add something to trade','error')
    return
  }
  
  let r=await fetch('/api/trade/create',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      to_user:window.PROFILE_USER,
      offer_shoes:offerShoes.map(s=>({id:s.id,qty:s.qty,appraised:s.appraised,appraisal_id:s.appraisal_id})),
      offer_cash:offerCash,
      want_shoes:wantShoes.map(s=>({id:s.id,qty:s.qty,appraised:s.appraised,appraisal_id:s.appraisal_id})),
      want_cash:wantCash
    })
  })
  
  if(r.ok){
    let j=await r.json()
    if(j.ok){
      toast('Trade request sent!')
      $('#trade-modal').classList.add('hidden')
    }else toast(j.error||'Failed','error')
  }else toast('Request failed','error')
}

const fetchProfile=async()=>{
  let r=await fetch('/api/user/'+encodeURIComponent(window.PROFILE_USER))
  if(r.ok){profile=await r.json();render()}
  else{$('#p-name').textContent='User not found'}
}

const uploadAvatar=async(file)=>{
  if(!file)return
  if(!file.type.startsWith('image/')){toast('Please choose an image file','error');return}
  let fd=new FormData()
  fd.append('image',file)
  let r=await fetch('/api/profile/picture',{method:'POST',body:fd})
  if(r.ok){
    let j=await r.json()
    if(j.ok){
      if(!profile)profile={}
      profile.profile_picture=j.profile_picture
      render()
      toast('Profile picture updated')
    }else toast(j.error||'Upload failed','error')
  }else toast('Upload failed','error')
}

const resetAvatar=async()=>{
  let r=await fetch('/api/profile/picture',{method:'DELETE'})
  if(r.ok){
    let j=await r.json()
    if(j.ok){
      profile.profile_picture=''
      render()
      toast('Profile picture reset')
    }else toast(j.error||'Failed','error')
  }else toast('Failed','error')
}

const toggleProfileEditor=()=>{
  editorOpen=!editorOpen
  render()
}

const fetchBalance=async()=>{
  let r=await fetch('/api/state')
  if(r.ok){let s=await r.json();$('#bal').textContent=money(s.balance)}
}

const updBadge=async()=>{
  let r=await fetch('/api/trade-count')
  if(r.ok){
    let j=await r.json()
    let b=$('#trade-badge')
    if(b){
      if(j.count>0){b.textContent=j.count;b.classList.remove('hidden')}
      else{b.classList.add('hidden')}
    }
  }
}

$('#btn-trade').onclick=openTradeModal
let editProfileBtn=$('#btn-edit-profile')
if(editProfileBtn)editProfileBtn.onclick=toggleProfileEditor
$('#modal-close').onclick=()=>$('#trade-modal').classList.add('hidden')
$('#trade-modal').onclick=(e)=>{if(e.target.id==='trade-modal')$('#trade-modal').classList.add('hidden')}
$('#submit-trade').onclick=submitTrade
$('#offer-cash').oninput=calcTotals
$('#want-cash').oninput=calcTotals
let avatarFile=$('#avatar-file')
if(avatarFile)avatarFile.onchange=(e)=>{let f=e.target.files&&e.target.files[0];uploadAvatar(f);e.target.value=''}
let avatarCamera=$('#avatar-camera')
if(avatarCamera)avatarCamera.onchange=(e)=>{let f=e.target.files&&e.target.files[0];uploadAvatar(f);e.target.value=''}
let avatarRemove=$('#avatar-remove')
if(avatarRemove)avatarRemove.onclick=resetAvatar

// If own profile, ensure edit button visible immediately (don't wait for API)
if(window.IS_OWN_PROFILE){
  let eb=$('#btn-edit-profile')
  if(eb){eb.classList.remove('hidden');eb.style.display=''}
  let tb=$('#btn-trade')
  if(tb){tb.classList.add('hidden');tb.style.display='none'}
}

const fetchNotifs=async()=>{let r=await fetch('/api/notifications');if(r.ok){let n=await r.json();n.forEach((x,i)=>setTimeout(()=>toast(x.message,'info'),i*5500))}}
const fetchAnn=async()=>{let r=await fetch('/api/announcements');if(r.ok){let a=await r.json(),bar=document.getElementById('announcement-bar');if(bar){if(a.length){bar.innerHTML=a.map(x=>`<div class="announcement"><span class="ann-icon">📢</span><span class="ann-text">${x.message}</span></div>`).join('');bar.classList.add('show');document.body.classList.add('has-announcement')}else{bar.classList.remove('show');document.body.classList.remove('has-announcement')}}}}
const checkHanging=async()=>{let r=await fetch('/api/hanging');if(r.ok){let h=await r.json();if(h.active&&!location.pathname.includes('/hanging')){location.href='/hanging/'+h.victim}}}

fetchProfile()
fetchBalance()
updBadge()
fetchNotifs()
fetchAnn()
checkHanging()
setInterval(updBadge,10000)
setInterval(fetchNotifs,10000)
setInterval(fetchAnn,5000)
setInterval(checkHanging,3000)