from sopel import plugin
from sopel.config import types

import datetime
import re
import requests
import secrets
import shelve
from selenium import webdriver

SETTINGS_FILENAME='/home/pi/.sopel/plugins/crossword_settings'
LAST_DATE_KEY='last_date'

DEFAULT_DATE=datetime.datetime.combine(datetime.date(2023, 4, 17), datetime.datetime.min.time())
NEWYORKER_CROSSWORD_BASE_URL='https://www.newyorker.com/puzzles-and-games-dept/crossword/'
NEWYORKER_CROSSWORD_REGEX=r'www\.newyorker\.com\/puzzles-and-games-dept\/crossword\/(\d{4})\/(\d{2})\/(\d{2})'

def set_last_date(date):
    with shelve.open(SETTINGS_FILENAME, writeback=True) as db:
        db[LAST_DATE_KEY] = date

def get_last_date():
    try:
        with shelve.open(SETTINGS_FILENAME) as db:
            return db[LAST_DATE_KEY]
    except:
        return DEFAULT_DATE

def get_crossword_url(date):
    return NEWYORKER_CROSSWORD_BASE_URL + date.strftime("%Y/%m/%d")

def get_shared_url(url):
    options = webdriver.ChromeOptions()
    options.binary_location = '/usr/lib/chromium-browser/chromedriver'
    options.add_argument("--headless")
    #options.add_argument("--no-sandbox")
    #options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    target_url = driver.find_element_by_css_selector('iframe:last').get_attribute('src')
    driver.get(target_url)
    driver.find_element_by_css_selector('.nav-social-play:first').click()
    driver.find_element_by_css_selector('.copy-social-link-button:first').click()
    shared_url = driver.execute_script('return navigator.clipboard.readText()')
    return shared_url

def set_next_crossword(bot, date):
    crossword_url = get_crossword_url(date)
    #shared_url = get_shared_url(crossword_url)
    bot.say(crossword_url + " " + date.strftime("(%A)"))
    set_last_date(date)

def is_valid_crossword_date(date):
    crossword_url = get_crossword_url(date)
    req = requests.get(crossword_url)
    return req.status_code == 200
    #return date.weekday() >= 0 and date.weekday() <= 4 

@plugin.url(NEWYORKER_CROSSWORD_REGEX)
@plugin.require_chanmsg('Channel only command.')
def register_crossword(bot, trigger):
    match = trigger.match
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    date = datetime.date(year, month, day)
    if is_valid_crossword_date(date):
        set_last_date(date)

@plugin.rule(r'^!cw prev$')
@plugin.require_chanmsg('Channel only command.')
def crossword_prev(bot, trigger):
    date = get_last_date() - datetime.timedelta(1)
    while not is_valid_crossword_date(date):
        date = date - datetime.timedelta(1)
    set_next_crossword(bot, date)

@plugin.rule(r'^!cw$')
@plugin.rule(r'^!cw next$')
@plugin.require_chanmsg('Channel only command.')
def crossword_next(bot, trigger):
    date = get_last_date() + datetime.timedelta(1)
    while not is_valid_crossword_date(date):
        date = date + datetime.timedelta(1)
    set_next_crossword(bot, date)
