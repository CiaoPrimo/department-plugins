"""
Department Selector Plugin for Modmail
Adds a dropdown menu for users to select departments when opening tickets
"""

import discord
from discord.ext import commands
from core import checks
from core.models import PermissionLevel


class DepartmentSelector(commands.Cog):
    """Plugin that adds department selection when opening tickets"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.api.get_plugin_partition(self)
        
    async def cog_load(self):
        """Initialize default departments if not set"""
        config = await self.db.find_one({"_id": "config"})
        if not config:
            await self.db.find_one_and_update(
                {"_id": "config"},
                {
                    "$set": {
                        "departments": [
                            {"name": "General Support", "category_id": None},
                            {"name": "Technical Support", "category_id": None},
                            {"name": "Billing", "category_id": None},
                            {"name": "Report", "category_id": None}
                        ]
                    }
                },
                upsert=True
            )
    
    @commands.group(invoke_without_command=True)
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def department(self, ctx):
        """Manage ticket departments"""
        await ctx.send_help(ctx.command)
    
    @department.command(name="add")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def dept_add(self, ctx, *, name: str):
        """Add a new department
        
        Usage: {prefix}department add Gaming Support
        """
        config = await self.db.find_one({"_id": "config"})
        departments = config.get("departments", [])
        
        departments.append({
            "name": name,
            "category_id": None
        })
        
        await self.db.find_one_and_update(
            {"_id": "config"},
            {"$set": {"departments": departments}},
            upsert=True
        )
        
        await ctx.send(f"Added department: {name}")
    
    @department.command(name="remove")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def dept_remove(self, ctx, *, name: str):
        """Remove a department
        
        Usage: {prefix}department remove Gaming Support
        """
        config = await self.db.find_one({"_id": "config"})
        departments = config.get("departments", [])
        
        departments = [d for d in departments if d["name"].lower() != name.lower()]
        
        await self.db.find_one_and_update(
            {"_id": "config"},
            {"$set": {"departments": departments}},
            upsert=True
        )
        
        await ctx.send(f"Removed department: {name}")
    
    @department.command(name="list")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def dept_list(self, ctx):
        """List all departments"""
        config = await self.db.find_one({"_id": "config"})
        departments = config.get("departments", [])
        
        if not departments:
            return await ctx.send("No departments configured.")
        
        embed = discord.Embed(
            title="Ticket Departments",
            color=self.bot.main_color
        )
        
        for dept in departments:
            category = "Not set"
            if dept.get("category_id"):
                cat = ctx.guild.get_channel(dept["category_id"])
                category = cat.name if cat else "Deleted"
            
            embed.add_field(
                name=dept['name'],
                value=f"Category: {category}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @department.command(name="category")
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    async def dept_category(self, ctx, department_name: str, category: discord.CategoryChannel):
        """Set a category for a department
        
        Usage: {prefix}department category "Technical Support" CategoryName
        """
        config = await self.db.find_one({"_id": "config"})
        departments = config.get("departments", [])
        
        for dept in departments:
            if dept["name"].lower() == department_name.lower():
                dept["category_id"] = category.id
                break
        else:
            return await ctx.send(f"Department '{department_name}' not found.")
        
        await self.db.find_one_and_update(
            {"_id": "config"},
            {"$set": {"departments": departments}},
            upsert=True
        )
        
        await ctx.send(f"Set category for {department_name} to {category.name}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Intercept DM messages to show department selector"""
        if message.guild or message.author.bot:
            return
        
        # Check if user already has a thread
        thread = await self.bot.threads.find(recipient=message.author)
        if thread:
            return
        
        # Get departments
        config = await self.db.find_one({"_id": "config"})
        departments = config.get("departments", [])
        
        if not departments:
            return
        
        # Create select menu
        view = DepartmentView(self.bot, departments, message.author)
        
        embed = discord.Embed(
            title="Select a Department",
            description="Please select the department that best matches your inquiry:",
            color=self.bot.main_color
        )
        
        await message.author.send(embed=embed, view=view)


class DepartmentView(discord.ui.View):
    def __init__(self, bot, departments, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.add_item(DepartmentSelect(bot, departments, user))


class DepartmentSelect(discord.ui.Select):
    def __init__(self, bot, departments, user):
        self.bot = bot
        self.user = user
        self.departments = departments
        
        options = [
            discord.SelectOption(
                label=dept["name"],
                value=str(i)
            )
            for i, dept in enumerate(departments)
        ]
        
        super().__init__(
            placeholder="Choose a department...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "This menu is not for you.",
                ephemeral=True
            )
        
        selected_index = int(self.values[0])
        selected_dept = self.departments[selected_index]
        
        # Create the thread with the selected department
        category_id = selected_dept.get("category_id")
        
        # Store department info for the thread
        thread = await self.bot.threads.create(
            recipient=self.user,
            creator=self.user,
            category=self.bot.main_category if not category_id else self.bot.get_channel(category_id)
        )
        
        # Add department info to thread channel topic
        if thread and thread.channel:
            await thread.channel.edit(
                topic=f"Department: {selected_dept['name']} | User ID: {self.user.id}"
            )
        
        await interaction.response.send_message(
            f"Ticket created in {selected_dept['name']} department. A staff member will be with you shortly.",
            ephemeral=True
        )
        
        # Disable the view
        self.view.stop()


async def setup(bot):
    await bot.add_cog(DepartmentSelector(bot))
