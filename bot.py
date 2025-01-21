from discord import Intents
from discord.ext import commands
from dotenv import load_dotenv
from os import getenv
import asyncio

# List of extensions (cogs) to load
exts = [
    "cogs.meme_collector",  # Add more cogs as needed
]

class MlscBot(commands.Bot):
    def __init__(self, command_prefix: str, intents: Intents, **kwargs):
        super().__init__(command_prefix, intents=intents, **kwargs)

    async def setup_hook(self) -> None:
        """Load all extensions (cogs) and sync slash commands."""
        for ext in exts:
            await self.load_extension(ext)
        print("Loaded all Cogs .....")

        # Sync slash commands globally
        await self.tree.sync()
        print("Slash commands synced!")

    async def on_ready(self):
        """Triggered when the bot is ready."""
        print(f"MLSC Bot is running as {self.user} ......")


async def main():
    """Main entry point for the bot."""
    # Create the bot instance
    bot = MlscBot(command_prefix="!", intents=Intents.all())

    # Load environment variables
    load_dotenv()

    # Start the bot
    await bot.start(getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    # Run the bot asynchronously
    asyncio.run(main())
