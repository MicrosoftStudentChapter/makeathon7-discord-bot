from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from os import getenv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SpotifyMusic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize Spotipy client using environment variables
        self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=getenv("SPOTIFY_CLIENT_ID"), 
            client_secret=getenv("SPOTIFY_CLIENT_SECRET")
        ))
        self.song_queue = []


async def setup(bot):
    await bot.add_cog(SpotifyMusic(bot))
