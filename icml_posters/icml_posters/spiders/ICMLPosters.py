import scrapy
import os

class ICMLPosterSpider(scrapy.Spider):
    name = "ICMLPoster"
    allowed_domains = ["icml.cc"]
    start_urls = ["https://icml.cc/virtual/2025/events/2025SpotlightPosters"]

    custom_settings = {
        "FEED_FORMAT": "json",
        "FEED_URI": "posters.json",
        "DOWNLOAD_DELAY": 1,
        "ROBOTSTXT_OBEY": True
    }

    def parse(self, response):
        for card in response.css("div.displaycards.touchup-date"):
            poster_page = card.css("a.small-title.text-underline-hover::attr(href)").get()
            title = card.css("a.small-title.text-underline-hover::text").get(default="").strip()
            authors = card.css("div.author-str::text").get(default="").strip().replace("·", ",")
            poster_type = card.css("div.type_display_name_virtual_card::text").get(default="").strip()

            # Abstract
            abstract_lines = card.css("details > div.text-start.p-4 *::text").getall()
            abstract = " ".join([line.strip() for line in abstract_lines if line.strip()])

            # 只抓 Spotlight Poster 不抓 Slides
            if "Spotlight Poster" in poster_type:
                yield scrapy.Request(
                    url=response.urljoin(poster_page),
                    callback=self.parse_poster,
                    meta={
                        "title": title,
                        "authors": authors,
                        "abstract": abstract
                    }
                )

    def parse_poster(self, response):
        title = response.meta["title"]
        authors = response.meta["authors"]
        abstract = response.meta["abstract"]

        # Poster 图片链接
        poster_links = response.css("a.href_Poster[title='Poster']::attr(href)").getall()
        if not poster_links:
            self.logger.warning(f"{response.url} NO Poster file")
            return

        # OpenReview 链接
        openreview_link = response.css("a.href_URL[title='OpenReview']::attr(href)").get(default="").strip()

        os.makedirs("posters", exist_ok=True)
        for link in poster_links:
            file_url = response.urljoin(link)
            file_name = file_url.split("/")[-1].split("?")[0]

            yield scrapy.Request(
                url=file_url,
                callback=self.save_poster,
                meta={
                    "file_name": file_name,
                    "page_url": response.url,
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "poster_url": file_url,
                    "openreview_url": openreview_link
                }
            )

    def save_poster(self, response):
        file_name = response.meta["file_name"]
        file_path = os.path.join("posters", file_name)
        with open(file_path, "wb") as f:
            f.write(response.body)
        self.logger.info(f"Downloaded: {file_name}")

        yield {
            "title": response.meta["title"],
            "authors": response.meta["authors"],
            "abstract": response.meta["abstract"],
            "poster_file": file_name,
            "poster_url": response.meta["poster_url"],
            "page_url": response.meta["page_url"],
            "openreview_url": response.meta["openreview_url"]
        }
