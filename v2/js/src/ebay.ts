import * as dotenv from "dotenv";
dotenv.config();

import fs from "fs";

export interface EbayItem {
    itemId: string;
    title: string;
    price?: {
        value: string;
        currency: string;
    };
    condition?: string;
    conditionId?: string;
    buyingOptions?: string[];
    itemWebUrl?: string;
    image?: {
        imageUrl: string;
    };
    seller?: {
        username?: string;
        feedbackPercentage?: number;
        feedbackScore?: number;
    };
    [key: string]: any;
}

interface EbayToken {
    access_token: string;
    expires_at: number;
}

export class EbayScraper {
    private readonly clientId: string;
    private readonly clientSecret: string;
    private readonly marketplaceId: string;

    private readonly tokenFile = "./ebay_token.json";
    private readonly frenchLabels = ["fr", "france", "français", "française", "🇫🇷"];

    constructor(
        marketplaceId: string = "EBAY_FR"
    ) {
        if (!process.env.CLIENT_ID || !process.env.CLIENT_SECRET) {
            throw new Error(
                "CLIENT_ID and CLIENT_SECRET must be defined in .env"
            );
        }

        this.clientId = process.env.CLIENT_ID;
        this.clientSecret = process.env.CLIENT_SECRET;
        this.marketplaceId = marketplaceId;
    }

    private async getEbayToken(): Promise<string> {
        if (fs.existsSync(this.tokenFile)) {
            const token = fs.readFileSync(this.tokenFile, "utf8");

            if (token) {
                const tokenData: EbayToken = JSON.parse(token);
                const now = Math.floor(Date.now() / 1000);

                if (tokenData.expires_at > now) {
                    return tokenData.access_token;
                }
            }
        }

        const credentials = `${this.clientId}:${this.clientSecret}`;
        const encoded = Buffer.from(credentials).toString("base64");

        const response = await fetch(
            "https://api.ebay.com/identity/v1/oauth2/token",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    Authorization: `Basic ${encoded}`
                },
                body: new URLSearchParams({
                    grant_type: "client_credentials",
                    scope: "https://api.ebay.com/oauth/api_scope"
                })
            }
        );

        if (!response.ok) {
            const error = await response.text();

            throw new Error(
                `eBay OAuth failed (${response.status}): ${error}`
            );
        }

        const data = await response.json();

        if (!data.access_token) {
            throw new Error(
                `No access token returned: ${JSON.stringify(data)}`
            );
        }

        const tokenData: EbayToken = {
            access_token: data.access_token,
            expires_at:
                Math.floor(Date.now() / 1000) + data.expires_in
        };

        fs.writeFileSync(
            this.tokenFile,
            JSON.stringify(tokenData, null, 2)
        );

        return data.access_token;
    }

    private async search(
        query: string,
        filter: string,
        onlyFrench: boolean = true
    ): Promise<EbayItem[]> {
        const token = await this.getEbayToken();

        const allItems: EbayItem[] = [];

        const limit = 200;
        let offset = 0;
        let total = Infinity;

        while (offset < total) {
            const params = new URLSearchParams({
                q: query,
                limit: String(limit),
                offset: String(offset),
                filter
            });

            const response = await fetch(
                `https://api.ebay.com/buy/browse/v1/item_summary/search?${params}`,
                {
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "X-EBAY-C-MARKETPLACE-ID": this.marketplaceId,
                        Accept: "application/json"
                    }
                }
            );

            if (!response.ok) {
                const error = await response.text();

                throw new Error(
                    `eBay search failed (${response.status}): ${error}`
                );
            }

            const data = await response.json();

            let items: EbayItem[] = data.itemSummaries ?? [];

            if (onlyFrench) {
                items = items.filter(item => {
                    return this.frenchLabels.some(label => item.title.toLowerCase().includes(label));
                });
            }

            console.log(
                `Retrieved ${items.length} items ` +
                `(offset: ${offset}, total: ${data.total ?? 0})`
            );

            allItems.push(...items);

            total = data.total ?? 0;
            offset += items.length;

            console.log(data);


            if (data.total < limit || data.length === 0) {
                break;
            }
        }

        return allItems;
    }

    public async searchFixedPrice(
        query: string,
        onlyFrench: boolean = true
    ): Promise<EbayItem[]> {
        return this.search(
            query,
            "conditionIds:{4000},buyingOptions:{FIXED_PRICE}",
            onlyFrench
        );
    }

    public async searchAuctions(
        query: string,
        onlyFrench: boolean = true
    ): Promise<EbayItem[]> {
        return this.search(
            query,
            "conditionIds:{4000},buyingOptions:{AUCTION}",
            onlyFrench  
        );
    }
}

const ebayScraper = new EbayScraper("EBAY_FR");

ebayScraper.searchFixedPrice("Pokémon Salamèche 168/165").then(items => {
    console.log(`Found ${items.length} fixed price items.`);
    // console.log(items);
}).catch(error => {
    console.error("Error searching fixed price items:", error);
});