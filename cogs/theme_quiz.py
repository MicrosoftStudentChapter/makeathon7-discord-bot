import discord
from discord.ext import commands
from asyncio import TimeoutError

# Quiz questions
QUESTIONS = {
    "easy": [
        {"question": "What is 2 + 2?", "answer": "4"},
        {"question": "What is the capital of France?", "answer": "paris"},
        {"question": "What is the color of the sky?", "answer": "blue"},
    ],
    "medium": [
        {"question": "What is the square root of 16?", "answer": "4"},
        {"question": "Who wrote 'To Kill a Mockingbird'?", "answer": "harper lee"},
        {"question": "What is 15 x 15?", "answer": "225"},
    ],
    "hard": [
        {"question": "What is the chemical symbol for Gold?", "answer": "au"},
        {"question": "Solve: 12 * (3 + 2) / 6", "answer": "10"},
    ],
}

class Quiz(commands.Cog):
    """Quiz Cog"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="quiz")
    async def quiz(self, ctx):
        """Start a quiz with the user"""
        user = ctx.author
        score = 0
        difficulties = ["easy", "medium", "hard"]

        for difficulty in difficulties:
            questions = QUESTIONS[difficulty]
            for question_data in questions:
                question = question_data["question"]
                correct_answer = question_data["answer"]

                await user.send(f"**{difficulty.capitalize()} Question:** {question}")
                await ctx.send(f"{user.mention}, check your DM for the question!")

                def check(msg):
                    return msg.author == user and isinstance(msg.channel, discord.DMChannel)
                if difficulty == "easy":
                    timeout = 10
                    try:
                        response = await self.bot.wait_for("message", check=check, timeout=timeout)
                        if response.content.strip().lower() == correct_answer:
                            score += 1
                            await user.send("Correct!")
                        else:
                            score -= 1
                            await user.send(f"Wrong! The correct answer was: {correct_answer}")
                    except TimeoutError:
                        score -= 1
                        await user.send("You ran out of time! -1 point.")
                elif difficulty == "medium":
                    timeout = 20
                    try:
                        response = await self.bot.wait_for("message", check=check, timeout=timeout)
                        if response.content.strip().lower() == correct_answer:
                            score += 1
                            await user.send("Correct!")
                        else:
                            score -= 1
                            await user.send(f"Wrong! The correct answer was: {correct_answer}")
                    except TimeoutError:
                        score -= 1
                        await user.send("You ran out of time! -1 point.")
                else:
                    timeout = 30
                    try:
                        response = await self.bot.wait_for("message", check=check, timeout=timeout)
                        if response.content.strip().lower() == correct_answer:
                            score += 1
                            await user.send("Correct!")
                        else:
                            score -= 1
                            await user.send(f"Wrong! The correct answer was: {correct_answer}")
                    except TimeoutError:
                        score -= 1
                        await user.send("You ran out of time! -1 point.")
                

        await user.send(f"Quiz finished! Your total score is: {score}")
        await ctx.send(f"{user.mention}, your quiz is complete! Check your DM for your score.")


async def setup(bot):
    await bot.add_cog(Quiz(bot))
