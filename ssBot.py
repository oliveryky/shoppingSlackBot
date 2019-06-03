import csv
import json
import os
import re
import requests
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from slackclient import SlackClient
slack_client = SlackClient(os.environ.get("SLACK_BOT_TOKEN"));

ssBot_id = None;

# 1sec delay between reading from RTM
RTM_READ_DELAY = 1;
#regex to match a direct mention to the bot at the beginning of a message
MENTION_REGEX = "^<@(|[WU].+?)>(.*)";
SEARCH = "search";

#features TBD
MONITOR = "monitor";
BUY = "buy";
DEFAULT_RESPONSE = "Please use one of the following commands: \n\t" + SEARCH + " using the format 'gender category brand color price'";

#checks a list of slack events from RTM for a bot command
# @return pair of the command and channel, or None pair if not a bot command
def parseCommands(slack_events):
    for event in slack_events:
        if (event["type"] == "message" and not "subtype" in event):
            user_id, message = checkDM(event["text"]);
            if(user_id == ssBot_id):
                return message.lower(), event["channel"];
    
    return None, None;

#finds a direct mention "@" that is at the beginning in the message
# @return user ID that mentioned the bot, or return None
def checkDM(message_text):
    matches = re.search(MENTION_REGEX, message_text);
    if(matches):
        return matches.group(1), matches.group(2).strip();
    
    return None, None;

def getTag(s, name):
    for tag in s.find_all("a"):
        if(tag.get_text().strip().lower() == name):
            return [tag.get_text().strip().lower(), tag.parent];
    return None;

def contains(w):
    return re.compile(r'\b({0})\b'.format(w), flags=re.IGNORECASE).search;

def postItem(itemName, itemUrl, itemBrand, itemPrice, imgUrl):
    itemBlock = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Found: " + itemName
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Link:* <" + itemUrl +"|"+ itemName + ">\n *Price:* " + itemPrice + " \n *Brand:* " + itemBrand
                        }
                    },
                    {
                        "type": "image",
                        "image_url": imgUrl,
                        "alt_text": "preview"
                    },
                    {
		                "type": "divider"
	                }
    ]
    
    slack_client.api_call(
        "chat.postMessage",
        channel = channel,
        blocks = itemBlock
    );

def writeToFile(query, url, soup, file, fileWriter):
    for item in soup.find("div", {"class": "browsing-product-list"}):
        if(query[4] == "#" or contains(query[4])(item.find("p", {"itemprop": "name"}).get_text())):
            itemBrand = item.find("p", {"itemprop": "brand"}).get_text();
            itemName = item.find("p", {"itemprop": "name"}).get_text().strip();
            itemPrice = item.find("p", {"class": "price"}).get_text();
            itemUrl = url + item.find("a")["href"];
            fileWriter.writerow([itemBrand, itemName, itemPrice, itemUrl]);
            imgUrl = item.find("img")["data-srcset"];
            print(imgUrl);
            postItem(itemName, itemUrl, itemBrand, itemPrice, imgUrl);
    
def search(command):
    command = command.split(" ", 1);
    if(len(command) != 2):
        print("len2");
        return None;
    
    query = command[1].split();
    if(len(query) != 6):
        return None;
    
    if(query[0] == "!"):
        query[0] = "men";
    
    url = "https://www.ssense.com";
    options = Options();
    options.headless = True;

    browser = webdriver.Firefox("/Users/oliveryu/Library/Application Support/Firefox/Profiles/28tkb6vr.default", options = options);
    browser.get(url);
    soup = BeautifulSoup(browser.page_source, 'lxml');

    for tag in soup.find_all("a"):
        if(tag.get_text().strip().lower() == query[0]):
            browser.get(url + tag["href"]);
            break;
    
    soup = BeautifulSoup(browser.page_source, 'lxml');
    if(query[1] != "#"):
        for tag in soup.find_all("a"):
            if(tag.get_text().strip().lower() == query[1]):
                browser.get(url + tag["href"]);
                break;

        soup = BeautifulSoup(browser.page_source, 'lxml');
        if(query[2] != "#"):
            parent = getTag(soup, query[1]);
            found = False;
            for link in parent[1].find("ul").find_all("a"):
                if(found):
                    break;
                if(link.get_text().strip().lower() == query[2]):

                    browser.get(url + link["href"]);
                    soup = BeautifulSoup(browser.page_source, 'lxml');
                    break;

                browser.get(url + link["href"]);
                subSoup = BeautifulSoup(browser.page_source, 'lxml');
                subParent = getTag(subSoup, link.get_text().strip().lower());
                for subLink in subParent[1].find("ul").find_all("a"):
                    subLinkText = subLink.get_text().strip().lower().replace(" ", "");
                    if(subLinkText == query[2]):
                        # source = requests.get(url + subLink["href"]).text;
                        # soup = BeautifulSoup(source, 'lxml');
                        browser.get(url + subLink["href"]);
                        soup = BeautifulSoup(browser.page_source, 'lxml');
                        found = True;
                        break;
    
    if(query[3] != "#"):
        for tag in soup.find("ul", {"id": "designer-list"}):
            tagText = tag.get_text().strip().lower().replace(" ", "");
            if(tagText == query[3]):
                browser.get(url + tag.find("a")["href"]);
                soup = BeautifulSoup(browser.page_source, 'lxml');
                break;
    
    file = open("webScrape.csv", "w");
    fileWriter = csv.writer(file);
    fileWriter.writerow(["Brand:", "Item:", "Price", "Link:"]);

    nav = soup.find("nav", {"aria-label": "Pagination"}).find("ul");
    if(nav is not None):
        lastIdx = soup.find("nav", {"aria-label": "Pagination"}).find("ul").find_all("li")[-1];

        while lastIdx.get_text() == "→":
            writeToFile(query, url, soup, file, fileWriter);
            print(url + lastIdx.find("a")["href"]);
            browser.get(url + lastIdx.find("a")["href"]);
            soup = BeautifulSoup(browser.page_source, 'lxml');
            lastIdx = soup.find("nav", {"aria-label": "Pagination"}).find("ul").find_all("li")[-1];
    else:
        writeToFile(query, url, soup, file, fileWriter);

    file.close();
    browser.quit();
    return "Search Complete!";

def runCommands(command, channel):
    response = None;
    print(command);

    if(command.startswith(SEARCH)):
        response = search(command);
    elif(command.startswith(MONITOR)):
        response = "This feature is not ready yet!";
    elif(command.startswith(BUY)):
        response = "This feature is not ready yet!";
    
    slack_client.api_call(
        "chat.postMessage",
        channel = channel,
        text = response or DEFAULT_RESPONSE
    );


if __name__ == "__main__":
    if(slack_client.rtm_connect(wiht_team_state = False)):
        print("ssBot connected and running!");
        #get ssBot's id from slack (web API method)
        ssBot_id = slack_client.api_call("auth.test")["user_id"];
        #run the bot
        while True:
            #read and parse the command
            command, channel = parseCommands(slack_client.rtm_read());
            
            #if valid command, run the bot
            if(command):
                runCommands(command, channel);

            #wait before reading again
            time.sleep(RTM_READ_DELAY);
else:
    print("Failed to connect...");