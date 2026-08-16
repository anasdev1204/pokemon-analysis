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
        // await page.goto('https://trends.google.com/home', {
        //     waitUntil: 'networkidle2'
        // });
        await new Promise(resolve => setTimeout(resolve, 2000));

        // await page.waitForSelector('input', { timeout: 10000 });
    
        // const inputs = await page.$$('input');

        // let searchBarCode = "YPqjbf";

        // const searchBarInput = inputs.find(async (input) => {
        //     const inputId = await input.evaluate((el) => el.getAttribute('jsname'));
        //     return inputId === searchBarCode;
        // });

        // if (!searchBarInput) {
        //     throw new Error('Search bar input not found');
        // }

        // console.log(searchBarInput);

        // const searchBarInput = await page.$('[jsname="YPqjbf"]');
        // console.log(searchBarInput);

        // if (!searchBarInput) {
        //     throw new Error('Search bar input not found');
        // }

        // // await searchBarInput.evaluate(el => el.focus());
        // await searchBarInput.click();
    
        // await page.keyboard.type('destined rivals pokemon');
        // await page.keyboard.press('Enter');

        // await page.waitForNavigation();

        // for (let i = 0; i < 3; i++) {
        //     await page.evaluate(() => {
        //         window.scrollBy(0, window.innerHeight);
        //     });

        //     await new Promise(resolve => setTimeout(resolve, 1500));
        // };

        // const posts = await page.$$eval(
        //     'div[data-testid="sdui-post-unit"]',
        //     elements => elements.map((element) => {
        //         const postDate = element.querySelector('time')?.getAttribute('datetime');
            
        //         let postStats = element.querySelector('div[data-testid="search-counter-row"]');
        //         let postUpvotesSpan = postStats?.querySelectorAll('span')[0];
        //         let postCommentsSpan = postStats?.querySelectorAll('span')[2];

        //         const postUpvotes = postUpvotesSpan?.querySelector('faceplate-number')?.getAttribute("number");
        //         const postComments = postCommentsSpan?.querySelector('faceplate-number')?.getAttribute("number");

        //         return {
        //             postDate,
        //             postUpvotes,
        //             postComments
        //         }
        //     })
        // );

        // console.log(posts);

        function createTrendsUrl(terms: string[], date = "today 1-m") {
            const params = new URLSearchParams({
                date,
                q: terms.join(",")
            });

            return `https://trends.google.com/trends/explore?${params}`;
        }

        const url = createTrendsUrl([
            "destined rivals pokemon",
            "pitch black pokemon"
        ]);

        await page.goto(url, {
            waitUntil: "networkidle2"
        });

        await new Promise(resolve => setTimeout(resolve, 2000));

        await page.reload()
    });