Maro Bingo Bot is a simple python based Discord bot that can create bingo sheets based on Mark Rosewater's clues about an upcoming Magic the Gathering set.

# Usage

- /setMaroClues: Allows admins and users with a "Bingo Master" role to set clues from the upcoming set. See "clues.txt" for the formatting.
- /listMaroClues: Allows any user to see a list of all the clues
- /createBingoSheet: Allows any user to create a bingo sheet for themselves
- /createBingoSheet @[user]: Allows admins and users with a "Bingo Master" role to create a bingo sheet for the mentioned user
- /viewBingoSheet: Allows any user to view their bingo sheet
- /viewBingoSheet @[user]: Allows any user to view the bingo sheet of the mentioned user
- /cross [square]: Allows any user to cross off a square on their bingo sheet. i.e. "/cross B1" to cross off cell B1.
- /freeSpace [on/off]: Allows admins and users with a "Bingo Master" role to toggle free space on or off
- /setRoleName [name]: Allows admins to set the name of the "Bingo Master" role (default is Bingo Master)

# To Dos

- optional: track the order in which users got bingo in this current set
