# dGPT
dGPT is a bot that uses Discord as a substitute interface over ChatGPT, primarily for the purposes of using API pricing over a monthly subscription. Right now this is an open-source project for self-hosting, however I may be creating an independently-hosted version of the bot compatible with multiple guilds, which would be accessible for a fee. This possible version of the bot would *not* be open-source.

Depends on the `discord`, `typing`, and `os` modules.

## Commands
- **/setup**
    - Use *only once* once a "For me and my friends" server is created, without altering the server. This will restructure the server into the 
- **/new [prompt]**
    - Starts a new public thread with specified prompt. When left empty, the bot will await a prompt. This is helpful for long or multi-line prompts
- **/clear**
    - Deletes all active *and* archived threads.
- **/log**
    - Saves a log of the thread as either a text file or markdown file
- **/sync**
    - Usable only by those in a list of usernames set in the config.json file


## Should I use dGPT?
**YES**, if you want to:
- Input and output fewer than 250,000 words per month (otherwise purchase a subscription, it's more cost-effective)
- Use ChatGPT within Discord
- Host the bot for just yourself and friends
- Customize your experience of the bot

**NO**, if you want to:
- Host for multiple guilds on one bot instance
- Host on servers with people you don't trust
- Host on large servers
- Have a dedicated app or web interface for ChatGPT
- Send messages that exceed Discord's character limit without Nitro

## Setup process
1. Download all files
2. Rename `config_base.json` to `config.json` and open the file
3. Set the `openai_token` variable to your OpenAI API key and the `discord_token` variable to your Discord bot's token
4. Create a new server > "For me and my friends" > Give it any random name. *Do NOT change the preset layout*
5. Invite the bot and use /setup


## To Be Implemented
- Close thread command
- Settings page to change custom instructions, GPT model
- Setup given any server layout
- Custom server logo
- Read and respond to text files

## Known Issues
- Messages from dGPT over 2,000 characters will not send, and instead throw an error

