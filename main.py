import argparse
import os
import re
import shutil

import discord
import asyncio
import json
from PIL import Image, ImageDraw, ImageFont
from random import sample
from discord.ext import commands

# Define intents and create bot with command prefix
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents, case_insensitive=True)

def read_sheet(path):
    expansion = None
    clues = []
    with open(path, 'r') as infile:
        for line in infile:
            if line.startswith("#"):
                expansion = line[1:].strip()
            else:
                clues.append(line.strip())
    return expansion, clues

def get_server_directory(guild_id):
    return f"servers/{guild_id}"

def get_settings_file(guild_id):
    return os.path.join(get_server_directory(guild_id), "settings.json")

def get_clues_file(guild_id):
    return os.path.join(get_server_directory(guild_id), "clues.txt")

def get_bingo_sheets_directory(guild_id):
    return os.path.join(get_server_directory(guild_id), "bingo_sheets")

def ensure_server_directories(guild_id):
    server_dir = get_server_directory(guild_id)
    bingo_sheets_dir = get_bingo_sheets_directory(guild_id)
    clues_file = get_clues_file(guild_id)

    os.makedirs(server_dir, exist_ok=True)
    os.makedirs(bingo_sheets_dir, exist_ok=True)
    if not os.path.exists(clues_file):
        shutil.copyfile("clues.txt", clues_file)

def load_settings(settings_file):
    try:
        with open(settings_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "free_space_enabled": False,
            "bingo_role": "Bingo Master",
            "users": {}
        }

def save_settings(settings_file, settings):
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)

def check_bingo(clues):
    size = 5  # Bingo board is always 5x5
    board = [clues[i:i+size] for i in range(0, len(clues), size)]  # Create a 5x5 board

    # Check rows for Bingo
    for row in board:
        if all(clue.endswith(" X") for clue in row):
            return True

    # Check columns for Bingo
    for col in range(size):
        if all(board[row][col].endswith(" X") for row in range(size)):
            return True

    # Check diagonals for Bingo
    if all(board[i][i].endswith(" X") for i in range(size)) or \
       all(board[i][size-i-1].endswith(" X") for i in range(size)):
        return True

    return False

def bingo_declared(user_bingo_file):
    bingo_marker = "# BINGO DECLARED"
    with open(user_bingo_file, 'r') as f:
        lines = f.readlines()

    if bingo_marker in lines:
        return True  # Bingo has already been declared

    # Append the marker and save the file
    with open(user_bingo_file, 'a') as f:
        f.write(f"{bingo_marker}\n")

    return False

@bot.event
async def on_guild_join(guild):
    ensure_server_directories(guild.id)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        ensure_server_directories(guild.id)
    print(f"Bot is ready and connected to {len(bot.guilds)} server(s).")

@bot.command(name="setMaroClues", help="Set clues for the upcoming expansion.")
async def set_maro_clues(ctx):
    guild_id = ctx.guild.id
    ensure_server_directories(guild_id)
    clues_file = get_clues_file(guild_id)
    settings = load_settings(f"{guild_id}/settings.json")
    bingo_role = settings["bingo_role"]

    # Check if the user has administrator permissions or bingo role
    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)
    if not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("You need to be an administrator or have the Bingo Master role to set the clues.")
        return

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    await ctx.send("Please provide the clues for the upcoming expansion...")

    try:
        user_response = await bot.wait_for('message', check=check, timeout=60.0)
        clues = [line.strip() for line in user_response.content.splitlines() if line.strip()]

        if not clues[0].startswith("#"):
            await ctx.send("Make sure to start with a # followed by the expansion name")
            return
        if len(clues) < 25:
            await ctx.send("You must provide at least 24 clues. Please try again.")
            return

        with open(clues_file, 'w', encoding='utf-8') as outfile:
            for clue in clues:
                outfile.write(f"{clue}\n")

        await ctx.send("Clues have been successfully updated!")

    except asyncio.TimeoutError:
        await ctx.send("You took too long to respond. Please try again.")

@bot.command(name="resetMaroClues", help="Sets clues to the server's default")
async def reset_maro_clues(ctx):
    guild_id = ctx.guild.id

    settings = load_settings(f"{guild_id}/settings.json")
    bingo_role = settings["bingo_role"]

    # Check if the user has administrator permissions or bingo role
    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)
    if not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("You need to be an administrator or have the Bingo Master role to set the clues.")
        return

    ensure_server_directories(guild_id)
    clues_file = get_clues_file(guild_id)

    shutil.copyfile("clues.txt", clues_file)

@bot.command(name="listMaroClues", help="List all clues")
async def list_maro_clues(ctx):
    guild_id = ctx.guild.id
    clues_file = get_clues_file(guild_id)
    if not os.path.exists(clues_file):
        await ctx.send("No clues file found for this server. Please set clues using `/setMaroClues`.")
        return
    expansion, clues = read_sheet(clues_file)
    clues_text = "\n".join(clues)
    await ctx.send(f"**Clues for {expansion}:**\n```{clues_text}```")

@bot.command(name="createBingoSheet", help="Create a new BINGO sheet for yourself or another user.")
async def create_bingo_sheet(ctx, target_user: discord.Member = None):
    guild_id = ctx.guild.id
    ensure_server_directories(guild_id)
    clues_file = get_clues_file(guild_id)
    bingo_sheets_dir = get_bingo_sheets_directory(guild_id)
    settings_file = get_settings_file(guild_id)
    settings = load_settings(settings_file)
    free_space = settings.get("free_space_enabled", False)
    bingo_role = settings.get("bingo_role", "Bingo Master")
    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)

    user = target_user if target_user else ctx.author
    user_bingo_file = os.path.join(bingo_sheets_dir, f"{user.id}.txt")

    if target_user and not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("You need admin or Bingo Master role to create sheets for others.")
        return

    if not os.path.exists(clues_file):
        await ctx.send("No clues file found. Please set clues using `/setMaroClues`.")
        return

    expansion, clues = read_sheet(clues_file)

    if os.path.exists(user_bingo_file):
        user_expansion, user_clues = read_sheet(user_bingo_file)
        if user_expansion == expansion:
            await ctx.send(f"{user.mention} already has a bingo sheet for '{expansion}'. Overwrite? (yes/no)")
            response = await bot.wait_for("message", timeout=30.0)
            if response.content.lower() != "yes":
                await ctx.send("Creation canceled.")
                return

    clue_selection = sample(clues, 25)
    if free_space:
        clue_selection[12] = "Free"

    with open(user_bingo_file, 'w') as outfile:
        outfile.write(f"# {expansion}\n")
        for c in clue_selection:
            outfile.write(c + "\n")

    await ctx.send(f"Bingo sheet created for {user.mention}.")
    await view_bingo_sheet(ctx, user)

@bot.command(name="viewBingoSheet", help="View your BINGO sheet", aliases=["viewBingoCard"])
async def view_bingo_sheet(message, target_user: discord.Member = None):
    guild_id = message.guild.id
    user = target_user if target_user else message.author
    bingo_sheets_dir = get_bingo_sheets_directory(guild_id)
    user_bingo_file = os.path.join(bingo_sheets_dir, f"{user.id}.txt")

    # Check if the user has a bingo sheet
    if not os.path.exists(user_bingo_file):
        await message.channel.send("You don't have a bingo sheet yet. Use `/createBingoSheet` to create one.")
        return

    # Read the user's bingo sheet clues
    expansion, clues = read_sheet(user_bingo_file)

    # Ensure we have exactly 25 clues
    if len(clues) != 25:
        await message.channel.send("Your bingo sheet data is incomplete.")
        return

    img_size = 600
    cell_size = 100
    label_offset = 50
    img = Image.new('RGB', (img_size, img_size), color='white')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 15)
    except IOError:
        font = ImageFont.load_default()

    column_labels = ['A', 'B', 'C', 'D', 'E']
    for i, label in enumerate(column_labels):
        text_x = label_offset + i * cell_size + (cell_size // 2)
        text_y = label_offset // 2
        draw.text((text_x, text_y), label, fill="black", font=font, anchor="mm")

    row_labels = ['1', '2', '3', '4', '5']
    for i, label in enumerate(row_labels):
        text_x = label_offset // 2
        text_y = label_offset + i * cell_size + (cell_size // 2)
        draw.text((text_x, text_y), label, fill="black", font=font, anchor="mm")

    def wrap_text(text, font, max_width):
        """Wrap text to fit within the specified width."""
        lines = []
        words = text.split()
        current_line = ""

        for word in words:
            # Check if the word fits on the current line
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]  # Bounding box width

            if width <= max_width:
                current_line = test_line  # Add word to current line
            else:
                if current_line:  # Push current line to list
                    lines.append(current_line)
                current_line = word  # Start new line with the current word

        # Add any remaining text
        if current_line:
            lines.append(current_line)

        return lines

    def adjust_font_size(text, font, max_width, max_height):
        """Adjust the font size to make sure the text fits within the specified max width and height."""
        original_font = font
        font_size = font.size
        adjusted_font = font

        # Try different font sizes until the text fits
        while True:
            wrapped_text = wrap_text(text, adjusted_font, max_width)
            total_height = sum([draw.textbbox((0, 0), line, font=adjusted_font)[3] for line in wrapped_text])

            if total_height <= max_height:  # Text fits vertically
                # Check if it fits horizontally as well
                max_line_width = max([draw.textbbox((0, 0), line, font=adjusted_font)[2] -
                                      draw.textbbox((0, 0), line, font=adjusted_font)[0] for line in wrapped_text])
                if max_line_width <= max_width:  # Fits horizontally and vertically
                    break

            # If not, reduce font size
            font_size -= 1
            if font_size <= 5:  # Limit font size to a reasonable minimum
                adjusted_font = original_font
                break
            adjusted_font = ImageFont.truetype("DejaVuSans.ttf", font_size)

        return adjusted_font, wrapped_text

    # Draw the grid and clues with crossed-out marks if needed
    for i in range(5):
        for j in range(5):
            x = label_offset + j * cell_size
            y = label_offset + i * cell_size

            clue_index = i * 5 + j
            clue = clues[clue_index]
            text = clue.replace(" X", "")  # Remove " X" if present for display

            # Sanitize problematic characters
            text = text.replace("\u201c", '"').replace("\u201d", '"')

            draw.rectangle([x, y, x + cell_size, y + cell_size], outline="black", width=2)

            adjusted_font, wrapped_text = adjust_font_size(text, font, cell_size - 10, cell_size - 10)

            # Calculate the total height of the wrapped text
            total_height = sum([draw.textbbox((0, 0), line, font=adjusted_font)[3] for line in wrapped_text])

            # Start drawing text at the top of the cell, centered
            current_y = y + (cell_size - total_height) / 2

            for line in wrapped_text:
                bbox = draw.textbbox((0, 0), line, font=adjusted_font)  # Get bounding box of the line
                text_width = bbox[2] - bbox[0]
                text_x = x + (cell_size - text_width) / 2
                draw.text((text_x, current_y), line, fill="black", font=adjusted_font)
                current_y += bbox[3] - bbox[1]  # Move to the next line, using the bounding box height

            # If the clue is crossed off, draw a red cross
            if clue.endswith(" X"):
                draw.line([x, y, x + cell_size, y + cell_size], fill="red", width=3)
                draw.line([x + cell_size, y, x, y + cell_size], fill="red", width=3)

    image_path = f"servers/{guild_id}/temp_bingo_{user.id}.png"
    img.save(image_path)

    with open(image_path, "rb") as f:
        picture = discord.File(f)
        await message.channel.send(f"{user.name}'s Bingo Sheet for '{expansion}'", file=picture)

    os.remove(image_path)

@bot.command(name="cross", help="Cross off a cell on your BINGO sheet")
async def cross_off_square(ctx, square: str, target_user: discord.Member = None):
    guild_id = ctx.guild.id
    bingo_sheets_dir = get_bingo_sheets_directory(guild_id)

    settings_file = get_settings_file(guild_id)
    settings = load_settings(settings_file)
    bingo_role = settings.get("bingo_role", "Bingo Master")
    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)

    user = target_user if target_user else ctx.author
    user_bingo_file = os.path.join(bingo_sheets_dir, f"{user.id}.txt")

    user_settings = settings["users"].get(str(user.id), {"bingo_declared": False})

    if target_user and not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("You need admin or Bingo Master role to cross off cells for others.")
        return

    if not os.path.exists(user_bingo_file):
        if target_user:
            await ctx.send(f"{user.name} does not have a bingo sheet yet. Use `/createBingoSheet` to create one.")
        else:
            await ctx.send(f"You don't have a bingo sheet yet. Use `/createBingoSheet` to create one.")
        return

    match = re.match(r'([A-E][1-5])', square.upper())
    if not match:
        await ctx.send("Please specify a valid square (e.g., `/cross B3`).")
        return

    square_id = match.group(1)
    col_letter = square_id[0]
    row_number = int(square_id[1])

    column_index = ord(col_letter) - ord('A')
    row_index = row_number - 1
    clue_index = row_index * 5 + column_index

    expansion, clues = read_sheet(user_bingo_file)

    if clue_index >= len(clues):
        await ctx.send("Invalid square. Please check your input.")
        return

    if clues[clue_index].endswith(" X"):
        await ctx.send("This square is already crossed off.")
        return

    clues[clue_index] += " X"

    with open(user_bingo_file, 'w') as outfile:
        outfile.write(f"# {expansion}\n")
        outfile.write("\n".join(clues) + "\n")

    if check_bingo(clues) and not user_settings.get("bingo_declared", False):
        await ctx.send(f"BINGO! Congratulations {user.name}")
        user_settings["bingo_declared"] = True
        settings["users"][str(user.id)] = user_settings
        save_settings(settings_file, settings)

    await view_bingo_sheet(ctx, target_user = user)


@bot.command(name="uncross", help="Remove a previously set cross")
async def uncross_square(ctx, square: str, target_user: discord.Member = None):
    guild_id = ctx.guild.id
    bingo_sheets_dir = get_bingo_sheets_directory(guild_id)

    settings_file = get_settings_file(guild_id)
    settings = load_settings(settings_file)
    bingo_role = settings.get("bingo_role", "Bingo Master")
    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)

    user = target_user if target_user else ctx.author
    user_bingo_file = os.path.join(bingo_sheets_dir, f"{user.id}.txt")

    if target_user and not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("You need admin or Bingo Master role to uncross cells for others.")
        return

    if not os.path.exists(user_bingo_file):
        if target_user:
            await ctx.send(f"{user.name} does not have a bingo sheet yet. Use `/createBingoSheet` to create one.")
        else:
            await ctx.send(f"You don't have a bingo sheet yet. Use `/createBingoSheet` to create one.")
        return

    match = re.match(r'([A-E][1-5])', square.upper())
    if not match:
        await ctx.send("Please specify a valid square (e.g., `/cross B3`).")
        return

    square_id = match.group(1)
    col_letter = square_id[0]
    row_number = int(square_id[1])

    column_index = ord(col_letter) - ord('A')
    row_index = row_number - 1
    clue_index = row_index * 5 + column_index

    expansion, clues = read_sheet(user_bingo_file)

    if clue_index >= len(clues):
        await ctx.send("Invalid square. Please check your input.")
        return

    if not clues[clue_index].endswith(" X"):
        await ctx.send("This square was not crossed off.")
        return

    clues[clue_index] = clues[clue_index][:-2]

    with open(user_bingo_file, 'w') as outfile:
        outfile.write(f"# {expansion}\n")
        outfile.write("\n".join(clues) + "\n")

    await view_bingo_sheet(ctx, target_user=user)


@bot.command(name="freeSpace", help="Make middle spaces free")
async def free_space_on(ctx, toggle: str):
    guild_id = ctx.guild.id
    settings_file = get_settings_file(guild_id)
    settings = load_settings(settings_file)
    bingo_role = settings["bingo_role"]

    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)
    if not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("You need to be an administrator to change settings.")
        return

    # Check if the toggle input is valid
    toggle = toggle.lower()
    if toggle == "on":
        settings["free_space_enabled"] = True
        await ctx.send("The middle free space has been enabled.")
    elif toggle == "off":
        settings["free_space_enabled"] = False
        await ctx.send("The middle free space has been disabled.")
    else:
        await ctx.send("Invalid option. Use '/freeSpace on' to enable or '/freeSpace off' to disable.")
        return

    save_settings(settings_file, settings)

@bot.command(name="setRoleName", help="Set role name")
async def set_role_name(ctx, role_name: str):
    guild_id = ctx.guild.id
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need to be an administrator to change settings.")
        return

    settings_file = get_settings_file(guild_id)
    settings = load_settings(settings_file)
    settings["bingo_role"] = role_name
    save_settings(settings_file, settings)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--token', type=str, help='the bot token', default=None)
    args = parser.parse_args()

    if not args.token:
        token = os.getenv('DISCORD_BOT_TOKEN')
    else:
        token = args.token

    bot.run(token)

if __name__ == "__main__":
    main()
