import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';

import type { Browser, Puppeteer } from 'puppeteer';


// @ts-expect-error
await puppeteer.use(StealthPlugin())
    .launch({
        headless: false,
        executablePath: "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    })
    .then(async (browser: Browser) => {
        const page = await browser.newPage()
        await page.goto('https://www.reddit.com/r/PokemonTCG/')

        let searchBarSelector = '[name="q"]'
        console.log("looking for ", searchBarSelector)
        let searchBar = await page.waitForSelector(searchBarSelector)
        console.log("found ", searchBar)
        await page.click(searchBarSelector)
        await page.keyboard.type('destined rivals')

        await page.keyboard.press('Enter')
    })