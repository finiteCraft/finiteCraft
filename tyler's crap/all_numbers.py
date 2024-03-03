import time
import selenium.webdriver.remote.webelement
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common import NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.support.wait import WebDriverWait

DRIVER: webdriver.Chrome | None = None
ELEMENTS: dict[str, selenium.webdriver.remote.webelement.WebElement] = {}


def find(element: str) -> None:
    id = "item-" + element
    wait = WebDriverWait(DRIVER, timeout=5, poll_frequency=0.2, ignored_exceptions=[NoSuchElementException])
    wait.until(lambda d: DRIVER.find_element(By.ID, id) or True)
    ELEMENTS[element] = DRIVER.find_element(By.ID, id)


def combine(element_one: str, element_two: str) -> None:
    if element_one not in ELEMENTS:
        find(element_one)
    if element_two not in ELEMENTS:
        find(element_two)
    wait = WebDriverWait(DRIVER, timeout=5, poll_frequency=0.2, ignored_exceptions=[ElementNotInteractableException])
    wait.until(lambda d: ELEMENTS[element_one].click() or True)
    wait.until(lambda d: ELEMENTS[element_two].click() or True)


def get_element_one() -> None:
    combine("Water", "Water")
    combine("Water", "Lake")
    combine("Earth", "Earth")
    combine("Mountain", "Ocean")
    combine("Fire", "Mountain")
    combine("Fire", "Volcano")
    combine("Lava", "Water")
    combine("Stone", "Stone")
    combine("Boulder", "Island")
    combine("Island", "Statue")
    combine("Island", "Statue of Liberty")
    combine("Fire", "New York")
    combine("9/11", "9/11")
    combine("9/22", "9/22")
    combine("18/44", "Fire")
    combine("22", "9/22")


if __name__ == "__main__":
    options = Options()
    DRIVER = webdriver.Chrome(options)

    DRIVER.implicitly_wait(1)

    DRIVER.get("https://neal.fun/infinite-craft/")

    try:
        sidebar = DRIVER.find_element(By.CLASS_NAME, "sidebar")

        DRIVER.set_window_size(0, 1000)
    except NoSuchElementException:
        print("we're in small mode")

    input("Press enter to continue...")

    get_element_one()

    input("Press enter to continue...")
    DRIVER.quit()
