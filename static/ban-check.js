(function(){
    let banOverlay=null
    let banInterval=null
    let banEndTime=0

    function createOverlay(){
        if(banOverlay)return banOverlay
        banOverlay=document.createElement('div')
        banOverlay.id='ban-overlay'
        banOverlay.innerHTML=`
            <div class="ban-overlay-bg"></div>
            <div class="ban-overlay-box">
                <div class="ban-icon">⛔</div>
                <h1 class="ban-title">ACCOUNT SUSPENDED</h1>
                <div class="ban-timer" id="ban-timer"></div>
                <div class="ban-reason" id="ban-reason-text"></div>
                <p class="ban-hint">Your account is temporarily banned. Please wait for the timer to expire.</p>
            </div>
        `
        let style=document.createElement('style')
        style.textContent=`
            #ban-overlay{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center}
            .ban-overlay-bg{position:absolute;inset:0;background:rgba(0,0,0,0.92);backdrop-filter:blur(12px)}
            .ban-overlay-box{position:relative;z-index:1;text-align:center;padding:48px 40px;max-width:500px;width:90%;
                background:linear-gradient(135deg,#1a1a26 0%,#12121a 100%);border:2px solid #ff4466;
                border-radius:16px;box-shadow:0 0 60px rgba(255,68,102,0.3)}
            .ban-icon{font-size:64px;margin-bottom:16px;animation:pulse 2s infinite}
            .ban-title{font-family:'Orbitron',sans-serif;color:#ff4466;font-size:24px;margin-bottom:20px;
                text-transform:uppercase;letter-spacing:3px;text-shadow:0 0 20px rgba(255,68,102,0.5)}
            .ban-timer{font-family:'Orbitron',sans-serif;font-size:42px;color:#fff;margin:16px 0;
                padding:16px 24px;background:rgba(255,68,102,0.1);border-radius:12px;border:1px solid rgba(255,68,102,0.3);
                letter-spacing:4px;text-shadow:0 0 10px rgba(255,68,102,0.4)}
            .ban-reason{color:#ffd700;font-size:16px;margin:16px 0;padding:12px 16px;
                background:rgba(255,215,0,0.08);border-radius:8px;border:1px solid rgba(255,215,0,0.2);
                font-family:'Rajdhani',sans-serif;display:none}
            .ban-reason.show{display:block}
            .ban-hint{color:#9898a8;font-size:13px;margin-top:20px;font-family:'Rajdhani',sans-serif}
            @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
        `
        document.head.appendChild(style)
        document.body.appendChild(banOverlay)
        return banOverlay
    }

    function formatTime(secs){
        if(secs<=0)return '00:00:00'
        let d=Math.floor(secs/86400)
        let h=Math.floor((secs%86400)/3600)
        let m=Math.floor((secs%3600)/60)
        let s=secs%60
        let pad=n=>(n<10?'0':'')+n
        if(d>0)return d+'d '+pad(h)+':'+pad(m)+':'+pad(s)
        return pad(h)+':'+pad(m)+':'+pad(s)
    }

    function updateTimer(){
        let now=Math.floor(Date.now()/1000)
        let remaining=Math.max(0,banEndTime-now)
        let el=document.getElementById('ban-timer')
        if(el)el.textContent=formatTime(remaining)
        if(remaining<=0){
            hideBan()
            checkBan()
        }
    }

    function showBan(data){
        createOverlay()
        banEndTime=Math.floor(Date.now()/1000)+data.remaining
        let reasonEl=document.getElementById('ban-reason-text')
        if(data.reason){
            reasonEl.textContent='Reason: '+data.reason
            reasonEl.classList.add('show')
        }else{
            reasonEl.classList.remove('show')
        }
        updateTimer()
        if(banInterval)clearInterval(banInterval)
        banInterval=setInterval(updateTimer,1000)
        banOverlay.style.display='flex'
    }

    function hideBan(){
        if(banInterval){clearInterval(banInterval);banInterval=null}
        if(banOverlay)banOverlay.style.display='none'
    }

    async function checkBan(){
        try{
            let r=await fetch('/api/ban-status')
            if(!r.ok)return
            let data=await r.json()
            if(data.banned){
                showBan(data)
            }else{
                hideBan()
            }
        }catch(e){}
    }

    // Check immediately on page load, then every 5 seconds
    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',()=>{checkBan()})
    }else{
        checkBan()
    }
    setInterval(checkBan,5000)
})()
