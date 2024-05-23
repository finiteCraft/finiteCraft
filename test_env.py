import js2py
from bs4 import BeautifulSoup, PageElement
from requests import Session, Response

class Jriver:
    def __init__(self):
        self.session = Session()
        self.response: Response | None = None
        self.context = js2py.EvalJs(enable_require=True)
        self.parent_url = "about:blank"

    def get(self, url: str, **kwargs):
        a = url.index("/", url.index("//") + 1)
        self.parent_url = url[:a]
        self.response = self.session.get(url, **kwargs)
        if "text/html" in self.response.headers["Content-Type"].split("; "):
            self.parse_html(self.response.text)

    def execute(self, js: str) -> any:
        return self.context.eval(js)


    def parse_html(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        to_defer = []
        for tag in soup.find_all("script"):
            try:
                # noinspection PyStatementEffect
                tag["defer"]
                to_defer.append(tag)
            except KeyError:
                self.execute_script_tag(tag)

        for tag in to_defer:
            self.execute_script_tag(tag)

    def execute_script_tag(self, script_tag: PageElement):
        try:
            src = script_tag["src"]
            if src[0] == '/':
                src_url = f"{self.parent_url}{src}"
            else:
                src_url = src

            response = self.session.get(src_url)
            self.execute(response.text)
        except KeyError:
            self.execute(script_tag.text)


if __name__ == "__main__":
    e = Jriver()
    print(e.execute("node"))
