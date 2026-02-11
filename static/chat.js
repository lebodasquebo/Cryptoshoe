const $=q=>document.querySelector(q)
const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),2500)}
const checkCourt=async()=>{let r=await fetch('/api/court/state');if(r.ok){let s=await r.json();if(s.active)window.location.href='/court'}}
checkCourt();setInterval(checkCourt,5000)

let lastMsgId = 0
let renderedIds = new Set()
let initialized = false

const formatTime = (ts) => {
  let d = new Date(ts * 1000)
  return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})
}

const initChat = async () => {
  let r = await fetch('/api/chat/latest-id')
  if (r.ok) {
    let data = await r.json()
    lastMsgId = Math.max(0, data.id - 50)
    initialized = true
    await fetchMessages()
    $('#messages').scrollTop = $('#messages').scrollHeight
  }
}

const fetchMessages = async () => {
  let r = await fetch(`/api/chat/messages?since=${lastMsgId}`)
  if (!r.ok) return
  let msgs = await r.json()
  let container = $('#messages')
  let shouldScroll = container.scrollHeight - container.scrollTop <= container.clientHeight + 100
  
  for (let m of msgs) {
    if (renderedIds.has(m.id)) continue
    renderedIds.add(m.id)
    
    let div = document.createElement('div')
    div.className = 'msg'
    let isAdmin = m.username.includes('👑')
    let cleanName = m.username.replace('👑 ', '')
    div.innerHTML = `
      <div class="msg-header">
        <a href="/user/${cleanName}" class="msg-user${isAdmin ? ' admin' : ''}">${m.username}</a>
        <span class="msg-time">${formatTime(m.ts)}</span>
      </div>
      <div class="msg-text">${highlightMentions(m.message)}</div>
    `
    container.appendChild(div)
    lastMsgId = m.id
  }
  
  if (msgs.length && shouldScroll) {
    container.scrollTop = container.scrollHeight
  }
}

const escapeHtml = (text) => {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

const highlightMentions = (text) => {
  let escaped = escapeHtml(text)
  return escaped.replace(/@([A-Za-z0-9_-]+)/g, '<span class="mention">@$1</span>')
}

const sendMessage = async () => {
  let input = $('#chat-input')
  let msg = input.value.trim()
  if (!msg) return
  
  input.value = ''
  input.focus()
  $('#mention-dropdown').classList.remove('show')
  mentionStart = -1
  
  let r = await fetch('/api/chat/send', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: msg})
  })
  let j = await r.json()
  if (!j.ok) {
    toast(j.error || 'Failed to send', 'error')
  } else {
    fetchMessages()
  }
}

let onlineUsers = []

const fetchOnline = async () => {
  let r = await fetch('/api/chat/online')
  if (!r.ok) return
  let users = await r.json()
  onlineUsers = users
  $('#online-count').textContent = users.length
  $('#online-users').innerHTML = users.map(u => {
    let cleanName = u.replace('👑 ', '')
    return `<a href="/user/${cleanName}" class="online-user${u.includes('👑') ? ' admin' : ''}">${u} <span class="trade-link">🤝</span></a>`
  }).join('')
}

const fetchBalance = async () => {
  let r = await fetch('/api/state')
  if (r.ok) {
    let s = await r.json()
    $('#bal').textContent = s.balance.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})
  }
}

const fetchAnn = async () => {
  let r = await fetch('/api/announcements')
  if (r.ok) {
    let a = await r.json()
    let bar = $('#announcement-bar')
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

const checkHanging = async () => {
  let r = await fetch('/api/hanging')
  if (r.ok) {
    let h = await r.json()
    if (h.active && !location.pathname.includes('/hanging')) {
      location.href = '/hanging/' + h.victim
    }
  }
}

let mentionStart = -1
let selectedMentionIndex = 0

const showMentionDropdown = (query) => {
  let dropdown = $('#mention-dropdown')
  let filtered = onlineUsers.filter(u => {
    let clean = u.replace('👑 ', '').toLowerCase()
    return clean.includes(query.toLowerCase())
  })
  
  if (filtered.length === 0) {
    dropdown.classList.remove('show')
    return
  }
  
  let maxShow = 8
  let hasMore = filtered.length > maxShow
  let toShow = filtered.slice(0, maxShow)
  
  dropdown.innerHTML = toShow.map((u, i) => {
    let clean = u.replace('👑 ', '')
    return `<div class="mention-option${i === selectedMentionIndex ? ' selected' : ''}${u.includes('👑') ? ' admin' : ''}" data-username="${clean}">${u}</div>`
  }).join('') + (hasMore ? `<div class="mention-more">... ${filtered.length - maxShow} more</div>` : '')
  
  dropdown.classList.add('show')
  
  dropdown.querySelectorAll('.mention-option').forEach((opt, i) => {
    opt.onclick = () => insertMention(opt.dataset.username)
  })
}

const insertMention = (username) => {
  let input = $('#chat-input')
  let text = input.value
  let before = text.substring(0, mentionStart)
  let after = text.substring(input.selectionStart)
  input.value = before + '@' + username + ' ' + after
  input.focus()
  let pos = before.length + username.length + 2
  input.setSelectionRange(pos, pos)
  $('#mention-dropdown').classList.remove('show')
  mentionStart = -1
}

$('#chat-input').addEventListener('input', e => {
  let input = e.target
  let text = input.value
  let pos = input.selectionStart
  
  let lastAt = text.lastIndexOf('@', pos - 1)
  if (lastAt !== -1) {
    let afterAt = text.substring(lastAt + 1, pos)
    if (afterAt.indexOf(' ') === -1) {
      mentionStart = lastAt
      showMentionDropdown(afterAt)
      return
    }
  }
  
  $('#mention-dropdown').classList.remove('show')
  mentionStart = -1
})

$('#chat-input').addEventListener('keydown', e => {
  let dropdown = $('#mention-dropdown')
  if (!dropdown.classList.contains('show')) return
  
  let options = dropdown.querySelectorAll('.mention-option')
  if (options.length === 0) return
  
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedMentionIndex = (selectedMentionIndex + 1) % options.length
    showMentionDropdown($('#chat-input').value.substring(mentionStart + 1, $('#chat-input').selectionStart))
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedMentionIndex = selectedMentionIndex === 0 ? options.length - 1 : selectedMentionIndex - 1
    showMentionDropdown($('#chat-input').value.substring(mentionStart + 1, $('#chat-input').selectionStart))
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    e.preventDefault()
    let selected = options[selectedMentionIndex]
    if (selected) insertMention(selected.dataset.username)
  } else if (e.key === 'Escape') {
    dropdown.classList.remove('show')
    mentionStart = -1
  }
})

document.addEventListener('click', e => {
  let dropdown = $('#mention-dropdown')
  let input = $('#chat-input')
  if (!dropdown.contains(e.target) && e.target !== input) {
    dropdown.classList.remove('show')
    mentionStart = -1
  }
})

$('#send-btn').addEventListener('click', sendMessage)
$('#chat-input').addEventListener('keypress', e => {
  if (e.key === 'Enter' && !$('#mention-dropdown').classList.contains('show')) sendMessage()
})

const fetchNotifs = async () => {
  let r = await fetch('/api/notifications')
  if (r.ok) {
    let n = await r.json()
    n.forEach(x => toast(x.message, 'info'))
  }
}

initChat()
fetchOnline()
fetchBalance()
fetchAnn()
checkHanging()
fetchNotifs()

setInterval(fetchMessages, 1500)
setInterval(fetchOnline, 5000)
setInterval(fetchAnn, 5000)
setInterval(checkHanging, 3000)
setInterval(fetchNotifs, 3000)