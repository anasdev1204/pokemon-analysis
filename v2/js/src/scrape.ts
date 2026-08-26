import * as dotenv from 'dotenv';
dotenv.config();

import fs from "fs";
import path from "path";
import crypto from "crypto";


import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";
import type { Browser, Page } from "puppeteer";


type Data = {
    iv: string;
    data: string;
};

type Offer = {
    offer_id: number;
    user_id: number;
    number: string;
};

type Demand = {
    demand_id: number;
    user_id: number;
    number: string;
};

type PriceEvolutionEntry = {
    date: string;
    price: number;
};

type Card = {
    id: number;
    name: string;
    number: string;
    rarity: number;
    pokedexId: string | null;
    offer: Offer[];
    demand: Demand[];
    image: string;
    priceEvolutionCM: PriceEvolutionEntry[];
    priceEvolutionTCG: PriceEvolutionEntry[];
}

type SeriesCards = Record<string, {
    commercialName: string;
    hypeLevel: number;
    ageLevel: number;
    cards: Card[];
}>

class Scraper {

    private browser!: Browser;

    private readonly headless = true;
    private readonly outputDirectory = path.resolve(__dirname, "../data");
    private readonly cacheDirectory = path.resolve(__dirname, "../data/cache");
    private readonly ket = process.env.KET as string;
    private readonly raritiesToExclude = [1, 2, 3, 4, 5, 6, 21, 32, 38, 39, 40];
    private readonly raritiesLabel = {
        1: [7],
        2: [33],
        3: [34],
        4: [35, 36, 43, 45, 47]
    }

    seriesCards: SeriesCards = {};
    links: Record<string, URL> = {};

    constructor() {
        const encryptedData = JSON.parse(fs.readFileSync(`${this.outputDirectory}/init.json`, "utf8")); 
        const decryptedData = this.decryptPokecardex(encryptedData[0] as Data);
        const hypeLevel = JSON.parse(fs.readFileSync(`${this.outputDirectory}/raw/hype-level.json`, "utf8"));
        const ageLevel = JSON.parse(fs.readFileSync(`${this.outputDirectory}/raw/age-level.json`, "utf8"));

        const cachedSeriesData = JSON.parse(fs.readFileSync(`${this.outputDirectory}/raw/pokemon-sets.json`, "utf8"));

        if (cachedSeriesData && Object.keys(cachedSeriesData).length > 0) {
            this.seriesCards = cachedSeriesData;
            this.links = Object.fromEntries(
                Object.entries(cachedSeriesData).map(([shortName, series]) => {
                    const seriesLink = new URL(`/series/${shortName}`, "https://www.pokecardex.com");
                    return [shortName, seriesLink];
                })
            );
            return;
        } else {
            const { seriesCards, links } = this.getSeriesList(decryptedData, hypeLevel, ageLevel, 2);
            this.seriesCards = seriesCards;
            this.links = links;
        }  
    }

    async scrape() {
        await this.initBrowser();
        const page = await this.newPage();

        try {
            for (const [shortName, seriesLink] of Object.entries(this.links)) {
                console.log(`Scraping series: ${shortName} - ${seriesLink.href}`);

                await this.scrapeSetsData(page, shortName, seriesLink);
                
                // @ts-expect-error
                const isFullyScraped = this.seriesCards[shortName].cards.every(card => card.priceEvolutionCM.length > 0);
                if (isFullyScraped) {
                    console.log(`Series ${shortName} already fully scraped. Skipping card scraping.`);
                    continue;
                }

                await this.scrapeCardsData(page, shortName);
            }
        } catch (error) {
            console.error("An error occurred during scraping:", error);
        } finally {
            await this.safeClosePage(page);
            await this.browser.close();
        }
    }

    private async initBrowser(): Promise<void> {
        puppeteer.use(StealthPlugin());

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

    // Scrape pokecardex website 
    private async scrapeSetsData(
        page: Page,
        shortName: string,
        seriesLink: URL
    ): Promise<void> {
        try {
                // @ts-expect-error

            if (this.seriesCards[shortName].cards.length > 0) {
                console.log(`Series ${shortName} already scraped. Skipping.`);
                return;
            }

            console.log(`Scraping series: ${shortName}`);

            const decryptedData = await this.readPokecardexData(page, seriesLink);
            const cards = decryptedData["cartes"].filter((cards: any) => {
                return !this.raritiesToExclude.includes(cards.id_rarete);
            });

            // @ts-expect-error
            this.seriesCards[shortName].cards = cards.map((card: any) => {
                const cardNumber = parseInt(card.num_card.slice(0, 3));
                const rarityLabel = Object.entries(this.raritiesLabel)
                .find(([_, rarities]) => rarities.includes(card.id_rarete));

                return ({
                    id: card.id_card,
                    name: card.name_card_fr,
                    number: cardNumber,
                    rarity: rarityLabel ? parseInt(rarityLabel[0]) : card.id_rarete,
                    pokedexId: card.id_pokedex || null,
                    offer: [],
                    demand: [],
                    image: `https://pokecardex-scans.b-cdn.net/sets/${shortName}/FR/${cardNumber}.jpg?class=md`,
                    priceEvolutionCM: [],
                    priceEvolutionTCG: []
                })
            });

            fs.writeFileSync(
                `${this.cacheDirectory}/${shortName}.json`,
                JSON.stringify(this.seriesCards[shortName], null, 2),
                "utf8"
            );

            fs.writeFileSync(
                `${this.outputDirectory}/raw/pokemon-sets.json`,
                JSON.stringify(this.seriesCards, null, 2),
                "utf8"
            );
        } catch (error) {
            console.error(`Error occurred while scraping ${shortName}:`, error);
            throw error;
        }
    }

    private async scrapeCardsData(
        page: Page,
        shortName: string
    ): Promise<void> {
        try {
            const cards: Card[] = [];

            // @ts-expect-error
            for (const card of this.seriesCards[shortName].cards) {
                const cardName = card.name;
                const cardNumber = card.number;
                const cardId = card.id;
                const cardLink = new URL(`/carte/${cardId}`, "https://www.pokecardex.com");

                console.log(`Scraping Card ${cardName} (${cardNumber}) from series ${shortName}`);

                // @ts-expect-error
                const currentEntry = this.seriesCards[shortName].cards.find(c => c.id === cardId) as Card;

                if (!currentEntry) {
                    console.warn(`Card ${cardName} (${cardNumber}) not found in series ${shortName}. Skipping.`);
                }

                if (
                    currentEntry.priceEvolutionCM.length > 0
                ) {
                    console.log(`Card ${cardName} (${cardNumber}) already scraped. Skipping.`);
                }

                const decryptedData = await this.readPokecardexData(page, cardLink);

                const offerData: Offer[] = decryptedData["ventes"].map((offer: any) => ({
                    offer_id: offer.id_possession,
                    user_id: offer.id_user,
                    number: offer.quantite
                }));
                const demandData: Demand[] = decryptedData["recherches"].map((demand: any) => ({
                    demand_id: demand.id_recherche,
                    user_id: demand.id_user,
                    number: demand.achat
                }));

                const priceEvolutionCM: PriceEvolutionEntry[] = decryptedData["carte"]["priceHistory"]["cardmarket"]["180"]["points"].map((entry: any) => ({
                    date: entry.date,
                    price: entry.v_null_normale_avg30
                }));
                const priceEvolutionTCG: PriceEvolutionEntry[] = decryptedData["carte"]["priceHistory"]["tcgplayer"]["180"]["points"].map((entry: any) => ({
                    date: entry.date,
                    price: entry.tcg_holofoil_market
                }));

                const newCard: Card = {
                    ...card,
                    offer: offerData,
                    demand: demandData,
                    priceEvolutionCM: priceEvolutionCM,
                    priceEvolutionTCG: priceEvolutionTCG
                }

                cards.push(newCard);
            }

            // @ts-expect-error
            this.seriesCards[shortName].cards = [
                ...cards
            ];

            fs.writeFileSync(
                `${this.cacheDirectory}/${shortName}.json`,
                JSON.stringify(this.seriesCards[shortName], null, 2),
                "utf8"
            );

            fs.writeFileSync(
                `${this.outputDirectory}/raw/pokemon-sets.json`,
                JSON.stringify(this.seriesCards, null, 2),
                "utf8"
            );
        } catch (error) {
            console.error(`Error occurred while scraping ${shortName}:`, error);
            throw error;
        }
    }

    // Puppeteer helpers
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

    // Data Helpers
    private async readPokecardexData(page: Page, link: URL): Promise<any> {
        const documentResponsePromise = page.waitForResponse(
            response =>
                response.request().resourceType() === "document" &&
                response.url() === link.href
        );

        await this.navigate(page, link.href);

        const response = await documentResponsePromise;
        const html = await response.text();

        const marker = "window.__INITIAL_DATA_ENCRYPTED__";
        const index = html.indexOf(marker);

        if (index !== -1) {
            const start = html.indexOf("{", index);

            if (start !== -1) {
                const end = html.indexOf("};", start);

                if (end !== -1) {
                    const jsonString = html.substring(start, end + 1);

                    const encryptedData = JSON.parse(jsonString);
                    const decryptedData = this.decryptPokecardex(encryptedData as Data);
                    
                    return decryptedData;
                }
            }
        }

        throw new Error("Failed to extract encrypted data from the page.");
    }

    private decryptPokecardex(encrypted: Data) {
        const key = Buffer.from(
            this.ket,
            "utf8"
        );

        const iv = Buffer.from(encrypted.iv, "base64");
        const ciphertext = Buffer.from(encrypted.data, "base64");

        const decipher = crypto.createDecipheriv(
            "aes-256-cbc",
            key,
            iv
        );

        const plaintext = Buffer.concat([
            decipher.update(ciphertext),
            decipher.final()
        ]);

        return JSON.parse(plaintext.toString("utf8"));
    }

    private getSeriesList(data: any, hypeLevel: Record<string, number>, ageLevel: Record<string, number>, numberBlocks: number = 2): {
        seriesCards: SeriesCards;
        links: Record<string, URL>;
    } { 
        const result: SeriesCards = {};
        const blocks = data["seriesMenu"]["blocksByRegion"]["FR"].slice(0, numberBlocks);

        const links: Record<string, URL> = {}
        for (const block of blocks) {
            for (const series of block.series) {
                const shortName = series.shortName;
                const commercialName = series.commercialName;

                if (!shortName || !commercialName) {
                    continue;
                }

                result[shortName] = {
                    commercialName: commercialName,
                    hypeLevel: hypeLevel[shortName] || 0,
                    ageLevel: ageLevel[shortName] || 0,
                    cards: []
                };

                const seriesLink = new URL(series.link, "https://www.pokecardex.com");
                links[shortName] = seriesLink;
            }
        }

        return {
            seriesCards: result,
            links: links
        }
    }
}

const scraper = new Scraper();

scraper.scrape()
.then(() => {
    console.log("Scraping completed successfully.");
})
.catch((error) => {
    console.error("An error occurred during scraping:", error);
});