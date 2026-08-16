import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';

import type { Browser } from 'puppeteer';


// @ts-expect-error
await puppeteer.use(StealthPlugin())
    .launch({
        headless: false,
        executablePath: "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    })
    .then(async (browser: Browser) => {
        const page = await browser.newPage();
        await page.goto('https://www.reddit.com/r/PokemonTCG/');

        let searchBarSelector = '[name="q"]';
        
        await page.waitForSelector(searchBarSelector);
        await page.click(searchBarSelector);
        await page.keyboard.type('destined rivals');
        await page.keyboard.press('Enter');

        await page.waitForNavigation();

        for (let i = 0; i < 3; i++) {
            await page.evaluate(() => {
                window.scrollBy(0, window.innerHeight);
            });

            await new Promise(resolve => setTimeout(resolve, 1500));
        };

        const posts = await page.$$eval(
            'div[data-testid="sdui-post-unit"]',
            elements => elements.map((element) => {
                const postDate = element.querySelector('time')?.getAttribute('datetime');
            
                let postStats = element.querySelector('div[data-testid="search-counter-row"]');
                let postUpvotesSpan = postStats?.querySelectorAll('span')[0];
                let postCommentsSpan = postStats?.querySelectorAll('span')[2];

                const postUpvotes = postUpvotesSpan?.querySelector('faceplate-number')?.getAttribute("number");
                const postComments = postCommentsSpan?.querySelector('faceplate-number')?.getAttribute("number");

                return {
                    postDate,
                    postUpvotes,
                    postComments
                }
            })
        );

        console.log(posts);
    });