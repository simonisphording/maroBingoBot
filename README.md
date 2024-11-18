Maro Bingo Bot is a simple python based Discord bot that can create bingo sheets based on Mark Rosewater's clues about an upcoming Magic the Gathering set.

# Usage

## General commands

- /listMaroClues: List the current clues
- /createBingoSheet: Create a bingo sheet for yourself
- /viewBingoSheet: View your bingo sheet
- /viewBingoSheet @[user]: View the bingo sheet of the mentioned user
- /cross [square]: Cross off a square on their bingo sheet. i.e. "/cross B1" to cross off cell B1.

## Admin (or "Bingo Role") commands

- /setMaroClues: Set clues from the upcoming set. See "clues.txt" for the formatting.
- /resetMaroClues: Reset clues to the bot's default
- /createBingoSheet @[user]: Create a bingo sheet for the mentioned user
- /freeSpace [on/off]: Toggle free space on or off
- /setRoleName [name]: Set the name of a "Bingo Admin" role (default is "Bingo Master")

# To Dos

- optional: track the order in which users got bingo in this current set
