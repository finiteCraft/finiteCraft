import random

import nodriver as uc

async def main():
    browser = await uc.start()
    page = await browser.get('https://neal.fun/infinite-craft')
    elements = ["Fire", "Water", "Wind", "Earth", "Mud", "Obsidian", "Diamond", "Gem", "Sand", "Cactus", "Lily", "Tea", "Pepsi", "Mother", "Father", "Love", "Beans", "Angel", "God", "Genius", "Einstein", "School", "Lobster", "Sport", "Basketball"]
    while True:
        await page.evaluate('fetch("https://neal.fun/api/infinite-craft/pair?first='+random.choice(elements)+'&second='+random.choice(elements)+'").then(function(resp) {resp.headers.forEach(function(val, key) { console.log(key + \' -> \' + val); });})')
        input()


if __name__ == '__main__':

    # since asyncio.run never worked (for me)
    uc.loop().run_until_complete(main())