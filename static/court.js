const $=q=>document.querySelector(q)
const toast=(msg,type='success')=>{let t=$('#toast');t.textContent=msg;t.className='toast show '+type;setTimeout(()=>t.classList.remove('show'),3000)}

let lastMsgId = 0
let courtActive = false

const fetchState = async () => {
    let r = await fetch('/api/court/state')
    if (!r.ok) return
    let s = await r.json()
    
    if (s.active) {
        $('#court-inactive').classList.add('hidden')
        $('#court-active').classList.remove('hidden')
        if (window.IS_ADMIN) $('#admin-start').style.display = 'none'
        
        $('#defendant-name').textContent = s.defendant
        $('#accusation-text').textContent = s.accusation
        $('#court-status').textContent = s.status === 'verdict' ? 'VERDICT DELIVERED' : 'TRIAL IN PROGRESS'
        $('#guilty-count').textContent = s.votes.guilty
        $('#innocent-count').textContent = s.votes.innocent
        
        if (s.is_defendant) {
            $('#jury-buttons').classList.add('hidden')
            $('#jury-voted').classList.add('hidden')
            $('#defendant-notice').classList.remove('hidden')
        } else if (s.my_vote) {
            $('#jury-buttons').classList.add('hidden')
            $('#defendant-notice').classList.add('hidden')
            $('#jury-voted').classList.remove('hidden')
            $('#my-vote-text').textContent = s.my_vote.toUpperCase()
        } else {
            $('#jury-buttons').classList.remove('hidden')
            $('#jury-voted').classList.add('hidden')
            $('#defendant-notice').classList.add('hidden')
        }
        
        if (!courtActive) {
            lastMsgId = 0
            $('#chat-messages').innerHTML = ''
        }
        courtActive = true
    } else {
        $('#court-inactive').classList.remove('hidden')
        $('#court-active').classList.add('hidden')
        if (window.IS_ADMIN) $('#admin-start').style.display = 'flex'
        courtActive = false
    }
}

const fetchMessages = async () => {
    if (!courtActive) return
    let r = await fetch(`/api/court/messages?since=${lastMsgId}`)
    if (!r.ok) return
    let msgs = await r.json()
    let container = $('#chat-messages')
    for (let m of msgs) {
        let div = document.createElement('div')
        div.className = 'chat-msg'
        if (m.is_system) {
            div.classList.add('system')
            div.innerHTML = `<span class="chat-msg-text">${m.message}</span>`
        } else {
            if (m.username.includes('DEFENDANT')) div.classList.add('defendant')
            if (m.username.includes('JUDGE')) div.classList.add('judge')
            div.innerHTML = `<span class="chat-msg-user">${m.username}:</span><span class="chat-msg-text">${m.message}</span>`
        }
        container.appendChild(div)
        lastMsgId = m.id
    }
    if (msgs.length) container.scrollTop = container.scrollHeight
}

const sendChat = async () => {
    let input = $('#chat-input')
    let msg = input.value.trim()
    if (!msg) return
    input.value = ''
    let r = await fetch('/api/court/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: msg})
    })
    let j = await r.json()
    if (!j.ok) toast(j.error, 'error')
    else fetchMessages()
}

const vote = async (v) => {
    let r = await fetch('/api/court/vote', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({vote: v})
    })
    let j = await r.json()
    if (j.ok) {
        toast(`Voted ${v.toUpperCase()}`)
        fetchState()
    } else {
        toast(j.error, 'error')
    }
}

window.startTrial = async () => {
    let defendant = $('#trial-defendant').value.trim()
    let accusation = $('#trial-accusation').value.trim() || 'unspecified crimes'
    if (!defendant) { toast('Enter defendant', 'error'); return }
    let r = await fetch('/api/admin/court/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({defendant, accusation})
    })
    let j = await r.json()
    if (j.ok) {
        toast('⚖️ Trial started!')
        $('#trial-defendant').value = ''
        $('#trial-accusation').value = ''
        fetchState()
    } else {
        toast(j.error, 'error')
    }
}

window.addAccusation = async () => {
    let accusation = $('#new-accusation').value.trim()
    if (!accusation) { toast('Enter accusation', 'error'); return }
    let r = await fetch('/api/admin/court/accuse', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({accusation})
    })
    let j = await r.json()
    if (j.ok) {
        $('#new-accusation').value = ''
        fetchMessages()
    } else {
        toast(j.error, 'error')
    }
}

window.deliverVerdict = async (verdict) => {
    let punishment = $('#punishment')?.value?.trim() || ''
    if (!confirm(`Deliver ${verdict.toUpperCase()} verdict?`)) return
    let r = await fetch('/api/admin/court/verdict', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({verdict, punishment})
    })
    let j = await r.json()
    if (j.ok) {
        toast('⚖️ ' + j.msg)
        fetchState()
        fetchMessages()
    } else {
        toast(j.error, 'error')
    }
}

window.executeSentence = async () => {
    let sentence = $('#sentencing')?.value || ''
    let custom = $('#punishment')?.value?.trim() || ''
    let punishment = custom || sentence
    if (!punishment) { toast('Select or enter a sentence', 'error'); return }
    if (punishment.includes('PUBLIC HANGING') && !confirm('⚠️ PUBLIC HANGING will PERMANENTLY DELETE their account! Are you sure?')) return
    let r = await fetch('/api/admin/court/sentence', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({sentence: punishment})
    })
    let j = await r.json()
    if (j.ok) {
        toast('⚖️ Sentence executed!')
        $('#sentencing').value = ''
        $('#punishment').value = ''
        fetchState()
        fetchMessages()
    } else {
        toast(j.error, 'error')
    }
}

window.endCourt = async () => {
    if (!confirm('End court session?')) return
    let r = await fetch('/api/admin/court/end', {method: 'POST'})
    let j = await r.json()
    if (j.ok) {
        toast('Court adjourned')
        fetchState()
    } else {
        toast(j.error, 'error')
    }
}

$('#chat-send').addEventListener('click', sendChat)
$('#chat-input').addEventListener('keypress', e => { if (e.key === 'Enter') sendChat() })
$('#vote-guilty').addEventListener('click', () => vote('guilty'))
$('#vote-innocent').addEventListener('click', () => vote('innocent'))

const fetchBal = async () => {
    let r = await fetch('/api/state')
    if (r.ok) {
        let s = await r.json()
        $('#bal').textContent = s.balance.toFixed(2)
    }
}

fetchState()
fetchMessages()
fetchBal()
setInterval(fetchState, 3000)
setInterval(fetchMessages, 1500)
