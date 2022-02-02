import time
import json
from datetime import datetime
from requests_html import HTMLSession
from amazon_config import (
    DIRECTORY,
    NAME,
    CURRENCY,
    FILTERS,
    BASE_URL,
)


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
        self.session = HTMLSession()
        self.headers = {
            "USer-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0"
        }
        self.base_url = base_url
        self.search_term = search_term
        self.currency = currency
        self.price_filter = f"&rh=p_36%3A{filters['min']}00-{filters['max']}00"

    def run(self):
        print("Strating script...")
        print(f"Looking for {self.search_term} products...")
        urls = self.get_product_links()
        if not urls:
            print("Stopped script.")
            return
        print(f"Got {len(urls)} products.")
        print("Parsing the product links...")
        products = [self.parse_urls(url) for url in urls]
        print(f"Got information about {len(products)} products.")
        return products

    def get_product_links(self):  #
        # https://www.amazon.com/s?k=ps5&rh=p_36%3A27500-65000
        url = self.session.get(
            self.base_url + self.search_term + self.price_filter,
            headers=self.headers,
        )
        url.html.render(timeout=60)
        product_asins = [
            asin.attrs["data-asin"]
            for asin in url.html.find("div[data-asin]")
            if asin.attrs["data-asin"] != ""
        ]
        if "B015HS4O1K" in product_asins:
            product_asins.remove("B015HS4O1K")
        product_link = ["https://www.amazon.com/dp/" + link for link in product_asins]
        return product_link

    def parse_urls(self, url):
        _session = self.session.get(url, headers=self.headers)
        _session.html.render(timeout=60)
        print("----------------------------------------------------------------")
        print(f"Getting Product:{url} --- Data")

        product_asin = url.split("/")[4]
        print("ASIN:", product_asin)
        product_title = self.get_title(url)
        print("TITLE:", product_title)
        product_price = self.get_price(url)
        print("PRICE:", product_price)
        product_seller = self.get_seller(url)
        print("SELLER:", product_seller)
        product_review_count = self.get_review_count(url)
        print("REVIEW_COUNT:", product_review_count)
        product_rating = self.get_rating(url)
        print("RATING:", product_rating)
        product_photo_url = self.get_photo_url(url)
        print("PHOTO_URL:", product_photo_url)
        print("----------------------------------------------------------------")
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

    def get_title(self, url):
        _session = self.session.get(url, headers=self.headers)
        _session.html.render(timeout=60)
        title = None

        try:
            if _session.html.find("span#productTitle", first=True):
                title = _session.html.find("span#productTitle", first=True).text
                return title
            elif _session.html.find("h1.a-size-large", first=True):
                title = _session.html.find("h1.a-size-", first=True).text
                return title
            else:
                title = ""

        except Exception as e:
            print(e)
            print(f"Can't get a title of a product - {url}")
            return None

    def get_seller(self, url):
        _session = self.session.get(url, headers=self.headers)
        _session.html.render(timeout=60)
        try:
            seller = _session.html.find("a#bylineInfo", first=True).text
            if "Visit the" in seller:
                return " ".join(seller.split(" ")[2:])
            elif "Brand" or "Brand: " in seller:
                return "".join(seller.split(" ")[0:])

        except Exception as e:
            print(e)
            try:
                return _session.html.find("a.qa-byline-url", first=True).text
            except Exception as e:
                print(f"Can't get a seller of a product - {url}")
                return None

    def get_price(self, url):
        price = None
        _session = self.session.get(url, headers=self.headers)
        _session.html.render(timeout=60)
        try:
            price_1 = _session.html.find("span.apexPriceToPay", first=True)
            if price_1 is not None:
                price = float(price_1.text.split("$")[1])
            else:
                price = float(
                    _session.html.find(
                        "span#priceblock_ourprice", first=True
                    ).text.split("$")[1]
                )
                print(price)
        except Exception as e:
            print(e)
            try:
                availability = _session.html.find("span.a-color-price", first=True).text
                out_of_stock = _session.html.find("span.a-color-price", first=True).text
                availability_message = _session.html.find(
                    "span.qa-availability-message", first=True
                ).text
                if "In Stock." or None in availability:
                    price = float(
                        _session.html.find(
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
                            _session.html.find(
                                "span.a-color-price:nth-child(2)", first=True
                            ).text.split("$")[1]
                        )
                    except Exception as e:
                        availability = None
                        if _session.html.find(
                            "div#availability", first=True
                        ).text.startswith("P"):
                            availability = "N/A"
                            print(f"Product {availability}")
                        elif (
                            "In Stock."
                            in _session.html.find("div#availability", first=True).text
                        ):
                            price = 0
                        else:
                            availability = _session.html.find(
                                "div#availability", first=True
                            ).text.split("\n")[0]
                            print(f"Product {availability}")

                        return None
        return float(price)

    def get_review_count(self, url):
        _session = self.session.get(url, headers=self.headers)
        _session.html.render(timeout=60)

        try:
            return int(
                _session.html.find("span#acrCustomerReviewText", first=True)
                .text.split(" ")[0]
                .replace(",", "")
                .strip()
            )
        except Exception as e:
            print(e)
            print(f"Can't get a review count of a product - {url}")
            return None

    def get_rating(self, url):
        _session = self.session.get(url, headers=self.headers)
        _session.html.render(timeout=60)

        try:
            return float(
                _session.html.find("span.a-icon-alt", first=True).text.split(" ")[0]
            )
        except Exception as e:
            print(e)
            print(f"Can't get a review of a product - {url}")
            return None

    def get_photo_url(self, url):
        _session = self.session.get(url, headers=self.headers)
        _session.html.render(timeout=60)

        try:
            return _session.html.find("img#landingImage", first=True).attrs["src"]
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
    am = AmazonAPI(NAME, FILTERS, BASE_URL, CURRENCY)
    scraped_data = am.run()
    data = remove_empty_elements(scraped_data)
    print(data)
    GenerateReport(NAME, FILTERS, BASE_URL, CURRENCY, data)
