import discord
import aiohttp
import asyncio

import os
TOKEN = os.environ.get('TOKEN', '')
CHANNEL_ID = 1469472326163632303
CHECK_INTERVAL = 30

client = discord.Client(intents=discord.Intents.default())
last_alerted = set()
last_refresh = 0

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    client.loop.create_task(check_stock())

async def check_stock():
    global last_alerted, last_refresh
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    
    while not client.is_closed():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://lebodasquebodev.pythonanywhere.com/api/public/stock') as r:
                    if r.status == 200:
                        data = await r.json()
                        next_refresh = data.get('next_refresh', 0)
                        if next_refresh != last_refresh:
                            last_alerted = set()
                            last_refresh = next_refresh
                        for shoe in data.get('market', []):
                            key = f"{shoe['id']}_{next_refresh}"
                            if shoe['rarity'] in ['lebos', 'dexies'] and key not in last_alerted:
                                emoji = '👑' if shoe['rarity'] == 'lebos' else '💎'
                                await channel.send(f"{emoji} **{shoe['rarity'].upper()} IN STOCK!** {emoji}\n{shoe['name']} - ${shoe['price']:,.0f} ({shoe['stock']} available)")
                                last_alerted.add(key)
                                print(f"Alerted: {shoe['name']}")
        except Exception as e:
            print(f'Error: {e}')
        
        await asyncio.sleep(CHECK_INTERVAL)

client.run(TOKEN)
