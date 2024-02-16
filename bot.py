import discord
import typing
import os
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

def getCategory(member, catname):
    category = discord.utils.get(member.guild.categories, name=catname)
    return category

def getVoiceChannel(member, channelname):
    voice_channel = discord.utils.get(member.guild.voice_channels, name=channelname)
    return voice_channel

def getTextChannel(member, channelname):
    text_channel = discord.utils.get(member.guild.text_channels, name=channelname)
    return text_channel


# Performs a full server setup, intended for one-time use.
@bot.tree.command(name="setup", description="One-time use command that autonomously sets up the server for proper usage.")
async def setup(interaction: discord.Interaction):
    try:
        try:
            with open("dgpt logo1.png", 'rb') as f:
                logo = f.read()
            logofound = True
        except FileNotFoundError:
            logofound = False
            print("Guild logo file not located. Skipping over...")

        await interaction.guild.create_voice_channel("New Chat")
        await interaction.guild.create_voice_channel("Open Settings")
        await interaction.guild.create_category("Chats")
        await getCategory(interaction.user, "Chats").create_text_channel("general")

        await getTextChannel(interaction.user, "general").delete()
        await getVoiceChannel(interaction.user, "General").delete()
        await getCategory(interaction.user, "Text Channels").delete()
        await getCategory(interaction.user, "Voice Channels").delete()

        await interaction.guild.edit(name=bot_name)
        await interaction.guild.edit(default_notifications=discord.NotificationLevel.only_mentions)
        if logofound == True:
            await interaction.guild.edit(icon=logo)
        print("Setup successful!")
    except discord.errors.Forbidden:
        await interaction.channel.send("I don't have the permissions for that operation! Please give me a role with Administrator permissions and try again.")


@bot.tree.command(name='sync', description="Used to sync App Commands to all guilds. Usable by those in admin_list manually set by bot owner.")
async def sync(interaction: discord.Interaction):
    print(f"{interaction.user} used command sync")
    if str(interaction.user) in admin_list:
        await bot.tree.sync()
        print("App Commands successfully synced to all guilds.")
        await interaction.channel.send("App Commands successfully synced to all guilds.")
    else:
        print(f"{interaction.user} failed authorization check to sync guilds.")
        await interaction.channel.send("You aren't authorized to use this command.")


@bot.event
async def on_voice_state_update(member: discord.Member, before, after):
    # Check if the member joined the specific channel
    if before.channel != after.channel and after.channel is not None and after.channel.name == "New Chat":
        await member.move_to(None)
        print(f"{member} clicked 'New Chat'")
        thread = await getTextChannel(member, "general").create_thread(name="New Thread", type=discord.ChannelType.public_thread)
        message = await thread.send(member.mention)
        await message.edit(content="Awaiting prompt...")
        print(f"User {member.global_name} started a new chat with no prompt.")

        @bot.event
        async def on_message(message: discord.Message):
            if message.channel == thread:
                if message.author.name != bot_name:
                    await message.channel.send(content=f":hourglass:")
                    await thread.typing()
                    print(f"{message.author} provided prompt {message.content}")
        
    
    # Check if the member OPENED the Settings channel
    if before.channel != after.channel and after.channel is not None and after.channel.name == "Open Settings":
        await member.move_to(None)
        print(f"{member} clicked 'Open Settings'")
        await member.guild.create_category("Settings", position=0)
        await getCategory(member, "Settings").create_text_channel('settings')

        await getVoiceChannel(member, "Open Settings").delete()
        await member.guild.create_voice_channel("Close Settings")

        await getTextChannel(member, "settings").send("This is the settings menu. Right now there's nothing to see, but soon you'll be able to pick your GPT model, adjust the custom instructions, .")
    
    # Check if the member CLOSED the Settings channel
    if before.channel != after.channel and after.channel is not None and after.channel.name == "Close Settings":
        await member.move_to(None)
        print(f"{member} clicked 'Close Settings'")
        await getTextChannel(member, "settings").delete()
        await getCategory(member, "Settings").delete()
        
        await getVoiceChannel(member, "Close Settings").delete()
        await member.guild.create_voice_channel("Open Settings", position=1)

@bot.tree.command(name="new", description="Start a new chat with dGPT. Leave prompt empty if you'd like to specify it after chat creation.")
async def new_chat(interaction: discord.Interaction, prompt: typing.Optional[str]):
    global new_thread
    new_thread = True
    if prompt: # If prompt is given
        thread = await interaction.channel.create_thread(name=prompt, type=discord.ChannelType.public_thread)
        message = await thread.send(interaction.user.mention)
        response_message = await message.edit(content=f":hourglass:")
        await thread.typing()
        print(f"User {interaction.user} started a new chat with prompt: {prompt}")
        await interaction.response.send_message(thread.jump_url)

        print("Received message from user. Sending API call...")
        response = await getGPTResponse(message.channel, prompt)
        try:
            await response_message.edit(content=response)
        except Exception as error:
            await response_message.edit(content=error)
    else: # If no prompt is given
        thread = await interaction.channel.create_thread(name="New Thread", type=discord.ChannelType.public_thread)
        message = await thread.send(interaction.user.mention)
        waiting_message = await message.edit(content="Awaiting prompt...")
        print(f"User {interaction.user} started a new chat with no prompt.")
        await interaction.response.send_message(thread.jump_url)

# Responds to message in public threads
@bot.event
async def on_message(message: discord.Message):
    if message.channel.type == discord.ChannelType.public_thread:
        if not message.author.bot:
            print("Received message from user. Sending API call...")
            response_message = await message.channel.send(content=f":hourglass:")
            await message.channel.typing()
            response = await getGPTResponse(message.channel, None)
            await response_message.edit(content=response)
            


async def getGPTResponse(thread: discord.Thread, prompt: typing.Optional[str]):
    global chat_completion
    messages_list = []
    
    if prompt: # Checks if there is a prompt passed to append before iterating through the chat history.
        messages_list.append(
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
            messages_list.append(
                {
                    "role": "user", # User is sender of message
                    "content": message.content # Content of user's message
                }
            )
        else: # If bot message
            if message.content != ":hourglass:" and message.content != "Awaiting prompt...": # Ensures it's not a placeholer message being passed
                messages_list.append(
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
    ] + messages_list,
    model="gpt-4-turbo-preview",
    )

    output = (chat_completion.choices[0].message.content)
    output = formatGPTResponse(output)
    print("OpenAI API call received.")
    return output

async def formatGPTResponse(content):
    if content > 2000: # Checks if content is within character limit
        messages = []
        while len(content) > 0:
            # Split the content into a message of max_length or less
            message_part = content[:2000]
            # Update the remaining content
            content = content[2000:]
            # Append the message part to the messages list
            messages.append(message_part)
        return messages # Returns array of messages to be sent
    else:
        return content # Returns content


class ClearConfirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.edit_message(content="Clearing threads...", view=None)
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()


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
async def clear(interaction: discord.Interaction):
    interaction.response.send_message("This currently doesn't do anything and is yet to be coded.")
    return

@bot.tree.command(name="log", description="Saves a log of the thread as your choice of file.")
async def log(interaction: discord.Interaction):
    if interaction.channel.type == discord.ChannelType.public_thread:
        view=saveLogView()
        save_message = await interaction.response.send_message(f"Use the below dropdown to select a file type to save this chat log to: ", view=view)
        await view.wait()
    else:
        await interaction.response.send_message(f"Please use this command in a thread, not the main channel.")

# Command to start the bot.
bot.run(discord_token)