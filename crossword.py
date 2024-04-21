# SPDX-License-Identifier: GPL-3.0-or-later
from sopel import plugin
from sopel.config import types

import datetime
import re
import requests
import secrets
import shelve
import urllib
import uuid
from selenium import webdriver

PLUGIN_BASE_DIR='/home/pi/.sopel/plugins'
SETTINGS_FILENAME=PLUGIN_BASE_DIR + '/crossword_settings'
LAST_DATE_KEY='last_date'
ALL_DATES_KEY='all_dates'

DEFAULT_DATE=datetime.datetime.combine(datetime.date(2023, 4, 17), datetime.datetime.min.time())
AMUSELABS_CDN_URL='https://cdn3.amuselabs.com/tny/crossword?set=tny-weekly&embed=1&compact=1&maxCols=2'
NEWYORKER_CROSSWORD_BASE_URL='https://www.newyorker.com/puzzles-and-games-dept/crossword/'
NEWYORKER_CROSSWORD_REGEX='((https?:\/\/)?www\.newyorker\.com)?\/puzzles-and-games-dept\/crossword\/(\d{4})\/(\d{2})\/(\d{2})'

def set_last_date(date):
    with shelve.open(SETTINGS_FILENAME, writeback=True) as db:
        db[LAST_DATE_KEY] = date

def get_last_date():
    try:
        with shelve.open(SETTINGS_FILENAME) as db:
            if not LAST_DATE_KEY in db:
                db[LAST_DATE_KEY] = DEFAULT_DATE
            return db[LAST_DATE_KEY]
    except:
        return DEFAULT_DATE

def get_crossword_dates():
    try:
        with shelve.open(SETTINGS_FILENAME, writeback=True) as db:
            if not ALL_DATES_KEY in db:
                db[ALL_DATES_KEY] = []
            return db[ALL_DATES_KEY]
    except:
        return []

def set_crossword_dates(dates):
    with shelve.open(SETTINGS_FILENAME, writeback=True) as db:
        db[ALL_DATES_KEY] = dates

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
    try:
        get_crossword_dates().index(date)
        return True
    except:
        return False

def extract_date_from_match(match):
    year = int(match.group(3))
    month = int(match.group(4))
    day = int(match.group(5))
    return datetime.date(year, month, day)

@plugin.rule(r"^!cw set " + NEWYORKER_CROSSWORD_REGEX + "$")
@plugin.require_chanmsg('Channel only command.')
def register_crossword(bot, trigger):
    date = extract_date_from_match(trigger.match)
    if is_valid_crossword_date(date):
        set_last_date(date)
    bot.say("Successfully set last crossword URL")

@plugin.rule(r'^!cw prev$')
@plugin.require_chanmsg('Channel only command.')
def crossword_prev(bot, trigger):
    dates = get_crossword_dates()
    idx = dates.index(get_last_date()) - 1
    if idx < 0:
        idx = 0
    set_next_crossword(bot, dates[idx])

@plugin.rule(r'^!cw$')
@plugin.rule(r'^!cw next$')
@plugin.require_chanmsg('Channel only command.')
def crossword_next(bot, trigger):
    dates = get_crossword_dates()
    idx = dates.index(get_last_date()) + 1
    if idx > len(dates) - 1:
        idx = len(dates) - 1
    set_next_crossword(bot, dates[idx])

@plugin.rule(r'^!lastcw$')
@plugin.rule(r'^!cw last$')
@plugin.require_chanmsg('Channel only command.')
def show_last_crossword(bot, trigger):
    date = get_last_date()
    url = get_crossword_url(date) 
    bot.say("Last crossword was: " + url + " " + date.strftime("(%A)"))

@plugin.rule(r'^!debugshare$')
def debug_share_url(bot, trigger):
    _crossword_url = get_crossword_url(get_last_date())
    _id = secrets.token_hex(4)
    _play_id = str(uuid.uuid4())
    _last_url = _crossword_url + "?id=" + _id + "&playId=" + _play_id
    _amuselabs_url = "https://cdn3.amuselabs.com/tny/postScore"
    _post_score_object = { 
        "updatePlayTable": False,
        "updateLoadTable": False,
        "series": "tny-weekly",
        "id": _id,
        "playId": _play_id,
        "userId": "99b711ad-17a4-4349-b830-1868a9db78fa",
        "browser": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0", 
        "getStreakStatsOfLen": 0,
        "getProgressFromBackend": False
    }
    req = requests.post(_amuselabs_url, json=_post_score_object)
    if req.status_code == 200:
        bot.say("Shared debug URL: " + _last_url)

@plugin.rule(r'^!reindex$')
def reindex(bot, trigger):
    reindex_crosswords(bot)

@plugin.rule(r'^!lastindex$')
def get_last_index(bot, trigger):
    last_date = get_crossword_dates()[-1]
    bot.say("Last indexed crossword was: " + last_date.strftime("%d.%m.%Y"))

@plugin.rule(r'^!todo')
def get_crosswords_until(bot, trigger):
    all_dates = get_crossword_dates()
    last_played_date = get_last_date()
    last_date = all_dates[-1]
    diff = all_dates.index(last_date) - all_dates.index(last_played_date)
    if diff > 0:
        bot.say("Roughly " + str(diff) + " crosswords to play")
    else:
        bot.say("You're all up-to-date!")

@plugin.interval(60 * 60 * 24)
def reindex_crosswords(bot):
    bot.say("Reindexing crosswords...", bot.settings.core.owner)

    idx = 1
    num_added = 0
    all_dates = get_crossword_dates()
    last_date = all_dates[-1]

    while True:
        req = requests.get(NEWYORKER_CROSSWORD_BASE_URL + "page/" + str(idx))
        if req.status_code != 200:
            break
        
        has_matches = False
        matches = re.finditer(NEWYORKER_CROSSWORD_REGEX, req.text)
        for match in matches:
            has_matches = True
            date = extract_date_from_match(match)
            if date == last_date:
                break

            try:
                all_dates.index(date)
            except ValueError:
                bot.say("Adding " + str(date), bot.settings.core.owner)
                all_dates.append(date)
                num_added += 1

        if not has_matches or date == last_date:
            break

        idx += 1

    all_dates.sort()
    set_crossword_dates(all_dates)
    if num_added > 0:
        bot.say("Successfully added " + str(num_added) + " crossword(s) to database")
    else:
        bot.say("Crosswords up-to-date! My database contains " + str(len(all_dates)) + " crosswords.")
