import os
import random
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from pymongo import MongoClient
import asyncpraw
from datetime import datetime, timedelta

class MemeCollector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = self.connect_to_db()
        self.reddit = self.connect_to_reddit()

    def connect_to_db(self):
        mongo_uri = os.getenv("MONGO_URI")
        client = MongoClient(mongo_uri)
        return client["MemeBotDatabase"]

    def connect_to_reddit(self):
        return asyncpraw.Reddit(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET"),
            user_agent=os.getenv("USER_AGENT"),
        )
    
    @app_commands.command(name="randommeme", description="Get a random meme from Reddit.")
    async def random_meme(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False) 
        try:
            subreddit = await self.reddit.subreddit("memes")
            posts = [
                post async for post in subreddit.hot(limit=50)
                if not post.over_18 and not post.stickied
            ]

            if not posts:
                await interaction.followup.send("Couldn't find any memes at the moment. Try again later!")
                return

            random_post = random.choice(posts)
            meme_title = random_post.title
            meme_url = random_post.url

            embed = discord.Embed(title=meme_title, color=discord.Color.blue())
            embed.set_image(url=meme_url)
            embed.set_footer(text=f"👍 {random_post.score} | 💬 {random_post.num_comments} comments")

            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error fetching meme: {e}")
            await interaction.followup.send("An error occurred while fetching a meme. Please try again later.")

    @app_commands.command(name="creatememe", description="Create a new meme by uploading an image.")
    async def create_meme(self, interaction: discord.Interaction, meme_name: str):
        await interaction.response.defer(ephemeral=True)

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

            meme_data = {
                "name": meme_name,
                "url": meme_url,
                "upvotes": 0,
                "downvotes": 0,
                "verified": False,
                "created_at": datetime.utcnow(),
            }

            self.db.memes.insert_one(meme_data)
            await interaction.followup.send(f"Meme **{meme_name}** has been saved! Start voting with 👍 (upvote) or 👎 (downvote).")

            await self.start_voting(meme_name, interaction.channel)

        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to upload an image. Please try again.")

    async def start_voting(self, meme_name: str, channel: discord.TextChannel):
        meme = self.db.memes.find_one({"name": meme_name})

        if not meme:
            return

        message = await channel.send(
            f"Voting for meme **{meme_name}** has started! React with 👍 to upvote or 👎 to downvote."
        )
        await message.add_reaction("👍")
        await message.add_reaction("👎")

        await asyncio.sleep(600)

        updated_meme = self.db.memes.find_one({"name": meme_name})

        if updated_meme:
            if updated_meme["upvotes"] >= 10:
                self.db.memes.update_one(
                    {"name": meme_name},
                    {"$set": {"verified": True}},
                )
                await channel.send(f"Meme **{meme_name}** has been verified! It received enough upvotes.")
            else:
                await channel.send(f"Meme **{meme_name}** did not receive enough upvotes to be verified.")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return

        meme_name = reaction.message.content.split("**")[1]

        meme = self.db.memes.find_one({"name": meme_name})
        if not meme:
            return

        if reaction.emoji == "👍":
            self.db.memes.update_one(
                {"name": meme_name},
                {"$inc": {"upvotes": 1}},
            )
        elif reaction.emoji == "👎":
            self.db.memes.update_one(
                {"name": meme_name},
                {"$inc": {"downvotes": 1}},
            )

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return

        meme_name = reaction.message.content.split("**")[1]

        meme = self.db.memes.find_one({"name": meme_name})
        if not meme:
            return

        if reaction.emoji == "👍":
            self.db.memes.update_one(
                {"name": meme_name},
                {"$inc": {"upvotes": -1}},
            )
        elif reaction.emoji == "👎":
            self.db.memes.update_one(
                {"name": meme_name},
                {"$inc": {"downvotes": -1}},
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        meme_name = message.content.strip().lower()
        meme = self.db.memes.find_one({"name": meme_name})

        if meme:
            await message.delete()  # Delete the original message
            embed = discord.Embed(description=f"{message.author.name} shared a meme!", title=meme_name)
            embed.set_image(url=meme["url"])
            embed.set_footer(text=message.author.name, icon_url=message.author.avatar.url)

            await message.channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MemeCollector(bot))
