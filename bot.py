import discord
import typing
import os
import asyncio
from discord.ext import commands
from discord import app_commands
from config import discord_token, openai_token, custom_instructions, bot_name, admin_list

import openai
from openai import OpenAI


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="//", intents=intents)

openai.api_key = openai_token
client = OpenAI(
    api_key=openai.api_key
)


@bot.event
async def on_ready(): # Do NOT include automatic bot syncing here. Liable to harsh rate-limits
    print(f'Logged in as {bot.user.name}')

def getCategory(interaction_user: discord.Interaction.user, category_name: str):
    category = discord.utils.get(interaction_user.guild.categories, name=category_name)
    return category

def getVoiceChannel(interaction_user: discord.Interaction.user, channel_name: str):
    voice_channel = discord.utils.get(interaction_user.guild.voice_channels, name=channel_name)
    return voice_channel

def getTextChannel(interaction_user: discord.Interaction.user, channel_name: str):
    text_channel = discord.utils.get(interaction_user.guild.text_channels, name=channel_name)
    return text_channel

class SetupConfirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.red)
    async def on_submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.edit_message(content="Setting up server...", view=None)
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = None
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()


# Performs a full server setup, intended for one-time use.
@bot.tree.command(name="setup", description="One-time use command that autonomously sets up the server for proper usage.")
async def setup(interaction: discord.Interaction):
    view = SetupConfirm()
    await interaction.response.send_message("Are you sure you want to set up the server for dGPT? This will **permanently delete all channels and categories.**", view=view)
    await view.wait()
    if view.value == True:
        try:
            try:
                with open("dgpt logo1.png", 'rb') as f:
                    logo = f.read()
                logofound = True
            except FileNotFoundError:
                logofound = False
                print("Guild logo file not located. Skipping over...")
            await interaction.guild.edit(name=bot_name)
            await interaction.guild.edit(default_notifications=discord.NotificationLevel.only_mentions)
            if logofound == True:
                await interaction.guild.edit(icon=logo)

            for category in interaction.guild.categories:
                await category.delete()
            for channel in interaction.guild.channels:
                await channel.delete()
                
            await interaction.guild.create_category("Chats")
            await getCategory(interaction.user, "Chats").create_text_channel("home")
            await getTextChannel(interaction.user, "home").edit(default_auto_archive_duration=60)

            
            print("Setup successful!")
            msg = await getTextChannel(interaction.user, "home").send("Setup successful!")
            await asyncio.sleep(5)
            await msg.delete()
        except discord.errors.Forbidden:
            await interaction.channel.send("I don't have the permissions for that operation! Please give me a role with Administrator permissions and try again.")

@bot.tree.command(name='sync', description="Used to sync App Commands to all guilds. Usable by those in admin_list manually set by bot owner.")
async def sync(interaction: discord.Interaction):
    print(f"{interaction.user} used command sync")
    if str(interaction.user) in admin_list:
        await bot.tree.sync()
        print("App Commands successfully synced to all guilds.")
        await interaction.response.send_message(content="App Commands successfully synced to all guilds.")
    else:
        print(f"{interaction.user} failed authorization check to sync guilds.")
        await interaction.response.send_message(content="You aren't authorized to use this command.")

@bot.tree.command(name="new", description="Start a new chat with dGPT. Leave prompt empty if you'd like to specify it after chat creation.")
async def new_chat(interaction: discord.Interaction, prompt: typing.Optional[str]):
    global new_thread
    new_thread = True
    if interaction.channel.type != discord.ChannelType.public_thread:
        if prompt: # If prompt is given
            try:
                thread = await interaction.channel.create_thread(name=prompt, type=discord.ChannelType.public_thread)
                message = await thread.send(interaction.user.mention)
                response_message = await message.edit(content=f":hourglass:")
                await thread.typing()
                print(f"User {interaction.user} started a new chat with prompt: {prompt}")
                await interaction.response.send_message("...")
                await interaction.delete_original_response()

                print("Received message from user. Sending API call...")
                response, withinCharLimit = await getGPTResponse(message.channel, prompt)
                if withinCharLimit == True:
                    await response_message.edit(content=response)
                else:
                    await response_message.edit(content=response[0])
                    for i in response[1:]:
                        await message.channel.send(content=i)
            except:
                await interaction.response.send_message(f"Prompt argument must be under 100 characters. Leave argument empty if you want to give a longer prompt.")

        else: # If no prompt is given
            thread = await interaction.channel.create_thread(name="New Thread", type=discord.ChannelType.public_thread)
            message = await thread.send(interaction.user.mention)
            waiting_message = await message.edit(content="Awaiting prompt...")
            print(f"User {interaction.user} started a new chat with no prompt.")
            await interaction.response.send_message(content="...")
            await interaction.delete_original_response()
    else:
        await interaction.response.send_message(content="New chats cannot be started in threads.")
        await asyncio.sleep(5)
        await interaction.delete_original_response()

# Responds to message in public threads
@bot.event
async def on_message(message: discord.Message):
    if message.channel.type == discord.ChannelType.public_thread:
        if not message.author.bot:
            print("Received message from user. Sending API call...")
            response_message = await message.channel.send(content=f":hourglass:")
            await message.channel.typing()
            response, withinCharLimit = await getGPTResponse(message.channel, None)
            if withinCharLimit == True: # Checks if the message fits within content limit
                await response_message.edit(content=response)
            else:
                await response_message.edit(content=response[0])
                for i in response[1:]:
                    await message.channel.send(content=i)


# Sends API call
async def getGPTResponse(thread: discord.Thread, prompt: typing.Optional[str]):
    global chat_completion
    message_history_list = []
    
    if prompt: # Checks if there is a prompt passed to append before iterating through the chat history.
        message_history_list.append(
            {
                "role": "user",
                "content": prompt
            }
        )
        if len(prompt) > 51: # Checks to truncate prompt
            print(f"Initial prompt passed from user: {prompt[0:51]}...")
        else:
            print(f"Initial prompt passed from user: {prompt}")
    async for message in thread.history(limit=None, oldest_first=True): # Grabs all messages in thread by iterating through chat history
        if not message.author.bot: # If user message
            message_history_list.append(
                {
                    "role": "user", # User is sender of message
                    "content": message.content # Content of user's message
                }
            )
        else: # If bot message
            if message.content != ":hourglass:" and message.content != "Awaiting prompt...": # Ensures it's not a placeholer message being passed
                message_history_list.append(
                    {
                    "role": "assistant", # Bot is sender of message
                    "content": message.content # Content of bot's message
                    }
                )
                print(f"Message grabbed from bot (self): {message.content[0:51]}...")

    
    chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": custom_instructions,
        }
    ] + message_history_list,
    model="gpt-4-turbo-preview",
    )

    output = (chat_completion.choices[0].message.content)
    output, withinCharLimit = await formatGPTResponse(output)
    print("OpenAI response received.")
    if withinCharLimit == False:
        print(f"Output outside of character limit, consists of {len(output)} messages.")
    else:
        print(f"Output within character limit.")
    return output, withinCharLimit

# Formats response of API call
async def formatGPTResponse(content):
    if len(content) <= 2000: # Checks if content is within character limit (2,000 or fewer)
        return content, True # Returns string, True = fits within character limit
    else:
        messages = []
        while len(content) > 0:
            # Split the content into a message of max_length or less
            message_part = content[:2000]
            # Update the remaining content
            content = content[2000:]
            # Append the message part to the messages list
            messages.append(message_part)
        return messages, False # Returns array of messages to be sent, False = doesn't fit within character limit



class ClearConfirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.edit_message(content="Clearing threads...", view=None)
        self.stop()
        await asyncio.sleep(5)
        await interaction.delete_original_response()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()
        await asyncio.sleep(5)
        await interaction.delete_original_response()

class saveLogDropdown(discord.ui.Select):
    def __init__(self):

        options = [
                discord.SelectOption(label='Text File', description='Saves as a .txt file.'),
                discord.SelectOption(label='Markdown File', description='Saves as a .md file.')
            ]
        
        super().__init__(placeholder="Select a file type...", min_values=1, max_values=1, options=options)
        

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "Text File":
            filename = f"logs/{interaction.channel_id}.txt"
            if not os.path.exists(filename):
                await interaction.response.edit_message(content=f'Saving log as .txt file...', view=None)
            else:
                f = open(filename, "w").close()
                await interaction.response.edit_message(content=f'Updating existing .txt file...', view=None)
            f = open(filename, "a")
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                f.write(f"[{message.author}]")
                f.write("\n")
                f.write(f"{message.content}")
                f.write("\n\n")
        
        elif self.values[0] == "Markdown File":
            filename = f"logs/{interaction.channel_id}.md"
            if not os.path.exists(filename):
                await interaction.response.edit_message(content=f'Saving log as .md file...', view=None)
            else:
                f = open(filename, "w").close()
                await interaction.response.edit_message(content=f'Updating existing .md file...', view=None)
            f = open(filename, "a")
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                f.write(f"## **{message.author}**")
                f.write("\n")
                f.write(f"{message.content}")
                f.write("\n\n")

    @discord.ui.button(label='Save Log', style=discord.ButtonStyle.green)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()

class saveLogView(discord.ui.View):
    def __init__(self):
        super().__init__()

        # Adds the dropdown to our view object.
        self.add_item(saveLogDropdown())

@bot.tree.command(name='clear', description="Deletes all active and archived threads.")
async def clear(interaction: discord.Interaction):
    view = ClearConfirm()
    threads_list = []
    archived_threads_list = []
    print(f"{interaction.user} used command clear")
    if interaction.channel.type == discord.ChannelType.public_thread:
        await interaction.response.send_message(content="Please use this command in the main channel, not a thread.")
    else:
        for i in interaction.channel.threads:
            threads_list.append(i.name)
        async for i in interaction.channel.archived_threads():
            archived_threads_list.append(i.name)
        
        if threads_list == [] and archived_threads_list == []:
            await interaction.response.send_message("There are no threads to clear.")
        else:
            confirm = await interaction.response.send_message(f":warning: Are you sure you want to irrecoverably delete the following threads? :warning:\n**Active Threads:** {threads_list}\n**Archived Threads:** {archived_threads_list}", view=view)
            await view.wait()
            if view.value is None:
                print('Timed out...')
            elif view.value:
                print('Clearing all threads...')
                for i in interaction.channel.threads:
                    await i.delete()
                async for i in interaction.channel.archived_threads():
                    await i.delete()
            else:
                print('Cancelling clear command...')

@bot.tree.command(name='close', description="Closes the current thread, archiving but not deleting.")
async def close(interaction: discord.Interaction):
    if interaction.channel.type == discord.ChannelType.public_thread:
        await interaction.response.send_message(content=":white_check_mark: Closed!")
        await interaction.channel.edit(archived=True)
    else:
        await interaction.response.send_message(content="This is not a public thread, and so it can't be closed.")
    # interaction.response.send_message("This currently doesn't do anything and is yet to be coded.")
    return

@bot.tree.command(name="log", description="Saves a log of the thread as your choice of file.")
async def log(interaction: discord.Interaction):
    if interaction.channel.type == discord.ChannelType.public_thread:
        view=saveLogView()
        save_message = await interaction.response.send_message(f"Use the below dropdown to select a file type to save this chat log to: ", view=view)
        await view.wait()
    else:
        await interaction.response.send_message(f"Please use this command in a thread, not the main channel.")

@bot.tree.command(name="settings", description="Opens settings menu in new channel")
async def settings(interaction: discord.Interaction):
    if await getCategory(interaction.user, "Settings") != True:
        await interaction.guild.create_category("Settings", position=0)
        await getCategory(interaction.user, "Settings").create_text_channel('settings')
        await getTextChannel(interaction.user, "settings").send("This is the settings menu. Right now there's nothing to see, but soon you'll be able to pick your GPT model, adjust the custom instructions, .")

# Command to start the bot.
bot.run(discord_token)