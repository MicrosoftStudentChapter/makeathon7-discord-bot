import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from pymongo import MongoClient


class MemeCollector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = self.connect_to_db()

    def connect_to_db(self):
        """Connects to the MongoDB database."""
        from os import getenv
        mongo_uri = getenv("MONGO_URI")
        client = MongoClient(mongo_uri)
        return client["MemeBotDatabase"]

    @app_commands.command(name="creatememe", description="Create a new meme by uploading an image.")
    async def create_meme(self, interaction: discord.Interaction, meme_name: str):
        await interaction.response.defer(ephemeral=True)  # Show a "processing" message

        meme_name = meme_name.lower()
        if self.db.memes.find_one({"name": meme_name}):
            await interaction.followup.send(f"A meme named **{meme_name}** already exists. Please use another name.")
            return

        await interaction.followup.send(f"Upload the image for the meme **{meme_name}**.")

        def check(msg):
            return (
                msg.author == interaction.user
                and msg.channel == interaction.channel
                and len(msg.attachments) > 0
            )

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
            meme_url = msg.attachments[0].url

            self.db.memes.insert_one({"name": meme_name, "url": meme_url})
            await interaction.followup.send(f"Meme **{meme_name}** has been saved!")
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to upload an image. Please try again.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        meme_name = message.content.strip().lower()
        meme = self.db.memes.find_one({"name": meme_name})

        if meme:
            await message.delete()  # Delete +- original message
            embed = discord.Embed(description=f"{message.author.name} shared a meme!")
            embed.set_image(url=meme["url"])
            embed.set_footer(text=message.author.name, icon_url=message.author.avatar.url)

            await message.channel.send(embed=embed)


async def setup(bot):
    """Adds the MemeCollector cog to the bot."""
    await bot.add_cog(MemeCollector(bot))
