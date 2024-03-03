# InfiniteScrape

_Here, have my proxy code [@Pixelz22](https://github.com/Pixelz22)_

## What's this?

This code is meant to be a smart auto-rescheduling multithreaded scraper for Neal Agarwal's Infinite Craft
(https://neal.fun/infinite-craft).
I have been able to get it to reach upwards of 25 crafts/sec with just 5 workers running.
With actually good proxies, this could conceivably scale to hundreds, if not thousands, of crafts per second.

Currently, this project only has two folders: `backend` and `legacy`. 

`legacy` is me screwing around with proxies and web scraping, and shouldn't really be used.

`backend` is an incredibly good backend with high scalability. 


Here's some features of my backend:

* Threadsafe scheduling
* MongoDB support
* No queue.Queue() lol
* Automatic proxy ranking and scheduling
* Plain awesome

## Why would you spend your time on this?


 [@Pixelz22](https://github.com/Pixelz22) decided it was a good idea to compete with me. 

Here's his repository: https://github.com/Pixelz22/InfiniteCraft


## Some stuff I want to add

- MongoDB -> neal.fun encoder
- actual algorithm
- Dockerfile
- Tyler





