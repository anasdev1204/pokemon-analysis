import fs from "fs/promises";
import path from "path";

import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";

import type { Browser, Page } from "puppeteer";

type PokemonSet = {
    name: string;
    searchName: string;
    series: string;
    releaseDate: string;
};

type RedditPost = {
    title: string;
    upvotes: number;
    comments: number;
    postDate: string | null;
};

type RedditSetData = {
    postCount: number;
    posts: RedditPost[];
};

const SETS_PATH =
    "/Users/anas/Projects/pkmn-analysis/scrap/puppeteer/cache/sets.json";

const OUTPUT_PATH =
    "/Users/anas/Projects/pkmn-analysis/data/reddit-set-posts.json";


async function sleep(ms: number): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, ms));
}

async function loadSets(): Promise<PokemonSet[]> {
    const data = await fs.readFile(
        SETS_PATH,
        "utf8"
    );

    return JSON.parse(data);
}

async function loadExistingResults(): Promise<
    Record<string, RedditSetData>
> {
    try {
        const data = await fs.readFile(
            OUTPUT_PATH,
            "utf8"
        );

        return JSON.parse(data);
    } catch {
        return {};
    }
}


async function saveResults(
    results: Record<string, RedditSetData>
): Promise<void> {

    await fs.mkdir(
        path.dirname(OUTPUT_PATH),
        { recursive: true }
    );

    await fs.writeFile(
        OUTPUT_PATH,
        JSON.stringify(results, null, 2),
        "utf8"
    );
}


async function scrapeRedditPosts(
    page: Page,
    searchName: string
): Promise<RedditSetData> {

    const searchUrl =
        `https://www.reddit.com/r/PokemonTCG/search/?q=${encodeURIComponent(searchName)}&restrict_sr=1&sort=relevance&t=all`;

    console.log(`Navigating to: ${searchUrl}`);

    const response = await page.goto(
        searchUrl,
        {
            waitUntil: "domcontentloaded",
            timeout: 30_000
        }
    );

    if (response) {
        const status = response.status();

        if (status === 429) {
            throw new Error(
                "REDDIT_RATE_LIMITED"
            );
        }

        if (status >= 400) {
            throw new Error(
                `Reddit returned HTTP ${status}`
            );
        }
    }

    await sleep(3000);

    // Detect Reddit challenge / block pages
    const pageText = await page.evaluate(
        () => document.body.innerText
    );

    if (
        pageText.includes("You've been blocked") ||
        pageText.includes("You've been rate limited") ||
        pageText.includes("Verify you're human")
    ) {
        throw new Error(
            "REDDIT_BLOCK_OR_CHALLENGE"
        );
    }

    // Scroll gradually rather than aggressively
    let previousHeight = 0;

    for (let i = 0; i < 10; i++) {

        const currentHeight = await page.evaluate(
            () => document.body.scrollHeight
        );

        if (currentHeight === previousHeight) {
            break;
        }

        previousHeight = currentHeight;

        await page.evaluate(
            () => window.scrollBy(
                0,
                window.innerHeight * 0.8
            )
        );

        // Slow, randomized-ish delay
        await sleep(2500);
    }

    const posts = await page.$$eval(
        'div[data-testid="sdui-post-unit"]',
        elements => {
            return elements
                .map(element => {

                    const postDate =
                        element
                            .querySelector("time")
                            ?.getAttribute("datetime") ?? null;

                    const stats =
                        element.querySelector(
                            'div[data-testid="search-counter-row"]'
                        );

                    const spans =
                        stats?.querySelectorAll("span");

                    const upvotes =
                        spans?.[0]
                            ?.querySelector("faceplate-number")
                            ?.getAttribute("number");

                    const comments =
                        spans?.[2]
                            ?.querySelector("faceplate-number")
                            ?.getAttribute("number");

                    return {
                        upvotes: Number(upvotes ?? 0),
                        comments: Number(comments ?? 0),
                        postDate
                    };
                })
        }
    );

    const postTitle = await page.$$eval(
        "#main-content > div > search-telemetry-tracker", 
        el => el.map((element) => { 
            const postTitle = element.querySelector('a[data-testid="post-title"]')?.getAttribute('aria-label'); 
            return { postTitle } 
        } 
    ));

    const completePosts = posts.map((post, index) => ({
        ...post,
        title: postTitle[index]?.postTitle ?? ""
    }));

    const uniquePosts = Array.from(
        new Map(
            completePosts.map(post => [
                `${post.title}|${post.postDate}`,
                post
            ])
        ).values()
    );

    return {
        postCount: uniquePosts.length,
        posts: uniquePosts
    };
}


async function main(): Promise<void> {
    // @ts-expect-error
    puppeteer.use(StealthPlugin());

    // @ts-expect-error
    const browser: Browser = await puppeteer.launch({
        headless: true,
        executablePath:
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    });

    const page = await browser.newPage();

    await page.setViewport({
        width: 1366,
        height: 900
    });

    const sets = await loadSets();

    const results = await loadExistingResults();

    console.log(
        `Found ${sets.length} Pokémon sets`
    );

    try {

        for (let i = 0; i < sets.length; i++) {

            const set = sets[i];
            
            if (!set) {
                continue;
            }

            console.log(
                `\n[${i + 1}/${sets.length}] ${set.name}`
            );

            if (results[set.name]) {
                console.log(
                    `Using cached Reddit data for ${set.name}`
                );

                continue;
            }

            try {

                const searchName = set.name + " " + (set?.searchName || "");

                const redditData =
                    await scrapeRedditPosts(
                        page,
                        searchName
                    );

                results[set.name] = redditData;

                await saveResults(results);

                console.log(
                    `${set.name}: ${redditData.postCount} posts`
                );

                await sleep(5000);

            } catch (error) {

                console.error(
                    `Failed to scrape ${set.name}:`,
                    error
                );

                /*
                 * Stop rather than hammering Reddit if
                 * we encounter a rate limit or challenge.
                 */
                if (
                    error instanceof Error &&
                    (
                        error.message ===
                            "REDDIT_RATE_LIMITED" ||
                        error.message ===
                            "REDDIT_BLOCK_OR_CHALLENGE"
                    )
                ) {
                    console.error(
                        "Reddit is rate limiting/challenging the scraper. Stopping."
                    );

                    break;
                }
            }
        }

    } finally {

        await browser.close();
    }

    console.log(
        `\nWritten: ${OUTPUT_PATH}`
    );
}


main().catch(console.error);