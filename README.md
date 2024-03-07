# finiteCraft

_Here, have my proxy code [@Pixelz22](https://github.com/Pixelz22)_

&mdash; _[@quantumbagel](https://github.com/quantumbagel)_
  
**Why thank you, kind sir**  
&mdash; _[@Pixelz22](https://github.com/Pixelz22)_

## What's this?

This code is meant to be a conglomerate of all tools you could think of needing for mastering
Neal Agarwal's Infinite Craft (https://neal.fun/infinite-craft). Up until now, these tools have
been scattered across various repos and profiles, so we finally decided to bring them all together
into one omniscient entity.

**The benefits of our system:**
- a smart auto-rescheduling multi-threaded scraper to search for recipes and elements
- a constantly growing database easily accessible through the website
- a tree searcher that finds the most optimal way to craft any element, using the
  least number of elements and crafting steps
- No queue.Queue() lol
- Loading your own progress on infinite craft into the tree searcher
- Plain Awesome.


## About the Developers
&minus; _[@Pixelz22](https://github.com/Pixelz22)_:   
The original developer of this project. The work for this started on 
[his own repo](https://github.com/Pixelz22/InfiniteTree) back when this was just
a small personal project. Pretty soon he challenged the other developer, a good friend of his,
to work on this project, which is  where it really started to kick off. Finally, we discovered
that there was another group out of Waterloo working on a nearly identical project. That's when this became a war.  

&minus; _[@quantumbagel](https://github.com/quantumbagel)_:  
Pixelz might have been the original developer, but Quantum kicked it into high gear.
He has pioneered the scraping side of this project, creating the best scraper for InfiniteCraft
currently out there. He single-handedly built the proxy scraper and rescheduling system from the
ground up to get around InfiniteCraft's rate limiter. He's given it multi-threading, interfacing
with MongoDB, and so much more. The scraper now averages around 25-30 crafts a second.
He has, without a doubt, hard-carried this project.



## TODO LIST:

- [ ] Autocrafter
  - [x] Proxy Scraper
    - [x] Searches multiple proxy sources
  - [x] Proxy management
    - [x] Keep track of which proxies are successful and which aren't
    - [x] automatically cycles through proxies that are unreliable
    - [x] reschedules proxies that have been temp-blocked by neal.fun to be used later
  - [ ] Multi-threaded Workers searching for crafting recipes
    - [x] Probes InfiniteCraft through sessioned GET requests
    - [x] Sends packets of multiple requests at once to make up for slow proxies
    - [ ] Order of recipes searched stays the same when, even if threads finish out of order
  - [ ] Storage of elements and recipe info
    - [ ] Stores element info in a map from numerical key to element info.  
      Should store element's
      - Name
      - Emoji
      - Depth
      - Whether it was discovered by the bot or not
      - list of recipes that this element is used in, formatted with the
        other ingredient and result.
    - [ ] Store recipes in map
      - Maps from element key to a list of all recipes that make that element,
        each stored as a tuple of the two ingredient keys
  - [ ] Exports data to GitHub repository
    - Use of subprocess commands to interact with Git
    - [ ] Chunking
  - [ ] API for accessing information from the repo
    - [ ] Interfaces with chunking
    - [ ] User can get element info
    - [ ] User can get recipe info


- [ ] Arborist
  - [x] Basic tree generation
  - [x] Naive search function
  - [x] Basic pruning based on breadcrumb count
  - [ ] Pulls recipes using Autocrafter API
  - [ ] Recipe scoring function
    - [ ] Uses max depth of the ingredients
    - [ ] Try prioritizing recipes that make use of already crafted elements
    - [ ] Come up with other ideas
  - [ ] Order recipes during search using scoring function
  - [ ] Timeout option to cancel search early
  - [ ] Research other means of optimization


- [ ] Website Frontend
  - [ ] Scrollable list of elements 
  - [ ] Search bar for elements
  - [ ] Element display:
    - [ ] All recipes that result in that element
    - [ ] All recipes that use that element
    - [ ] A basic crafting tree
    - [ ] Option for generating a more optimal tree with a search timeout
  - [ ] Ability to load InfiniteCraft save data from user's cookies
    - [ ] Option to use this save data to affect tree generation
    - Maybe an option to show the next crafts available to the user?
  - [ ] Links to github profiles and repos, because who doesn't like
        a little shameless self promotion?


- [ ] Tyler


