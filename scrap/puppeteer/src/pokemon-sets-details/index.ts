// Get sets and their release dates from https://www.pokemon.com/us/pokemon-tcg/trading-card-expansions

// Get sets booster prices from https://www.pokemonpricetracker.com/sealed-products

// Get pull rates and concerned rarities for available sets on https://www.pullrates.gg/sets

// Get set cards (names, number, image) by rarity (make sure to include rainbows as it is not included in the rarity list and make) from  https://www.tcgcollector.com/sets/intl?cardCountMode=anyCardVariant&releaseDateOrder=newToOld&displayAs=images

// Get chase cards of each set from https://www.pittpokeresearch.com/chase-cards

// Get pokemon popularity from the poll at https://thomasgamedocs.com/pokemon/

// Get each card's price evolution depedning on the quarters and ebay sold listings from https://www.pokemonpricetracker.com/pokemon-prices  

// Final format should be something like this: 
// "destined-rivals": {
//    "name": "Destined Rivals",
//      "Series": "Scarlet & Violet",
//    "number": "03",
//     "releaseDate": "2024-02-23",
//     "boosterPrice": 4.99, 
//      "numberOfChases": 1,
//     "chaseRatioOutOfHits": 0.05,
//      "numberOfHits": 20,
//     "numberOfCards": 200,
//    "hitsRarities": [
//        {
//           "rarity": "Rare Holo",
//            "pullRate": 0.25,
//            "numberOfCards": 20,
//            "specificCardPullRate": 0.001
//            "costPerPull": 19.96
//            "concernedCards": [
//                {
//                    "name": "Charizard",
//                    "number": "03/25",
//                    "image": "https://images.pokemontcg.io/swsh12/3_hires.png",
//                      "isChase": false,
//                      "isPokemon": true,
//                    "pokemonPopularity": 0.9, If energy card set to 0.05 and if trainer card set to 0.2, else set to 0  
//                    "priceOnRelease": 4.99,
//                    "priceEvolution": [
//                    5.99, 6.99, 7.99, 8.99, 9.99
//                     ],
//                   "ebaySoldVolumeFrom2026": 76
//                }
//      ]

import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";
import type { Browser, ElementHandle, Page } from "puppeteer";
import fs from "node:fs/promises";
import path from "node:path";
import readline from "readline/promises";
import { stdin as input, stdout as output } from "process";

interface PokemonSet {
    name: string;
    series: string;
    number: string;
    releaseDate: string;

    boosterPrice: number;

    numberOfChases: number;
    numberOfHits: number;

    chaseRatioOutOfHits: number;

    numberOfCards: number;

    hitsRarities: HitRarity[];
}

interface HitRarity {
    rarity: string;
    pullRate: number;
    numberOfCards: number;
    specificCardPullRate: number;
    costPerPull: number;

    concernedCards: CardData[];
}

interface CardData {
    name: string;
    number: string;
    image: string;

    isChase: boolean;
    isPromo: boolean;
    isPokemon: boolean;

    pokemonPopularity: number;

    priceOnRelease?: number;

    priceEvolution: number[];

    ebaySoldVolumeFrom2026?: number;
}

interface RawSet {
    name: string;
    searchName?: string;
    series: string;
    releaseDate: string;
}

interface RawBoosterPrice {
    setName: string;
    price: number;
}

interface RawPullRate {
    setName: string;
    rarity: string;
    pullRate: number;
    cards: number;
}

interface RawCard {
    setName: string;
    name: string;
    number: string;
    isPokemon: boolean;
    isPromo: boolean;
    image: string;
    rarity: string;
}

interface RawChaseCard {
    setName: string;
    name: string;
    number: string;
}

interface RawPokemonPopularity extends Record<string, number> {}

class PokemonSetDetailsScraper {

    private browser!: Browser;
    
    private readonly headless = true;
    private readonly outputDirectory: string;
    private readonly cacheDirectory = "./cache";

    private readonly urls = {
        pokemonSets:
            "https://www.pokemon.com/us/pokemon-tcg/trading-card-expansions",

        boosterPrices:
            "https://www.pokemonpricetracker.com/sealed-products",

        pullRates:
            "https://www.pullrates.gg/sets",

        cards:
            "https://www.tcgcollector.com/sets/intl?cardCountMode=anyCardVariant&releaseDateOrder=newToOld&displayAs=images",

        chaseCards:
            "https://www.pittpokeresearch.com/chase-cards",

        pokemonPopularity:
            "https://thomasgamedocs.com/pokemon/",

        priceHistory:
            "https://www.pokemonpricetracker.com/pokemon-prices",
    };

    private readonly numberOfScrapedSets = 39;

    sets: RawSet[] = [];
    boosterPrices: RawBoosterPrice[] = [];
    pullRates :RawPullRate[] = [];
    pokemonPopularity: RawPokemonPopularity = {};
    cards: RawCard[] = [];
    chaseCards: RawChaseCard[] = [];

    setsAPIDone: Set<string> = new Set();
    priceAPIUrls: Record<string, string> = {};

    constructor(outputDirectory: string) {
        this.outputDirectory = outputDirectory;
    }

    private async initBrowser(): Promise<void> {

        // @ts-expect-error puppeteer-extra typings
        puppeteer.use(StealthPlugin());

        // @ts-expect-error puppeteer-extra typings
        this.browser = await puppeteer.launch({
            headless: this.headless,

            executablePath:
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",

            args: [
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        });
    }

    private async restartBrowser(): Promise<void> {
        console.log("Restarting browser...");

        try {
            if (this.browser?.connected) {
                await this.browser.close();
            }
        } catch {
            // Browser is already disconnected.
        }

        await this.initBrowser();
    }

    /** 
     * Testing methods
    */
    private async loadOrScrape<T>(
        filename: string,
        scrapeFunction: () => Promise<T>
    ): Promise<T> {

        await fs.mkdir(this.cacheDirectory, {
            recursive: true
        });

        const filePath = path.join(
            this.cacheDirectory,
            filename
        );

        // Check if cached file exists
        try {
            const data = await fs.readFile(
                filePath,
                "utf8"
            );

            console.log(`Loading cached data: ${filename}`);

            return JSON.parse(data) as T;

        } catch (error: any) {

            // File doesn't exist → scrape
            if (error.code !== "ENOENT") {
                throw error;
            }
        }

        console.log(`Scraping: ${filename}`);

        const result = await this.retry(scrapeFunction, 5);

        await fs.writeFile(
            filePath,
            JSON.stringify(result, null, 2),
            "utf8"
        );

        console.log(`Saved: ${filePath}`);

        return result;
    }

    public async test(): Promise<void> {
        await this.initBrowser();

        try {
            this.sets = await this.loadOrScrape(
                "sets.json",
                () => this.scrapePokemonSets()
            );

            const manualSets = await fs.readFile(
                "cache/manual-sets.json",
                "utf8"
            );

            this.sets = this.sets.concat(
                JSON.parse(manualSets) as RawSet[]
            );

            this.boosterPrices = await this.loadOrScrape(
                "booster-prices.json",
                () => this.scrapeBoosterPrices()
            );

            this.pullRates = await this.loadOrScrape(
                "pull-rates.json",
                () => this.scrapePullRates()
            );

            const manualPullRates = await fs.readFile(
                "cache/manual-pull-rates.json",
                "utf8"
            );

            this.pullRates = this.pullRates.concat(
                JSON.parse(manualPullRates) as RawPullRate[]
            );

            this.pokemonPopularity = await this.loadOrScrape(
                "pokemon-popularity.json",
                () => this.scrapePokemonPopularity()
            );

            this.cards = await this.loadOrScrape(
                "cards.json",
                () => this.scrapeSetCards()
            );

            this.chaseCards = await this.loadOrScrape(
                "chase-cards.json",
                () => this.scrapeChaseCards()
            )

            this.priceAPIUrls = await this.loadOrScrape(
                "api-urls.json",
                () => this.scrapePriceHistoryAPIUrls()
            )

            // console.log("Sets:", this.sets);
            // console.log("Booster prices:", this.boosterPrices);
            // console.log("Pull rates:", this.pullRates);
            // console.log("Pokemon popularity:", this.pokemonPopularity);
            // console.log("Cards:", this.cards);

            // CURRENTLY TESTING
            // const res = await this.mergeData();

            const result = await this.createAccountInPriceTracker();
            console.log(result);
        } finally {
            // await this.browser.close();
        }
    }

    /**
     * Main entry point.
     */
    public async scrape(): Promise<Record<string, PokemonSet>> {

        await this.initBrowser();

        try {
            const page = await this.newPage();

            const response = await page.goto("https://api.ipify.org?format=json");
            
            const data = await response?.json() as { ip: string };

            console.log(data.ip);

            this.sets = await this.loadOrScrape(
                "sets.json",
                () => this.scrapePokemonSets()
            );

            this.boosterPrices = await this.loadOrScrape(
                "booster-prices.json",
                () => this.scrapeBoosterPrices()
            );

            this.pullRates = await this.loadOrScrape(
                "pull-rates.json",
                () => this.scrapePullRates()
            );

            const manualPullRates = await fs.readFile(
                "cache/manual-pull-rates.json",
                "utf8"
            );

            this.pullRates = this.pullRates.concat(
                JSON.parse(manualPullRates) as RawPullRate[]
            );

            this.pokemonPopularity = await this.loadOrScrape(
                "pokemon-popularity.json",
                () => this.scrapePokemonPopularity()
            );

            this.cards = await this.loadOrScrape(
                "cards.json",
                () => this.scrapeSetCards()
            );

            this.chaseCards = await this.loadOrScrape(
                "chase-cards.json",
                () => this.scrapeChaseCards()
            )

            this.priceAPIUrls = await this.loadOrScrape(
                "api-urls.json",
                () => this.scrapePriceHistoryAPIUrls()
            )

            const result = await this.mergeData();
            return result;
        } finally {
            await this.browser.close();
        }
    }

    // Need manually adding set codes to the first sets of each seris to not conflict with promos
    private async scrapePokemonSets(): Promise<RawSet[]> {

        const page = await this.newPage();

        try {

            await this.navigate(
                page,
                this.urls.pokemonSets
            );
            const targetCount = this.numberOfScrapedSets;

            let currentCount = await page.$$eval(
                ".releases ul li",
                elements => elements.length
            );

            console.log(`Initially loaded: ${currentCount} sets`);

            const loadMoreButton =
                await page.$(".releases #loadMore");

            if (loadMoreButton) {

                console.log("Clicking Load More...");

                await loadMoreButton.click();

                await page.waitForFunction(
                    previousCount => {
                        return document.querySelectorAll(
                            ".releases ul li"
                        ).length > previousCount;
                    },
                    {
                        timeout: 10_000
                    },
                    currentCount
                );
            }

            let unchangedAttempts = 0;

            while (true) {

                currentCount = await page.$$eval(
                    ".releases ul li",
                    elements => elements.length
                );

                console.log(`Loaded: ${currentCount} sets`);

                if (currentCount >= targetCount) {
                    break;
                }

                const oldCount = currentCount;

                await page.evaluate(async () => {

                    const distance = 800;
                    const delay = 100;

                    while (
                        window.innerHeight +
                        window.scrollY <
                        document.body.scrollHeight
                    ) {
                        window.scrollBy(0, distance);

                        await new Promise(resolve =>
                            setTimeout(resolve, delay)
                        );
                    }
                });

                try {

                    await page.waitForFunction(
                        previousCount => {
                            return document.querySelectorAll(
                                ".releases ul li"
                            ).length > previousCount;
                        },
                        {
                            timeout: 5_000
                        },
                        oldCount
                    );

                    unchangedAttempts = 0;

                } catch {

                    unchangedAttempts++;

                    console.log(
                        `No new sets loaded (${unchangedAttempts}/3)`
                    );

                    if (unchangedAttempts >= 3) {
                        console.log(
                            "No more sets appear to be loading."
                        );
                        break;
                    }
                }
            }

            const setElements = await page.$$(".releases ul li");
            setElements.reverse();
            
            const sets: RawSet[] = [];
            
            for (let set of setElements) {
                const metadata = await set.$$eval("span", elements => elements.map(el => el.textContent?.trim()));

                const series = metadata[1] ?? undefined;

                if (series == "Sun & Moon Series") {
                    continue;
                }

                const releaseDate = metadata[2] ?? undefined;

                const name = await set.$eval("h2", el => {
                    
                    if (!el.textContent) {
                        throw new Error("Set title not found");
                    }

                    let trimmedTitle = el.textContent.trim();
                    trimmedTitle = trimmedTitle.replace("é", "e");
                    trimmedTitle = trimmedTitle.replace("’", "'");

                    return trimmedTitle.includes("—") ? trimmedTitle.split("—")[1] : trimmedTitle;
                });
                
                sets.push({
                    name,
                    series,
                    releaseDate
                } as RawSet)
            };

            return sets;
        } finally {
            await this.safeClosePage(page);
        }
    }

    private async scrapeBoosterPrices(): Promise<RawBoosterPrice[]> {

        let page = await this.newPage();

        try {
            await this.navigate(
                page,
                this.urls.boosterPrices
            );

            const results: RawBoosterPrice[] = [];

            for (const selectedSet of this.sets) {
                const setDropdownButton = await page.$(
                    'button[role="combobox"]'
                );
                if (setDropdownButton) {
                    await setDropdownButton.click();
                };

                console.log("Set dropdown clicked");

                if (!this.sets || this.sets.length === 0) {
                    throw new Error("Sets not loaded. Please run scrapePokemonSets() first.");
                };
                
                const setOptions = await page.$$('div[role="listbox"] > button');
                console.log("Set options loaded");
                
                let optionFound = false;
                for (const option of setOptions) {
                    const setName = await option.evaluate(el => el.textContent?.trim().toLowerCase() ?? "");

                    const searchName = selectedSet.searchName ? selectedSet.searchName.toLowerCase() : selectedSet.name.toLowerCase();

                    if (setName.includes(searchName)) {
                        console.log("Selecting set:", setName);
                        optionFound = true;
                        await option.click();
                        break;
                    }
                };

                if (!optionFound) {
                    continue;
                }

                await page.waitForNavigation({ waitUntil: "domcontentloaded" });

                const switchDisplayButton = await page.$(
                    'div[role="tablist"] > button:nth-of-type(2)'
                );
                if (switchDisplayButton) {
                    await switchDisplayButton.click();
                };

                console.log("Display switched");

                let productOptions = await page.$$('table > tbody > tr');
                let nextPageButton = await page.$('a[aria-label="Next page"]');
                console.log(nextPageButton ? "Next page button found" : "Next page button not found");
                while (nextPageButton) {
                    await nextPageButton.click();
                    await page.waitForNavigation({ waitUntil: "domcontentloaded" });
                    let tempProductOptions = await page.$$('table > tbody > tr');
                    productOptions = productOptions.concat(tempProductOptions);
                    nextPageButton = await page.$('a[aria-label="Next page"]');
                };

                console.log("Product options loaded:", productOptions.length);
                productOptions.reverse();
                
                for (const product of productOptions) {
                    const productData = await product.$$eval('td', elements => elements.map(el => el.textContent?.trim() ?? ""));

                    const productName = productData[0] ?? "";
                    const productPriceText = productData[3] ?? "";

                    if (productName.toLowerCase().includes("booster pack")) {
                        console.log("Found booster pack:", productName, "Price text:", productPriceText);
                        const priceMatch = productPriceText.match(/\$([\d,.]+)/);
                        if (priceMatch && priceMatch[1]) {
                            const price = parseFloat(priceMatch[1].replace(/,/g, ''));
                            results.push({
                                setName: selectedSet.name,
                                price
                            } as RawBoosterPrice);
                            break;
                        }
                    }
                };

                await this.safeClosePage(page);

                await this.sleep(1000);
                page = await this.newPage();
                await this.navigate(
                    page,
                    this.urls.boosterPrices
                );
            };

            console.log("Results:", results);
            return results;
        } finally {
            await this.safeClosePage(page);
        }
    }

    // NEEDED TO ADD MANUALLY A COUPLE SETS AND PROMOS PULL RATES AS THEY ARE NOT AVAILABLE ON THE WEBSITE
    private async scrapePullRates(): Promise<RawPullRate[]> {

        const page = await this.newPage();

        try {

            await this.navigate(
                page,
                this.urls.pullRates
            );

            const setUrls: { name: string; url: string }[] = [];

            const allSetsAnchors = await page.$$(
                'main > div > div > a'
            );

            for (const anchor of allSetsAnchors) {
                const setName = await anchor.evaluate(
                    el => el.querySelector("h2")?.textContent?.trim() ?? ""
                );

                const setUrl = await anchor.evaluate(
                    el => (el as HTMLAnchorElement).href
                );

                if (setName && setUrl) {
                    setUrls.push({
                        name: setName,
                        url: setUrl
                    });
                }
            };

            console.log(setUrls);

            const results: RawPullRate[] = [];

            for (const set of setUrls) {

                await this.navigate(page, set.url);

                const pullRates = await page.$$("main > div > div > section:nth-of-type(3) > div:nth-of-type(2) > div");

                for (const rate of pullRates) {
                    const rarity: string = await rate.$eval(
                        "span",
                        el => el.title?.trim() ?? ""
                    );
                    const rarityCode: string = await rate.$eval(
                        "span",
                        el => el.textContent?.trim() ?? ""
                    );

                    const pullRate: string = await rate.$eval(
                        "p",
                        el => el.textContent?.trim().split(":")[1]?.trim() ?? ""
                    );

                    const intPullRate = parseInt(pullRate);

                    if (intPullRate >= 6) {
                        results.push({
                            rarity,
                            pullRate: intPullRate,
                            setName: set.name,
                            cards: 0
                        });
                    } else {
                        console.log("Skipping rarity with pull rate less than 6:", rarity, "Pull rate:", intPullRate, "In set:", set.name);
                    }
                };
            }

            return results;

        } finally {
            await this.safeClosePage(page);
        }
    }

    private async scrapeSetCards(): Promise<RawCard[]> {

        let page = await this.newPage();
        try {
            const results: RawCard[] = [];

            await this.navigate(
                page,
                this.urls.cards
            );

            const megaEvolutionCards = await page.$$("#mega-evolution-series > div > div");

            const scarletVioletCards = await page.$$("#scarlet-and-violet-series > div > div");

            const swordShieldCards = await page.$$("#sword-and-shield-series > div > div");

            const allSetCards = [
                ...megaEvolutionCards,
                ...scarletVioletCards,
                ...swordShieldCards
            ];

            const anchors = [];
            const titles: string[] = [];
            const seenTitles = new Set<string>();
            for (const setCard of allSetCards) {
                const anchor = await setCard.$("a");
                let title = await anchor?.evaluate(el => el.getAttribute("title"));
                title = title?.replace("é", "e").replace("’", "'") ?? "";
                title = title.toLowerCase();
                const numberMatch = title.match(/\d+/);

                if (numberMatch) {
                    title = numberMatch[0];
                }

                console.log("Card title:", title);

                const matchingSetName = this.sets.find(set => title.includes(set.name.toLowerCase()));
                if (matchingSetName) {
                    console.log(title, matchingSetName.name, seenTitles.has(matchingSetName.name));
                }

                if (
                    title 
                    && matchingSetName 
                    && (!seenTitles.has(matchingSetName.name) || title.includes("promos"))) {
                    anchors.push(anchor);
                    titles.push(matchingSetName.name);
                    seenTitles.add(matchingSetName.name);
                    continue;
                }
                
                console.log("Skipping card with title:", title);
            };

            console.log(anchors.length);

            const setsAnchorsTitles = await Promise.all(
                anchors.map(async anchor => {

                    const href = await anchor?.evaluate(
                        el => (el as HTMLAnchorElement).href
                    ) ?? "";

                    const title = await anchor?.evaluate(
                        el => el.getAttribute("title")?.trim() ?? ""
                    ) ?? "";

                    return {
                        href,
                        title
                    };
                })
            );
            
            for (let x = 0; x < setsAnchorsTitles.length; x++) {
                page = await this.newPage();
                const { href, title: currentTitle } = setsAnchorsTitles[x] as { href: string; title: string };

                console.log("Navigating to card details page:", href);
                await this.navigate(page, href);

                let setRaritiesPullRate: RawPullRate[] = [];

                if (currentTitle.toLowerCase().includes("promos")) {
                    console.log("Filtering pull rates for promos set:", currentTitle);
                    console.log("Current title split:", currentTitle.split("Promos")[0]);
                    setRaritiesPullRate = this.pullRates.filter(pr => pr.setName == currentTitle.split("Promos")[0]?.trim() && pr.rarity.toLowerCase().includes("promo"));
                } else {
                    setRaritiesPullRate = this.pullRates.filter((pr) => pr.setName == currentTitle && !pr.rarity.toLowerCase().includes("promo"));
                }

                const filterButton = await page.$("#show-card-filters-drawer-button");
                console.log("Clicking filter button to show rarity drawer", filterButton );
                await filterButton?.click();

                await new Promise(resolve =>
                    setTimeout(resolve, 500)
                );

                const rarityDrawer = await page.$("#card-filters-drawer > div:nth-of-type(2) > div > div > div:nth-of-type(3) > div:nth-of-type(2) > div:nth-of-type(3)");
                console.log("Clicking rarity drawer to show all rarities", rarityDrawer);

                await rarityDrawer?.click();

                await new Promise(resolve =>
                    setTimeout(resolve, 500)
                );

                const raritiesCheckboxes = await page.$$("#card-rarity-checkbox-containers > div");

                console.log("Found rarity checkboxes:", raritiesCheckboxes.length);

                const rarityCheckboxesInput: Record<string, string> = {};
                let containsRainbow = false;
                for (const rarityCheckbox of raritiesCheckboxes) {
                    const rarityLabel = (await rarityCheckbox.$eval("label", el => el.textContent?.trim().replace("Rare", "") ?? "")).trim();
                    const rarityInput = await rarityCheckbox.$eval(
                        'input[type="checkbox"][name="rarities"]',
                        el => el.getAttribute("value")
                    );
                    if (!rarityInput) {
                        console.log("no rarity input found");
                        continue;
                    };
                    if (rarityLabel.includes("Rainbow")) {
                        containsRainbow = true;
                    };
                    rarityCheckboxesInput[rarityLabel] = rarityInput;
                };

                console.log(rarityCheckboxesInput);
                console.log(setRaritiesPullRate);         

                for (const rarityPullRate of setRaritiesPullRate) {
                    const rarityNameWithoutRare = rarityPullRate.rarity.replace("Rare", "").trim();

                    let rainbowRarityCode: string | undefined = undefined;
                    if (rarityNameWithoutRare.toLowerCase() == "secret" && containsRainbow) {
                        console.log("Adding Rainbow rarity code for Secret rarity");
                        rainbowRarityCode = rarityCheckboxesInput["Rainbow"];
                    };

                    const rarityCode = rarityCheckboxesInput[rarityNameWithoutRare];

                    if (!rarityCode) {
                        continue;
                    }

                    const link = `${href}&rarities=${rarityCode}${rainbowRarityCode ? `,${rainbowRarityCode}` : ""}`
                    await this.navigate(page, link);

                    await this.sleep(500);

                    console.log("Navigated to filtered card details page for set:", currentTitle, "with rarity:", rarityPullRate.rarity, "and code:", rarityCode);
                    const cardGrid = await page.$("#card-image-grid");
                    console.log("Card grid found:", cardGrid);
                    const cardGridContent = await page.$$("#card-image-grid > div");
                    console.log("Found cards in grid:", cardGridContent.length);
                    for (const card of cardGridContent) {
                        const cardDetailedName = await card.$eval("a", 
                            el => el.getAttribute("title")?.trim() ?? ""
                        );

                        const pokemonName = cardDetailedName.split("(")[0]?.trim() ?? "";
                        const cardNumber = cardDetailedName.split("(")[1]?.replace(/\D/g, "").trim().slice(0, 3) ?? "";

                        const cardImage = await card.$eval("a > img", el => (el as HTMLImageElement).src ?? "");

                        console.log("Card detailed name:", cardDetailedName, "Pokemon name:", pokemonName, "Card number:", cardNumber);

                        let isPokemon = false;
                        let i = 0;
                        const splitPokemonName = pokemonName.split(" ");

                        for (let start = 0; start < splitPokemonName.length; start++) {
                            let current = "";

                            for (let end = start; end < splitPokemonName.length; end++) {

                                current +=
                                    (current ? " " : "") +
                                    splitPokemonName[end];

                                if (
                                    this.pokemonPopularity[current] !== undefined
                                ) {
                                    isPokemon = true;
                                    break;
                                }
                            }

                            if (isPokemon) {
                                break;
                            }
                        }


                        const finalCard: RawCard = {
                            setName: currentTitle ?? "",
                            rarity: rarityPullRate.rarity,
                            name: pokemonName,
                            number: cardNumber,
                            image: cardImage,
                            isPromo: currentTitle.toLowerCase().includes("promo"),
                            isPokemon
                        };

                        results.push(finalCard);
                    };   
                }

                await this.sleep(
                    2000 + Math.random() * 3000
                );

                if ((x + 1) % 10 === 0) {

                    console.log(
                        "Restarting page..."
                    );

                    await this.safeClosePage(page);

                    page = await this.newPage();
                }
            }

            return results;
        } catch(error) {
            if (!this.browser.connected) {
                await this.restartBrowser();
            }
            throw error;
        } finally {
            await this.safeClosePage(page);
        }
    }

    // NEED TO ADD THE CARD NUMBER FOR GIRATINA V AND GOLD ENERGY
    private async scrapeChaseCards(): Promise<RawChaseCard[]> {

        const FORCEINCLUDE = ["Champions Path", "Sword & Shield Base"]

        const page = await this.newPage();
        const results: RawChaseCard[] = [];

        try {

            await this.navigate(
                page,
                this.urls.chaseCards
            );

            const priceTable = await page.$("body > main > div:nth-child(2) > div");

            const setTitles = await priceTable?.$$eval("h2", elements => elements.map(el => el.textContent?.trim() ?? "")) ?? [];
            const setTables = await priceTable?.$$("table") ?? [];

            const zipped = setTitles.map((title, index) => ({
                title,
                table: setTables[index]
            }))

            for (const { title, table } of zipped) {
                const isPromos = title.toLowerCase().includes("promo");
                let setTitle = isPromos ? title.split("Black Star Promos")[0]?.trim() : title;

                if (!setTitle || (!FORCEINCLUDE.includes(setTitle) && !this.sets.some(set => set.name === setTitle))) {
                    console.log("Skipping set not found in scraped sets:", setTitle);
                    continue;
                }

               setTitle = setTitle?.replace("Base", "");

                const tableData = await table?.$$eval("tr", rows =>
                    rows.map(row =>
                        Array.from(row.querySelectorAll("th, td"))
                            .map(cell => cell.textContent?.trim() ?? "")
                    )
                );

                for (const row of tableData ?? []) {
                    const cardNameAndNumber = row[0]?.trim() ?? "";
                    if (cardNameAndNumber == "Name") {
                        continue;
                    }

                    let cardName = ""
                    if (cardNameAndNumber.includes("-")) {
                        cardName = cardNameAndNumber.split("-")[0]?.trim() ?? ""
                    } else if (cardNameAndNumber.includes("(")) {
                        cardName = cardNameAndNumber.split("(")[0]?.trim() ?? ""
                    }
                    
                    const cardNumber = cardNameAndNumber.replace(/\D/g, "").trim().slice(0, 3) ?? "";

                    const finalChaseCard: RawChaseCard = {
                        setName: isPromos ? setTitle + " Promos" : setTitle,
                        name: cardName,
                        number: cardNumber
                    }

                    results.push(finalChaseCard);
                }
            }

            return results;
        } finally {
            await this.safeClosePage(page);
        }
    }

    private async scrapePokemonPopularity(): Promise<
        RawPokemonPopularity
    > {

        const page = await this.newPage();

        try {

            await this.navigate(
                page,
                this.urls.pokemonPopularity
            );

            return await page.evaluate(() => {
                const results: RawPokemonPopularity = {};
                
                document
                    .querySelectorAll("tr")
                    .forEach(row => {
                        const cells =
                            Array.from(row.querySelectorAll("td"));

                        if (cells.length < 3) {
                            return;
                        }

                        const pokemon =
                            cells[1]?.textContent?.trim();

                        if (pokemon == "Name") {
                            return;
                        }

                        const percentage =
                            cells[2]?.textContent?.trim();

                        if (!pokemon || !percentage) {
                            return;
                        }   

                        const popularity =
                            parseFloat(
                                percentage.replace("%", "")
                            ) / 100;

                        if (!Number.isNaN(popularity)) {
                            results[pokemon] = popularity;
                        }
                    });

                return results;
            });
        } finally {
            await this.safeClosePage(page);
        }
    }

    private async scrapePriceHistoryAPIUrls(): Promise<Record<string, string>> {
        let page = await this.newPage();
        const urls: Record<string, string> = {};

        const parseTCGPlayerCode = (url: string) => {
            return url.split("/")[4]?.split("_")[0];
        };

        const buildAPIUrl = (tcgplayerCode: string) => {
            return `https://www.pokemonpricetracker.com/api/v2/internal/card-history?cardId=${tcgplayerCode}&days=999&language=english`;
        };

        try {

            for (const selectedSet of this.sets) {
                let setTotalCards = 0;

                page = await this.newPage();

                if (this.setsAPIDone.has(selectedSet.name)) {
                    console.log("Skipping", selectedSet.name, "already done");
                    continue;
                }

                console.log("\n================================");
                console.log("Processing set:", selectedSet.name);
                console.log("================================");

                try {

                    await this.navigate(
                        page,
                        this.urls.priceHistory
                    );

                    await this.sleep(1000 + Math.random() * 1000);

                    const setDropdownButton = await page.$(
                        'button[role="combobox"]'
                    );

                    if (!setDropdownButton) {
                        throw new Error("Set dropdown not found");
                    }

                    await setDropdownButton.click();

                    await page.waitForSelector(
                        'div[role="listbox"] > button'
                    );

                    const setOptions = await page.$$(
                        'div[role="listbox"] > button'
                    );

                    const searchName = (
                        selectedSet.searchName ?? selectedSet.name
                    ).toLowerCase();

                    let foundSet = false;

                    for (const option of setOptions) {

                        const setName = await option.evaluate(
                            el =>
                                el.textContent
                                    ?.trim()
                                    .toLowerCase() ?? ""
                        );

                        if (setName.includes(searchName)) {

                            console.log("Selecting set:", setName);

                            await option.click();

                            foundSet = true;
                            break;
                        }
                    }

                    if (!foundSet) {
                        console.log(
                            "Could not find set:",
                            selectedSet.name
                        );

                        continue;
                    }

                    await page.waitForNavigation({
                        waitUntil: "domcontentloaded",
                        timeout: 30000
                    }).catch(() => {
                        console.log("Navigation event not detected");
                    });

                    await this.sleep(
                        1000 + Math.random() * 1000
                    );

                    console.log(
                        "Loaded price history for:",
                        selectedSet.name
                    );

                    while (true) {
                        // Extract everything inside the browser at once.
                        const container = await page.$('[id$="-content-grid"] > div > div');

                        if (!container) {
                            throw new Error("No container");
                        }

                        const images = await container.$$eval(
                            "img",
                            imgs => imgs
                                .map(img => ({
                                    src: (img as HTMLImageElement).src,
                                    label: (img as HTMLImageElement).alt,
                                }))
                                .filter(img => img.src.includes("tcgplayer-cdn"))
                        );
                        
                        // console.log(images);
                        let urlsAdded = 0;

                        for (const { src: imageUrl, label: imageLabel} of images) {

                            const cardTCGPlayerCode =
                                parseTCGPlayerCode(imageUrl);

                            if (!cardTCGPlayerCode) {
                                continue;
                            }

                            const cardNumber = imageLabel?.split("#")[1]?.slice(0, 3);

                            if (!isNaN(parseInt(cardNumber || ""))) {
                                setTotalCards += 1;
                                console.log("Card number", cardNumber, "added to set", selectedSet.name, "from original data", imageLabel);

                                urls[`${selectedSet.name}/${cardNumber}`] = buildAPIUrl(cardTCGPlayerCode);
                                
                                urlsAdded += 1
                            }
                        }

                        console.log("added urls", urlsAdded);
                        // Find next page directly.
                        const nextButton = await page.$(
                            'a[aria-label="Next page"]'
                        );

                        if (!nextButton) {
                            console.log("Last page");
                            break;
                        }

                        const nextButtonHref =
                            await nextButton.evaluate(
                                el =>
                                    el.getAttribute("href") ?? ""
                            );

                        if (!nextButtonHref) {
                            console.log(
                                "Next page has no href"
                            );
                            break;
                        }

                        const nextUrl = new URL(
                            nextButtonHref,
                            page.url()
                        ).href;


                        await this.sleep(
                            2000 + Math.random() * 3000
                        );

                        await page.goto(nextUrl, {
                            waitUntil: "domcontentloaded",
                            timeout: 30000
                        });

                        await page.waitForSelector(
                            '[id$="-content-grid"]',
                            { timeout: 15000 }
                        );
                    }

                    this.setsAPIDone.add(
                        selectedSet.name
                    );

                    console.log(setTotalCards);

                    await this.safeClosePage(page);

                    await this.sleep(
                        3000 + Math.random() * 4000
                    );

                } catch (error) {

                    console.error(
                        `Error scraping ${selectedSet.name}:`,
                        error
                    );

                    // Continue with the next set instead of
                    // killing the entire scraper.
                    continue;
                }
            }

            return urls;

        } finally {

            await this.safeClosePage(page);

        }
    }

    private async signInToPriceTracker(email: string, pw: string): Promise<Page> {
        try {
            const page = await this.newPage();

            await this.navigate(
                page,
                "https://www.pokemonpricetracker.com/sign-in"
            );

            await page.waitForSelector('#identifier-field', {
                timeout: 30000
            });

            await page.type(
                '#identifier-field',
                email
            );

            await page.waitForSelector("#identifier-field");

            await page.type(
                '#password-field',
                pw
            )

            await page.click('#main-content > div > div > div > div.cl-card.cl-signIn-start.🔒️.cl-internal-d5pd3d > div.cl-main.🔒️.cl-internal-vvtys3 > form > div.cl-internal-1pnppin > button');

            // await page.waitForSelector('input[autocomplete="one-time-code"]', {
            //     timeout: 30000
            // });

            // const rl = readline.createInterface({ input, output });

            // const code = await rl.question(
            //     "Enter the verification code sent to your email: "
            // );

            // rl.close();

            // await page.type(
            //     'input[autocomplete="one-time-code"]',
            //     code.trim()
            // );

            await page.waitForNavigation({
                waitUntil: "networkidle2"
            });

            console.log("Successfully signed in to Pokemon Price Tracker");

            return page;
        } catch (error) {
            console.log(error)
            throw error;
        }
    };

    private async scrapeCardPriceData(page: Page, apiUrl: string): Promise<{
        priceOnRelease: number;
        priceEvolution: number[];
        ebaySoldVolumeFrom2026: number;
    }> {
        try {
            console.log("Scraping price data for API URL:", apiUrl);
            await this.navigate(page, apiUrl);

            const result = await page.evaluate(async (url) => {
                const res = await fetch(url, {
                    credentials: "include",
                });

                const data = await res.json();

                return data["data"] ?? {};
            }, apiUrl);

            if (!result) {
                console.log("No data returned from API for URL:", apiUrl);
                return {
                    priceOnRelease: 0,
                    priceEvolution: [],
                    ebaySoldVolumeFrom2026: 0
                }
            }

            let ebayData: any[] = [];
            if (!result["ebay"]) {
                console.log("No ebay data available for this card");
            } else {
                ebayData = result["ebay"]["soldListings"]?.["ungraded"] ?? [];
            }

            let priceHistory: any[] = [];
            if (!result["priceHistory"] || !result["priceHistory"]["conditions"] || !result["priceHistory"]["conditions"]["Near Mint"]) {
                console.log("No price history available for this card");
            } else {
                priceHistory = result["priceHistory"]["conditions"]["Near Mint"]["history"] ?? [];
            }
           

            const priceEvolution: number[] = []
            for (let i = 0; i < priceHistory.length; i+=30) { 
                priceEvolution.push(priceHistory[i].market);
            }

            const result2= {
                priceOnRelease: priceHistory[0]?.market ?? 0,
                priceEvolution: priceEvolution,
                ebaySoldVolumeFrom2026: ebayData.length
            }

            return result2;
        } catch (error) {
            console.error("Error fetching price data for API URL:", error);
            throw error;
        }
    }

    private async createAccountInPriceTracker(): Promise<{ email: string; pw: string }> {
        return new Promise((resolve) => {
            const email = "xavodig183@ebflyai.com"
            const pw = "1342_ECOmessi"

            resolve({ email, pw });
        });
        
        // const page1 = await this.newPage();
        // const page2 = await this.newPage();

        // try {
        //     await this.navigate(
        //         page1,
        //         "https://temp-mail.org/en/"
        //     );

        //     console.log("Navigating succesfully")
            
        //     const tempEmail = await page1.waitForSelector("#mail");

        //     let tempEmailValue = await tempEmail?.evaluate(el => (el as HTMLInputElement).value) ?? "";

        //     while(tempEmailValue.includes("Loading")) {
        //         console.log("Waiting for temporary email to load...");
        //         await this.sleep(1000);
        //         tempEmailValue = await tempEmail?.evaluate(el => (el as HTMLInputElement).value) ?? "";
        //     }
            
        //     console.log("Temporary email generated:", tempEmailValue);

        //     const email = tempEmailValue;
        //     const pw = "TempPassword123!";

        //     await this.navigate(
        //         page2,
        //         "https://www.pokemonpricetracker.com/sign-up"
        //     );

        //     await this.sleep(1000 + Math.random() * 1000);

        //     const emailInput = await page2.waitForSelector('#emailAddress-field');
        //     const passwordInput = await page2.waitForSelector('#password-field');
        //     const agreeTermsCheckbox = await page2.waitForSelector('#legalAccepted-field');
        //     const signUpButton = await page2.waitForSelector('#main-content > div > div > div > div.cl-card.cl-signUp-start.🔒️.cl-internal-d5pd3d > div.cl-main.🔒️.cl-internal-vvtys3 > form > div.cl-internal-1pnppin > div > button');
            
        //     await emailInput?.type(email);
        //     await this.sleep(1000 + Math.random() * 1000);

        //     await passwordInput?.type(pw);
        //     await this.sleep(1000 + Math.random() * 1000);

        //     await agreeTermsCheckbox?.click();
        //     await this.sleep(1000 + Math.random() * 1000);

        //     await signUpButton?.click();
        //     await this.sleep(1000 + Math.random() * 1000);

        //     return { email, pw };
        // } catch (error) {
        //     throw error
        // } finally {
        //     await this.safeClosePage(page1);
        // }
    }

    // ============================================================
    // MERGING
    // ============================================================
    private async mergeData(): Promise<Record<string, PokemonSet>> {
        const data = await fs.readFile(
            this.outputDirectory + "/processed/pokemon-sets.json",
            "utf8"
        );

        // console.log(data); 
    
        const result = data ? JSON.parse(data) as Record<string, PokemonSet> : {};

        const chaseCardsPerSet: Partial<Record<string, RawChaseCard[]>> = Object.groupBy(this.chaseCards, (item) => item.setName);

        const hitsPerSet: Partial<Record<string, RawCard[]>> = Object.groupBy(this.cards, (item) => item.setName);

        const pullRatesPerset: Partial<Record<string, RawPullRate[]>> = Object.groupBy(this.pullRates, (item) => item.setName);

        const cardsPerSet = Object.entries(this.priceAPIUrls).reduce<
            Record<string, Record<string, string>>
        >((result, [key, url]) => {
            const [set, cardNumber] = key.split("/");

            if (!set || !cardNumber || isNaN(parseInt(cardNumber))) return result;

            (result[set] ??= {})[cardNumber] = url;

            return result;
        }, {});

        const { email, pw } = await this.createAccountInPriceTracker();

        const page = await this.signInToPriceTracker(email, pw);

        for (const pkmnSet of this.sets) {
            if (!pkmnSet) {
                throw new Error("No sets available to process.");
            }

            const { name: setName, series: setSeries, releaseDate: setReleaseDate } = pkmnSet;

            const boosterPrice = this.boosterPrices.find(bp => bp.setName.includes(setName))?.price ?? 0;

            const setChaseCards = chaseCardsPerSet[setName];
            const setHitRates = hitsPerSet[setName];
            const setPullRates = pullRatesPerset[setName];
            const setCards = cardsPerSet[setName];
            
            const hitsRarities: HitRarity[] = setPullRates ? setPullRates.map((pullRate) => {
                    const concernedCards: CardData[] = (setHitRates ?? [])
                        .filter(card => card.rarity === pullRate.rarity)
                        .map((card: RawCard) => {
                            const chase = setChaseCards?.some(
                                chaseCard => chaseCard.number === card.number
                            ) ?? false;

                            let popularity = 0;

                            if (card.isPokemon) {
                                const splitPokemonName = card.name.split(" ");

                                for (let start = 0; start < splitPokemonName.length; start++) {
                                    let current = "";

                                    for (
                                        let end = start;
                                        end < splitPokemonName.length;
                                        end++
                                    ) {
                                        current +=
                                            (current ? " " : "") +
                                            splitPokemonName[end];

                                        if (
                                            this.pokemonPopularity[current] !== undefined
                                        ) {
                                            popularity =
                                                this.pokemonPopularity[current] ?? 0;
                                            break;
                                        }
                                    }
                                }
                            }

                            return {
                                name: card.name,
                                number: card.number,
                                image: card.image,

                                isChase: chase,
                                isPromo: card.isPromo,
                                isPokemon: card.isPokemon,

                                pokemonPopularity: popularity,

                                priceOnRelease: 0,
                                priceEvolution: [],

                                ebaySoldVolumeFrom2026: 0
                            };
                        }
                    );

                    const cardPullRate = 1 / pullRate.pullRate;
                    const numberOfCards = concernedCards.length;
                    const specificCardPullRate =
                        cardPullRate / numberOfCards;

                    const costPerPull =
                        (1 / specificCardPullRate) * boosterPrice;

                    return {
                        rarity: pullRate.rarity,
                        pullRate: cardPullRate,
                        numberOfCards,
                        specificCardPullRate,
                        costPerPull,
                        concernedCards,
                        apiUrls: concernedCards.reduce<Record<string, string>>((acc, card) => {
                            const cardAPIUrl =
                                cardsPerSet[setName]?.[card.number] ?? "";

                            if (cardAPIUrl) {
                                acc[card.number] = cardAPIUrl;
                            }

                            return acc;
                        }, {})
                    };
                }) : [];

            let hitLimitReached = false;

        for (let j = 0; j < hitsRarities.length; j++) {
            if (hitLimitReached) {
                break;
            }

            const rarityData = hitsRarities[j];

            if (!rarityData) {
                continue;
            }

            for (let i = 0; i < rarityData.concernedCards.length; i++) {
                const card = rarityData.concernedCards[i];

                if (!card) {
                    continue;
                }

                const cached = await this.getCardCache(
                    setName,
                    card.number
                );

                if (cached) {
                    console.log(
                        `Using cached data for ${card.name} (${card.number})`
                    );

                    // @ts-expect-error
                    hitsRarities[j].concernedCards[i] = {
                        ...card,
                        ...cached
                    };

                    const finalPokemonSet: PokemonSet = {
                        name: setName,
                        series: setSeries,
                        number: "0",
                        releaseDate: setReleaseDate,
                        boosterPrice: boosterPrice,
                        numberOfChases: setChaseCards?.length ?? 0,
                        numberOfHits: setHitRates?.length ?? 0,
                        chaseRatioOutOfHits:
                            (setChaseCards?.length ?? 0) /
                            (setHitRates?.length ?? 1),
                        numberOfCards: Object.keys(
                            setCards ?? {}
                        ).length,
                        hitsRarities: hitsRarities
                    };

                    result[setName] = finalPokemonSet;

                    await this.writeJson(result);

                    continue;
                }

                console.log(
                    `Scraping price data for ${card.name} (${card.number})`
                );

                const cardApiUrl =
                    cardsPerSet[setName]?.[card.number] ?? "";

                if (!cardApiUrl) {
                    console.warn(
                        `No API URL found for ${card.name} (${card.number}) in set ${setName}`
                    );
                    continue;
                }

                let priceData: {
                    priceOnRelease: number;
                    priceEvolution: any[];
                    ebaySoldVolumeFrom2026: number;
                } | null = null;

                // =====================================================
                // Retry up to 3 times if we get completely empty data
                // =====================================================

                for (let attempt = 1; attempt <= 3; attempt++) {
                    try {
                        console.log(
                            `Attempt ${attempt}/3 for ${card.name} (${card.number})`
                        );

                        const {
                            priceOnRelease,
                            priceEvolution,
                            ebaySoldVolumeFrom2026
                        } = await this.scrapeCardPriceData(
                            page,
                            cardApiUrl
                        );

                        const noData =
                            priceOnRelease === 0 &&
                            priceEvolution.length === 0 &&
                            ebaySoldVolumeFrom2026 === 0;

                        if (noData) {
                            console.warn(
                                `No price data returned for ${card.name} (${card.number})`
                            );

                            if (attempt < 3) {
                                console.log(
                                    `Retrying in 10 seconds...`
                                );

                                await new Promise(resolve =>
                                    setTimeout(resolve, 10000)
                                );

                                continue;
                            }

                            // All 3 attempts returned no data.
                            console.error(
                                `Price limit likely reached. ` +
                                `3 consecutive attempts returned no data.`
                            );

                            hitLimitReached = true;
                            break;
                        }

                        // =================================================
                        // Successful request
                        // =================================================

                        priceData = {
                            priceOnRelease,
                            priceEvolution,
                            ebaySoldVolumeFrom2026
                        };

                        console.log(
                            "Scraped successfully for card:",
                            card.name,
                            "priceOnRelease:",
                            priceOnRelease,
                            "priceEvolution:",
                            priceEvolution,
                            "ebaySoldVolumeFrom2026:",
                            ebaySoldVolumeFrom2026
                        );

                        break;

                    } catch (error) {
                        console.error(
                            `Attempt ${attempt}/3 failed for ${card.name} (${card.number})`,
                            error
                        );

                        if (attempt < 3) {
                            console.log(
                                `Retrying in 10 seconds...`
                            );

                            await new Promise(resolve =>
                                setTimeout(resolve, 10000)
                            );
                        } else {
                            console.error(
                                `All 3 attempts failed. Stopping price scraping.`
                            );

                            hitLimitReached = true;
                        }
                    }
                }

                // =====================================================
                // Stop if all retries failed
                // =====================================================

                if (hitLimitReached || !priceData) {
                    break;
                }

                // =====================================================
                // Save cache immediately
                // =====================================================

                await this.saveCardCache(
                    setName,
                    card.number,
                    priceData
                );

                // =====================================================
                // Update card
                // =====================================================

                // @ts-expect-error
                hitsRarities[j].concernedCards[i] = {
                    ...card,
                    ...priceData
                };

                // =====================================================
                // Save complete set progress
                // =====================================================

                const finalPokemonSet: PokemonSet = {
                    name: setName,
                    series: setSeries,
                    number: "0",
                    releaseDate: setReleaseDate,
                    boosterPrice: boosterPrice,
                    numberOfChases: setChaseCards?.length ?? 0,
                    numberOfHits: setHitRates?.length ?? 0,
                    chaseRatioOutOfHits:
                        (setChaseCards?.length ?? 0) /
                        (setHitRates?.length ?? 1),
                    numberOfCards: Object.keys(
                        setCards ?? {}
                    ).length,
                    hitsRarities: hitsRarities
                };

                result[setName] = finalPokemonSet;

                await this.writeJson(result);

                console.log(
                    `Saved progress for ${card.name} (${card.number})`
                );

                await new Promise(resolve =>
                    setTimeout(resolve, 2000)
                );
            }

            if (hitLimitReached) {
                break;
            }
        }

        if (hitLimitReached) {
            console.warn(
                "Price API limit appears to have been reached. Stopping scraper."
            );
            break;
        }
        }

        // console.log(finalPokemonSet);
        return result;
    }

    // ============================================================
    // HELPERS
    // ============================================================

    private async getCardCache(
        setName: string,
        cardNumber: string
    ): Promise<{
        priceOnRelease: number;
        priceEvolution: unknown[];
        ebaySoldVolumeFrom2026: number;
    } | null> {

        const cacheDirectory = path.join(
            this.outputDirectory,
            "price-cache",
            setName
        );

        const cachePath = path.join(
            cacheDirectory,
            `${cardNumber}.json`
        );

        try {
            const data = await fs.readFile(cachePath, "utf8");
            return JSON.parse(data);
        } catch {
            return null;
        }
    }

    private async saveCardCache(
        setName: string,
        cardNumber: string,
        data: {
            priceOnRelease: number;
            priceEvolution: unknown[];
            ebaySoldVolumeFrom2026: number;
        }
    ): Promise<void> {

        const cacheDirectory = path.join(
            this.outputDirectory,
            "price-cache",
            setName
        );

        await fs.mkdir(cacheDirectory, {
            recursive: true
        });

        const cachePath = path.join(
            cacheDirectory,
            `${cardNumber}.json`
        );

        await fs.writeFile(
            cachePath,
            JSON.stringify(data, null, 2),
            "utf8"
        );
    }

    private async newPage(): Promise<Page> {

        const page = await this.browser.newPage();

        await page.setViewport({
            width: 1440,
            height: 1000
        });

        await page.setUserAgent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
            "AppleWebKit/537.36 (KHTML, like Gecko) " +
            "Chrome/150.0.0.0 Safari/537.36"
        );

        return page;
    }

    private async safeClosePage(page: Page): Promise<void> {
        if (!page.isClosed()) {
            try {
                await page.close();
            } catch {
                console.warn("Page already disconnected");
            }
        }
    }

    private async navigate(
        page: Page,
        url: string
    ): Promise<void> {

        console.log(`Navigating: ${url}`);

        await page.goto(url, {
            waitUntil: "domcontentloaded",
            timeout: 60_000
        });

        /*
         * Small delay for JS-rendered content.
         */
        await new Promise(resolve =>
            setTimeout(resolve, 1_000)
        );
    }

    private async sleep(ms: number): Promise<void> {
        await new Promise(resolve => setTimeout(resolve, ms));
    }

    private async retry<T>(
        fn: () => Promise<T>,
        attempts = 3
    ): Promise<T> {
        let lastError: unknown;

        for (let i = 0; i < attempts; i++) {
            try {
                return await fn();
            } catch (error) {
                lastError = error;
                await this.sleep(3000 * (i + 1));
            }
        }

        throw lastError;
    }

    private async writeJson(
        data: Record<string, PokemonSet>
    ): Promise<void> {

        await fs.mkdir(
            this.outputDirectory,
            { recursive: true }
        );

        const outputPath =
            path.join(
                this.outputDirectory,
                "processed/pokemon-sets.json"
            );

        await fs.writeFile(
            outputPath,
            JSON.stringify(data, null, 2),
            "utf8"
        );

        console.log(
            `Written: ${outputPath}`
        );
    }
}

const testInstance = new PokemonSetDetailsScraper(
    "/Users/anas/Projects/pkmn-analysis/data"
);

testInstance.scrape()
    .then(() => {
        console.log("Scraping completed.");
    })
    .catch(error => {
        console.error("Error during scraping:", error);
    });