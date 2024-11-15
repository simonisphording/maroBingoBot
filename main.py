import argparse
import os
import re
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

settings_file = "settings.json"
free_space = True
bingo_role = "Bingo Master"

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

def load_settings():
    try:
        with open(settings_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"free_space_enabled": False, "bingo_role": "Bingo Master"}

def save_settings(settings):
    with open(settings_file, "w") as f:
        json.dump(settings, f)

@bot.command(name="setMaroClues", help="Set clues for the upcoming expansion.")
async def set_maro_clues(ctx):
    # Check if the user has administrator permissions or bingo role
    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)

    if not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("You need to be an administrator to set the clues.")
        return

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    # Prompt the user to provide clues
    await ctx.send("Please provide the clues for the upcoming expansion. The clues should be formatted as follows:\n\\# [Expansion name]\n[Clue 1]\n[Clue 2]\n\nFor example:\n\\# Foundations (FDN)\n3 dragon cards\nBoth monocolor reprints, each of a different color, that together win you the game\n1/1 white Rabbit token")

    try:
        # Collect the clues from the user's message (with a timeout of 60 seconds)
        user_response = await bot.wait_for('message', check=check, timeout=60.0)

        # Split the clues by newlines and filter out empty lines
        clues = [line.strip() for line in user_response.content.splitlines() if line.strip()]

        if not clues[0].startswith("#"):
            await ctx.send("Make sure to start with a # followed by the expansion name")
            return
        if len(clues) < 25:
            await ctx.send("You must provide at least 24 clues. Please try again.")
            return

        # Save the clues to the file
        with open('clues.txt', 'w', encoding='utf-8') as outfile:
            for clue in clues:
                outfile.write(f"{clue}\n")

        await ctx.send("Clues have been successfully updated!")

    except asyncio.TimeoutError:
        await ctx.send("You took too long to respond. Please try again.")

@bot.command(name="listMaroClues", help="List all clues")
async def list_maro_clues(ctx):
    expansion, clues = read_sheet("clues.txt")
    clues_text = "\n".join(clues)
    await ctx.send(f"**Clues for {expansion}:**\n```{clues_text}```")

@bot.command(name="createBingoSheet", help="Create a new BINGO sheet for yourself or another user (Admins only).")
async def create_bingo_sheet(ctx, target_user: discord.Member = None):
    # Determine the user for whom to create the bingo sheet
    user = target_user if target_user else ctx.author
    user_bingo_file = f"bingo_sheets/{user.id}.txt"

    # Check if the command is invoked by an admin when targeting another user
    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)
    if target_user and not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("Only administrators can create a bingo sheet for other users.")
        return

    # Read clues from 'clues.txt'
    if not os.path.exists("clues.txt"):
        await ctx.send("No clues file found. Please set clues using `/setMaroClues`.")
        return

    expansion, clues = read_sheet("clues.txt")

    # Warn if user already has a sheet for the same expansion
    if os.path.exists(user_bingo_file):
        user_expansion, user_clues = read_sheet(user_bingo_file)
        if user_expansion == expansion:
            if target_user:
                await ctx.send(
                    f"{user.mention}, already has a bingo sheet for '{expansion}'. "
                    "Would you like to overwrite it? Reply with 'yes' to confirm, or 'no' to cancel."
                )
            else:
                await ctx.send(
                    f"{user.mention}, you already have a bingo sheet for '{expansion}'. "
                    "Would you like to overwrite it? Reply with 'yes' to confirm, or 'no' to cancel."
                )

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]

            try:
                response = await bot.wait_for("message", check=check, timeout=30.0)
                if response.content.lower() != "yes":
                    await ctx.send("Bingo sheet creation canceled.")
                    return
            except asyncio.TimeoutError:
                await ctx.send("No response received. Bingo sheet creation canceled.")
                return

    # Select random clues
    clue_selection = sample(clues, 25)

    # Set middle to free if applicable
    if free_space:
        clue_selection[12] = "Free"

    # Save the new bingo sheet
    with open(user_bingo_file, 'w') as outfile:
        outfile.write(f"# {expansion}\n")
        for c in clue_selection:
            outfile.write(c + "\n")

    # Notify the creation
    if target_user:
        await ctx.send(f"Bingo sheet created for {user.mention}.")
    else:
        await ctx.send(f"{user.mention}, your new bingo sheet has been created.")

    # Display the newly created bingo sheet
    await view_bingo_sheet(ctx, user)

@bot.command(name="viewBingoSheet", help="View your BINGO sheet")
async def view_bingo_sheet(message, target_user: discord.Member = None):
    user = target_user if target_user else message.author
    user_bingo_file = f"bingo_sheets/{user.id}.txt"

    # Check if the user has a bingo sheet
    if not os.path.exists(user_bingo_file):
        await message.channel.send("You don't have a bingo sheet yet. Use `/createBingoSheet` to create one.")
        return

    # Read the user's bingo sheet clues
    with open(user_bingo_file, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()
        expansion = lines[0][2:].strip()  # Get the expansion title
        clues = [line.strip() for line in lines[1:]]

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

    image_path = f"temp_bingo_{user.id}.png"
    img.save(image_path)

    with open(image_path, "rb") as f:
        picture = discord.File(f)
        await message.channel.send(f"{user.mention}'s Bingo Sheet for '{expansion}'", file=picture)

    os.remove(image_path)

@bot.command(name="cross", help="Cross off a cell on your BINGO sheet")
async def cross_off_square(ctx, square: str):
    user_bingo_file = f"bingo_sheets/{ctx.author.id}.txt"

    if not os.path.exists(user_bingo_file):
        await ctx.send("You don't have a bingo sheet yet. Use `/createBingoSheet` to create one.")
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

    await view_bingo_sheet(ctx)

@bot.command(name="freeSpace", help="Make middle spaces free")
async def free_space_on(ctx, toggle: str):
    has_bingo_role = discord.utils.get(ctx.author.roles, name=bingo_role)
    if not (ctx.author.guild_permissions.administrator or has_bingo_role):
        await ctx.send("You need to be an administrator to change settings.")
        return

    global free_space

    # Check if the toggle input is valid
    toggle = toggle.lower()
    if toggle == "on":
        free_space = True
        await ctx.send("The middle free space has been enabled.")
    elif toggle == "off":
        free_space = False
        await ctx.send("The middle free space has been disabled.")
    else:
        await ctx.send("Invalid option. Use '/freeSpace on' to enable or '/freeSpace off' to disable.")
        return

    settings = load_settings()
    settings["free_space_enabled"] = free_space
    save_settings(settings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('token', type=str, help='the bot token')
    args = parser.parse_args()

    settings = load_settings()
    global free_space, bingo_role
    free_space = settings['free_space_enabled']
    bingo_role = settings['bingo_role']

    bot.run(args.token)

if __name__ == "__main__":
    main()
