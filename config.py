import json

try:
    f = open('config.json')
    config = json.load(f)
except:
    print("config.json file not found. Searching for config_base.json instead...")
    try:
        f = open('config_base.json')
        config = json.load(f)
    except:
        print("WARNING!")
        print("Backup file (config_base.json) file not found. A config.json file is necessary for the bot to function.")


###################
### GLOBAL VARS ###
###################

# Discord bot token
discord_token = config[0]['discord_token']
if discord_token:
    print("Discord Bot token loaded.")
else:
    print("Discord Bot token not found.")

# OpenAI token
openai_token = config[0]['openai_token']
if openai_token:
    print("OpenAI API token loaded.")
else:
    print("OpenAI API token not found.")

# This is used primarily to determine the name of the server during setup
bot_name = config[0]['bot_name']
if bot_name:
    print("Bot name loaded.")
else:
    print("Bot name not found, defaulting to dGPT.")
    bot_name = "dGPT"

# This is used as authentication for the sync command. If you're independently hosting this bot, you 
# and other developers should be the only people in this list, as continuous syncing in a short
# time can lead to very harsh rate limits from Discord.
admin_list = config[0]['admin_list']
if admin_list:
    print(f"Admin list loaded: {admin_list}")
else:
    print(f"Admin list not found, you won't be able to sync app commands.")


##################
### LOCAL VARS ###
##################

# Custom instructions given to the bot to contextualize the conversation.
custom_instructions = config[1]['custom_instructions']
print(f"Custom instuctions loaded: \n    '{custom_instructions}'")