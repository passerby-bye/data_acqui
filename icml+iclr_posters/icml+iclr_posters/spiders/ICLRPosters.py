import scrapy
import os

class ICLRPosterSpider(scrapy.Spider):
    name = "ICLRPoster"
    allowed_domains = ["iclr.cc"]
    start_urls = [
        "https://iclr.cc/virtual/2025/papers.html?filter=session&search=Poster+Session+1"
    ]

    custom_settings = {
        "FEED_FORMAT": "json",
        "FEED_URI": "iclr_posters.json",
        "DOWNLOAD_DELAY": 0.5,
        "ROBOTSTXT_OBEY": True,
        "FEED_EXPORT_ENCODING": "utf-8",
    }

    def parse(self, response):
        # 获取母页面中所有子页面链接
        poster_links = response.css("li a::attr(href)").getall()
        for link in poster_links:
            url = response.urljoin(link)
            yield scrapy.Request(url, callback=self.parse_poster)

    def parse_poster(self, response):
        # Poster 图片链接
        poster_url = response.css("a.href_Poster[title='Poster']::attr(href)").get()
        if poster_url:
            poster_url = response.urljoin(poster_url)

            # 标题
            title = response.css("h2.card-title.main-title::text").get()
            if title:
                title = title.strip()

            # 作者
            authors = response.css("h3.card-subtitle.mb-2::text").get()
            if authors:
                authors = authors.strip()

            # 创建 posters 文件夹
            os.makedirs("posters", exist_ok=True)
            file_name = poster_url.split("/")[-1].split("?")[0]
            file_path = os.path.join("posters", file_name)

            # 下载 Poster
            yield scrapy.Request(
                url=poster_url,
                callback=self.save_poster,
                meta={
                    "title": title,
                    "authors": authors,
                    "page_url": response.url,
                    "poster_url": poster_url,
                    "file_path": file_path
                }
            )

    def save_poster(self, response):
        # 保存 Poster
        file_path = response.meta["file_path"]
        with open(file_path, "wb") as f:
            f.write(response.body)

        yield {
            "title": response.meta["title"],
            "authors": response.meta["authors"],
            "poster_url": response.meta["poster_url"],
            "poster_file": os.path.basename(file_path),
            "page_url": response.meta["page_url"]
        }
