const $=q=>document.querySelector(q)
const $$=q=>document.querySelectorAll(q)
const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),2500)}
const checkCourt=async()=>{let r=await fetch('/api/court/state');if(r.ok){let s=await r.json();if(s.active)window.location.href='/court'}}
checkCourt();setInterval(checkCourt,5000)

let selectedShoe = null
let myShoes = []
let nextSpin = 0

// Tab switching
$$('.tab-btn').forEach(btn => {
  btn.onclick = () => {
    $$('.tab-btn').forEach(b => b.classList.remove('active'))
    btn.classList.add('active')
    $$('.gambling-section').forEach(s => s.classList.add('hidden'))
    $(`#${btn.dataset.tab}-section`).classList.remove('hidden')
  }
})

// === POT GAMBLING ===
const COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#14b8a6','#3b82f6','#8b5cf6','#ec4899','#f43f5e','#06b6d4']

const showWinner = (name, total) => {
  const overlay = document.createElement('div')
  overlay.className = 'winner-overlay'
  overlay.innerHTML = `
    <div class="winner-card">
      <div class="winner-icon">🎰</div>
      <div class="winner-title">WINNER!</div>
      <div class="winner-name">${name}</div>
      <div class="winner-amount">$${(total||0).toLocaleString()}</div>
    </div>
  `
  document.body.appendChild(overlay)
  setTimeout(() => overlay.remove(), 4000)
}

let isSpinning = false
let lastWinner = null
let spinStartTime = 0

const fetchPot = async () => {
  let r = await fetch('/api/pot/current')
  if (!r.ok) return
  let pot = await r.json()
  
  nextSpin = pot.next_spin
  $('#pot-cap').textContent = pot.cap_display
  $('#pot-total').textContent = pot.total.toLocaleString()
  $('#pot-percent').textContent = pot.percent_filled.toFixed(0)
  $('#pot-fill').style.width = pot.percent_filled + '%'
  
  const wheel = $('#wheel-container')
  
  if (pot.spinning && !isSpinning) {
    isSpinning = true
    spinStartTime = Date.now()
    let winnerAngle = 0
    let currentAngle = 0
    for (let p of pot.participants) {
      let segmentSize = (p.percent / 100) * 360
      if (p.username === pot.winner) {
        winnerAngle = currentAngle + segmentSize / 2
        break
      }
      currentAngle += segmentSize
    }
    let targetAngle = 360 - winnerAngle
    let totalRotation = 1800 + targetAngle + (Math.random() * 20 - 10)
    wheel.style.transition = 'none'
    wheel.style.transform = 'rotate(0deg)'
    setTimeout(() => {
      wheel.style.transition = 'transform 5s cubic-bezier(0.15, 0.85, 0.25, 1)'
      wheel.style.transform = 'rotate(' + totalRotation + 'deg)'
    }, 50)
    setTimeout(() => {
      isSpinning = false
      if (pot.winner) {
        showWinner(pot.winner, pot.total)
        lastWinner = pot.winner
      }
    }, 5500)
  }
  
  if (pot.winner && pot.winner !== lastWinner && !isSpinning && !pot.spinning) {
    lastWinner = pot.winner
    showWinner(pot.winner, pot.total)
  }
  
  if (isSpinning) return
  
  if (pot.participants.length === 0) {
    wheel.innerHTML = '<div class="wheel-empty">No entries yet</div>'
    wheel.style.background = 'var(--card)'
  } else {
    let gradient = ''
    let angle = 0
    pot.participants.forEach((p, i) => {
      const size = (p.percent / 100) * 360
      const color = COLORS[i % COLORS.length]
      gradient += `${color} ${angle}deg ${angle + size}deg,`
      angle += size
    })
    wheel.style.background = `conic-gradient(${gradient.slice(0,-1)})`
    wheel.innerHTML = ''
  }
  
  const list = $('#participants-list')
  list.innerHTML = pot.participants.map((p, i) => `
    <div class="participant${p.is_me ? ' me' : ''}">
      <div class="participant-color" style="background:${COLORS[i % COLORS.length]}"></div>
      <div class="participant-info">
        <div class="participant-name">${p.username}${p.is_me ? ' (you)' : ''}</div>
        <div class="participant-shoes">${p.shoes.length} shoe${p.shoes.length>1?'s':''}</div>
      </div>
      <div class="participant-stats">
        <div class="participant-value">$${p.value.toLocaleString()}</div>
        <div class="participant-percent">${p.percent}%</div>
      </div>
    </div>
  `).join('')
}

const updateTimer = () => {
  const now = Math.floor(Date.now() / 1000)
  const left = Math.max(0, nextSpin - now)
  const mins = Math.floor(left / 60)
  const secs = left % 60
  $('#pot-timer').textContent = `${mins}:${secs.toString().padStart(2, '0')}`
  if (left <= 0 && nextSpin > 0) fetchPot()
}
setInterval(updateTimer, 1000)

const fetchHistory = async () => {
  let r = await fetch('/api/pot/history')
  if (!r.ok) return
  let history = await r.json()
  $('#pot-history').innerHTML = history.map(h => `
    <div class="history-item">
      <span class="history-winner">${h.winner}</span> won 
      <span class="history-amount">$${h.total.toLocaleString()}</span>
      (cap: ${h.cap})
    </div>
  `).join('') || '<div class="history-item">No history yet</div>'
}

const fetchMyShoes = async () => {
  let r = await fetch('/api/my-shoes')
  if (!r.ok) return
  myShoes = await r.json()
  renderShoeSelect()
}

const renderShoeSelect = () => {
  const grid = $('#your-shoes')
  grid.innerHTML = myShoes.map(s => {
    const key = s.appraised ? `a_${s.appraisal_id}` : `h_${s.id}`
    const label = s.appraised ? `⭐${s.rating.toFixed(1)}` : `×${s.qty}`
    return `
      <div class="shoe-option" data-key="${key}" data-id="${s.id}" data-appraisal="${s.appraisal_id || ''}" data-value="${s.price || s.base}">
        <div class="shoe-option-name">${s.name}</div>
        <div class="shoe-option-rarity rarity-${s.rarity}">${s.rarity}</div>
        <div class="shoe-option-value">$${Math.round(s.price || s.base).toLocaleString()}</div>
        <div>${label}</div>
      </div>
    `
  }).join('') || '<p style="text-align:center;color:var(--muted)">No shoes</p>'
  
  $$('.shoe-option').forEach(opt => {
    opt.onclick = () => {
      $$('.shoe-option').forEach(o => o.classList.remove('selected'))
      opt.classList.add('selected')
      selectedShoe = {
        id: parseInt(opt.dataset.id),
        appraisal_id: opt.dataset.appraisal ? parseInt(opt.dataset.appraisal) : null,
        value: parseFloat(opt.dataset.value)
      }
      $('#selected-name').textContent = opt.querySelector('.shoe-option-name').textContent
      $('#selected-value').textContent = Math.round(selectedShoe.value).toLocaleString()
      $('#confirm-enter').disabled = false
    }
  })
}

$('#enter-pot-btn').onclick = () => {
  fetchMyShoes()
  selectedShoe = null
  $('#selected-name').textContent = 'None'
  $('#selected-value').textContent = '0'
  $('#confirm-enter').disabled = true
  $('#enter-modal').classList.remove('hidden')
}

$('#modal-close').onclick = () => $('#enter-modal').classList.add('hidden')
$('#enter-modal').onclick = (e) => { if (e.target.id === 'enter-modal') $('#enter-modal').classList.add('hidden') }

$('#confirm-enter').onclick = async () => {
  if (!selectedShoe) return
  let r = await fetch('/api/pot/enter', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      shoe_id: selectedShoe.appraisal_id ? null : selectedShoe.id,
      appraisal_id: selectedShoe.appraisal_id
    })
  })
  let j = await r.json()
  if (j.ok) {
    toast(`Entered shoe worth $${Math.round(j.value).toLocaleString()}!`)
    $('#enter-modal').classList.add('hidden')
    fetchPot()
    fetchBalance()
  } else {
    toast(j.error || 'Failed', 'error')
  }
}

$('#add-all-btn').onclick = async () => {
  if (myShoes.length === 0) {
    toast('No shoes to add', 'error')
    return
  }
  if (!confirm(`Add all ${myShoes.length} shoes to the pot?`)) return
  let total = 0, count = 0
  for (const s of myShoes) {
    const body = s.appraised 
      ? { appraisal_id: s.appraisal_id }
      : { shoe_id: s.id }
    let r = await fetch('/api/pot/enter', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    })
    let j = await r.json()
    if (j.ok) {
      total += j.value
      count++
    }
  }
  toast(`Added ${count} shoes worth $${Math.round(total).toLocaleString()}!`)
  $('#enter-modal').classList.add('hidden')
  fetchPot()
  fetchBalance()
}

if ($('#spin-btn')) {
  $('#spin-btn').onclick = async () => {
    if (!confirm('Force spin the pot?')) return
    let r = await fetch('/api/pot/spin', { method: 'POST' })
    let j = await r.json()
    if (j.ok) {
      toast('🎰 Pot spun!')
      fetchPot()
      fetchHistory()
    } else {
      toast(j.error || 'Failed', 'error')
    }
  }
}

// === LOOTBOX ===
const presets = $$('.preset-btn')
const lootInput = $('#loot-amount')

presets.forEach(btn => {
  btn.onclick = () => {
    presets.forEach(p => p.classList.remove('active'))
    btn.classList.add('active')
    lootInput.value = btn.dataset.amt
  }
})

lootInput.oninput = () => presets.forEach(p => p.classList.remove('active'))

$('#open-loot-btn').onclick = async () => {
  let amount = parseInt(lootInput.value) || 0
  if (amount < 2500 || amount > 150000) {
    toast('Amount must be $2,500-$150,000', 'error')
    return
  }
  
  $('#loot-idle').classList.add('hidden')
  $('#loot-result').classList.add('hidden')
  $('#loot-opening').classList.remove('hidden')
  
  let r = await fetch('/api/lootbox', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({amount})
  })
  let j = await r.json()
  
  setTimeout(() => {
    $('#loot-opening').classList.add('hidden')
    if (!j.ok) {
      toast(j.error || 'Failed', 'error')
      $('#loot-idle').classList.remove('hidden')
      return
    }
    showLootResult(j)
    fetchBalance()
  }, 1200)
}

const showLootResult = (data) => {
  $('#result-rarity').textContent = data.shoe.rarity
  $('#result-rarity').className = 'result-rarity rarity-' + data.shoe.rarity
  $('#result-name').textContent = data.shoe.name
  
  let ratingClass = data.rating >= 6 ? 'rating-positive' : data.rating >= 4 ? 'rating-neutral' : 'rating-negative'
  let sign = data.multiplier >= 1 ? '+' : ''
  let pct = ((data.multiplier - 1) * 100).toFixed(0)
  $('#result-rating').textContent = `${data.rating}/10 (${sign}${pct}%)`
  $('#result-rating').className = 'result-rating ' + ratingClass
  
  $('#result-paid').textContent = '$' + data.paid.toLocaleString()
  $('#result-price').textContent = '$' + data.price.toLocaleString()
  $('#result-value').textContent = '$' + Math.round(data.value).toLocaleString()
  
  let diff = data.value - data.paid
  let verdict = $('#result-verdict')
  if (diff >= 0) {
    verdict.textContent = 'WIN +$' + Math.round(diff).toLocaleString()
    verdict.className = 'result-verdict verdict-win'
  } else {
    verdict.textContent = 'LOSS -$' + Math.round(Math.abs(diff)).toLocaleString()
    verdict.className = 'result-verdict verdict-loss'
  }
  
  $('#loot-result').classList.remove('hidden')
}

// === COMMON ===
const fetchBalance = async () => {
  let r = await fetch('/api/state')
  if (r.ok) {
    let s = await r.json()
    $('#bal').textContent = s.balance.toFixed(2)
  }
}

const fetchNotifs = async () => {
  let r = await fetch('/api/notifications')
  if (r.ok) {
    let n = await r.json()
    n.forEach(x => toast(x.message, 'info'))
  }
}

const fetchAnn = async () => {
  let r = await fetch('/api/announcements')
  if (r.ok) {
    let a = await r.json()
    let bar = $('#announcement-bar')
    if (bar) {
      if (a.length) {
        bar.innerHTML = a.map(x => `<div class="announcement"><span class="ann-icon">📢</span><span class="ann-text">${x.message}</span></div>`).join('')
        bar.classList.add('show')
        document.body.classList.add('has-announcement')
      } else {
        bar.classList.remove('show')
        document.body.classList.remove('has-announcement')
      }
    }
  }
}

const checkHanging = async () => {
  let r = await fetch('/api/hanging')
  if (r.ok) {
    let h = await r.json()
    if (h.active && !location.pathname.includes('/hanging')) {
      location.href = '/hanging/' + h.victim
    }
  }
}

// Init
fetchPot()
fetchHistory()
fetchBalance()
fetchNotifs()
fetchAnn()
checkHanging()

setInterval(fetchPot, 5000)
setInterval(fetchHistory, 30000)
setInterval(fetchNotifs, 10000)
setInterval(fetchAnn, 5000)
setInterval(checkHanging, 3000)
