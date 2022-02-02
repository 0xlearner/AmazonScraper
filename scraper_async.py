import time
import json
from datetime import datetime
from requests_html import AsyncHTMLSession
import asyncio
from amazon_config import (
    DIRECTORY,
    NAME,
    CURRENCY,
    FILTERS,
    BASE_URL,
)

TIMEOUT = 240
RETRIES = 4


class GenerateReport:
    def __init__(self, file_name, filters, base_link, currency, data):

        self.data = data
        self.file_name = file_name
        self.filters = filters
        self.base_link = base_link
        self.currency = currency

        report = {
            "title": self.file_name,
            "date": self.get_now(),
            "product_count": len(self.data),
            "best_item": self.get_best_item(),
            "currency": self.currency,
            "filters": self.filters,
            "base_link": self.base_link,
            "products": self.data,
        }
        print("Creating Report...")
        with open(f"{DIRECTORY}/{file_name}.json", "w") as f:
            json.dump(report, f)
        print("Done.")

    @staticmethod
    def get_now():
        now = datetime.now()
        return now.strftime("%d/%m/%Y %H:%M:%S")

    def get_best_item(self):
        try:
            return sorted(self.data, key=lambda x: x["rating"], reverse=True)[0]
        except Exception as e:
            print(e)
            print("Problem with sorting items")
            return None


class AmazonAPI:
    def __init__(self, search_term, filters, base_url, currency):
        self.asession = AsyncHTMLSession()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0",
            "Accept": "text/html,*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
            "Referer": f"https://www.amazon.com/s?k={search_term}&ref=nb_sb_noss",
        }
        self.base_url = base_url
        self.search_term = search_term
        self.currency = currency
        self.price_filter = f"&rh=p_36%3A{filters['min']}00-{filters['max']}00"

    async def run(self):
        print("Strating script...")
        print(f"Looking for {self.search_term} products...")
        urls = await self.get_product_links()
        if not urls:
            print("Stopped script.")
            return
        print(f"Got {len(urls)} products.")
        print("Parsing the product links...")
        tasks = [asyncio.create_task(self.parse_urls(url)) for url in urls]
        # print(f"Got information about {len(products)} products.")
        result = await asyncio.gather(*tasks)
        return result

    async def get_product_links(self):  #
        # https://www.amazon.com/s?k=ps5&rh=p_36%3A27500-65000
        url = await self.asession.get(
            self.base_url + self.search_term + self.price_filter,
            headers=self.headers,
        )
        # await url.html.arender(retries=RETRIES, timeout=TIMEOUT)
        print(url.status_code)
        product_asins = [
            asin.attrs["data-asin"]
            for asin in url.html.find("div[data-asin]")
            if asin.attrs["data-asin"] != ""
        ]
        if "B015HS4O1K" in product_asins:
            product_asins.remove("B015HS4O1K")
        product_link = ["https://www.amazon.com/dp/" + link for link in product_asins]
        return product_link

    async def parse_urls(self, url):
        _asession = await self.asession.get(url, headers=self.headers)
        # await _asession.html.arender(retries=RETRIES, timeout=TIMEOUT)
        print(f"Getting Product:{url} --- Data")

        product_asin = url.split("/")[4]
        print("ASIN:", product_asin)
        product_title = await self.get_title(url)
        print(f"TITLE: {product_title} --- {url}")
        product_price = await self.get_price(url)
        print(f"PRICE: {product_price} --- {url}")
        product_seller = await self.get_seller(url)
        print(f"SELLER: {product_seller} --- {url}")
        product_review_count = await self.get_review_count(url)
        print(f"REVIEW_COUNT: {product_review_count} --- {url}")
        product_rating = await self.get_rating(url)
        print(f"RATING: {product_rating} --- {url}")
        product_photo_url = await self.get_photo_url(url)
        print(f"PHOTO: {product_photo_url} --- {url}")
        if product_title and product_price and product_rating:
            product_info = {
                "asin": product_asin,
                "url": url,
                "title": product_title,
                "price": product_price,
                "rating": product_rating,
                "photo_url": product_photo_url,
                "seller": product_seller,
                "review_count": product_review_count,
            }

            return product_info
        return None

    async def get_title(self, url):
        _asession = await self.asession.get(url, headers=self.headers)
        # await _asession.html.arender(retries=RETRIES, timeout=TIMEOUT)
        title = None

        try:
            if _asession.html.find("span#productTitle", first=True):
                title = _asession.html.find("span#productTitle", first=True).text
                return title
            elif _asession.html.find("h1.a-size-large", first=True):
                title = _asession.html.find("h1.a-size-", first=True).text
                return title
            else:
                title = ""

        except Exception as e:
            print(e)
            print(f"Can't get a title of a product - {url}")
            return None

    async def get_seller(self, url):
        _asession = await self.asession.get(url, headers=self.headers)
        # await _asession.html.arender(retries=RETRIES, timeout=TIMEOUT)
        try:
            seller = _asession.html.find("a#bylineInfo", first=True).text
            if "Visit the" in seller:
                return " ".join(seller.split(" ")[2:])
            elif "Brand" or "Brand: " in seller:
                return "".join(seller.split(" ")[0:])

        except Exception as e:
            print(e)
            try:
                return _asession.html.find("a.qa-byline-url", first=True).text
            except Exception as e:
                print(f"Can't get a seller of a product - {url}")
                return None

    async def get_price(self, url):
        price = None
        _asession = await self.asession.get(url, headers=self.headers)
        # await _asession.html.arender(retries=RETRIES, timeout=TIMEOUT)
        try:
            price_1 = _asession.html.find("span.apexPriceToPay", first=True)
            if price_1 is not None:
                price = float(price_1.text.split("$")[1])
            else:
                price = float(
                    _asession.html.find(
                        "span#priceblock_ourprice", first=True
                    ).text.split("$")[1]
                )
                print(price)
        except Exception as e:
            print(e)
            try:
                availability = _asession.html.find(
                    "span.a-color-price", first=True
                ).text
                out_of_stock = _asession.html.find(
                    "span.a-color-price", first=True
                ).text
                availability_message = _asession.html.find(
                    "span.qa-availability-message", first=True
                ).text
                if "In Stock." or None in availability:
                    price = float(
                        _asession.html.find(
                            "span.apexPriceToPay", first=True
                        ).text.split("$")[1]
                    )
                elif "Temporarily out of stock." in out_of_stock:
                    price = 0
                elif "Currently unavailable." in availability:
                    price = 0
                elif "Currently unavailable." in availability_message:
                    price = 0
                    print(price)
                elif "Currently unavailable." in out_of_stock:
                    price = 0
                else:
                    price = None
            except Exception as e:
                print(price)
                if not price:
                    try:
                        price = float(
                            _asession.html.find(
                                "span.a-color-price:nth-child(2)", first=True
                            ).text.split("$")[1]
                        )
                    except Exception as e:
                        availability = None
                        if _asession.html.find(
                            "div#availability", first=True
                        ).text.startswith("P"):
                            availability = "N/A"
                            print(f"Product {availability}")
                        elif (
                            "In Stock."
                            in _asession.html.find("div#availability", first=True).text
                        ):
                            price = 0
                        else:
                            availability = _asession.html.find(
                                "div#availability", first=True
                            ).text.split("\n")[0]
                            print(f"Product {availability}")

                        return None
        return float(price)

    async def get_review_count(self, url):
        _asession = await self.asession.get(url, headers=self.headers)
        # await _asession.html.arender(retries=RETRIES, timeout=TIMEOUT)

        try:
            return int(
                _asession.html.find("span#acrCustomerReviewText", first=True)
                .text.split(" ")[0]
                .replace(",", "")
                .strip()
            )
        except Exception as e:
            print(e)
            print(f"Can't get a review count of a product - {url}")
            return None

    async def get_rating(self, url):
        _asession = await self.asession.get(url, headers=self.headers)
        # await _asession.html.arender(retries=RETRIES, timeout=TIMEOUT)

        try:
            return float(
                _asession.html.find("span.a-icon-alt", first=True).text.split(" ")[0]
            )
        except Exception as e:
            print(e)
            print(f"Can't get a review of a product - {url}")
            return None

    async def get_photo_url(self, url):
        _asession = await self.asession.get(url, headers=self.headers)
        # await _asession.html.arender(retries=RETRIES, timeout=TIMEOUT)

        try:
            return _asession.html.find("img#landingImage", first=True).attrs["src"]
        except Exception as e:
            print(e)
            print(f"Can't get a photo url of a product - {url}")
            return None


def remove_empty_elements(d):
    """recursively remove empty lists, empty dicts, or None elements from a dictionary"""

    def empty(x):
        return x is None or x == {} or x == []

    if not isinstance(d, (dict, list)):
        return d
    elif isinstance(d, list):
        return [v for v in (remove_empty_elements(v) for v in d) if not empty(v)]
    else:
        return {
            k: v
            for k, v in ((k, remove_empty_elements(v)) for k, v in d.items())
            if not empty(v)
        }


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    am = AmazonAPI(NAME, FILTERS, BASE_URL, CURRENCY)
    scraped_data = loop.run_until_complete(am.run())
    data = remove_empty_elements(scraped_data)
    print(data)
    GenerateReport(NAME, FILTERS, BASE_URL, CURRENCY, data)
