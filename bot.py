import os
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web

# 1. 簡易Webサーバーの設定（Renderのポート検知用）
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Webサーバーをポート {port} で起動しました。")

# 2. Botの初期設定とインテントの有効化
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"同期エラー: {e}")
    print(f"ログインしました: {bot.user.name} (ID: {bot.user.id})")


# ==========================================
# 3. 認証・チケット用ビュー
# ==========================================
class VerifyView(discord.ui.View):
    def __init__(self, verify_role: discord.Role):
        super().__init__(timeout=None)
        self.verify_role = verify_role

    @discord.ui.button(label="✅ 認証する", style=discord.ButtonStyle.green, custom_id="persistent_verify_btn")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if self.verify_role in interaction.user.roles:
                await interaction.response.send_message("すでに認証は完了しています！", ephemeral=True)
            else:
                await interaction.user.add_roles(self.verify_role)
                await interaction.response.send_message("✅ 認証が完了しロールが付与されました！", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ エラーが発生しました: {e}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 チケットを閉じる", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("チャンネルを削除します...")
        await interaction.channel.delete()

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 チケットを作成する", style=discord.ButtonStyle.blurple, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        category = discord.utils.get(guild.categories, name="チケット")
        if not category:
            category = await guild.create_category("チケット")

        channel = await guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites, category=category)
        await channel.send(f"{interaction.user.mention}さん、ようこそ！", view=TicketCloseView())
        await interaction.response.send_message(f"チケットを作成しました: {channel.mention}", ephemeral=True)


# ==========================================
# 4. パネル生成系コマンド
# ==========================================
@bot.tree.command(name="verify_setup", description="認証ロールを設定します。")
@app_commands.describe(role="付与したいロール")
@app_commands.checks.has_permissions(administrator=True)
async def verify_setup(interaction: discord.Interaction, role: discord.Role):
    bot.verify_target_role = role
    await interaction.response.send_message(f"✅ 認証ロールを {role.mention} に設定しました。", ephemeral=True)

@bot.tree.command(name="verify_panel", description="認証パネルを送信します。")
@app_commands.checks.has_permissions(administrator=True)
async def verify_panel(interaction: discord.Interaction):
    target_role = getattr(bot, "verify_target_role", None)
    if not target_role:
        target_role = discord.utils.get(interaction.guild.roles, name="メンバー")
        if not target_role:
            await interaction.response.send_message("⚠️ 先に `/verify_setup` でロールを設定してください。", ephemeral=True)
            return
    embed = discord.Embed(title="🔒 サーバー認証", description="下のボタンを押して認証してください。", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=VerifyView(target_role))
    await interaction.response.send_message("認証パネルを送信しました！", ephemeral=True)

@bot.tree.command(name="ticket_panel", description="チケットパネルを送信します。")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🎫 お問い合わせチケット", description="ボタンを押してチャンネルを作成。", color=discord.Color.green())
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("チケットパネルを送信しました！", ephemeral=True)


# ==========================================
# 5. ミニゲーム（スロット ＆ ガチャ）
# ==========================================
@bot.tree.command(name="slot", description="🎰 スロットゲームで遊ぶ！")
async def slot_game(interaction: discord.Interaction):
    fruits = ["🍎", "🍊", "🍋", "🍇", "🍒", "💎", "⭐"]
    res = [random.choice(fruits) for _ in range(3)]
    
    if res[0] == res[1] == res[2]:
        msg = "🎉 **大当たり！おめでとうございます！** 🎉"
        color = discord.Color.gold()
    elif res[0] == res[1] or res[1] == res[2] or res[0] == res[2]:
        msg = "✨ **おしい！2つ揃いました！** ✨"
        color = discord.Color.blue()
    else:
        msg = "😢 **ハズレ…また挑戦してね！** 😢"
        color = discord.Color.red()

    embed = discord.Embed(title="🎰 スロットマシーン", description=f"# ｜ {' ｜ '.join(res)} ｜\n\n{msg}", color=color)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gacha", description="🎁 運試し！ランダムガチャを引く")
async def gacha_command(interaction: discord.Interaction):
    # ガチャの排出設定（確率とレア度）
    pool = [
        ("🌟🌟🌟🌟🌟 【SSR】 神話級アイテム", discord.Color.gold()),
        ("⭐⭐⭐⭐ 【SR】 超レアアイテム", discord.Color.purple()),
        ("⭐⭐⭐ 【R】 レアアイテム", discord.Color.blue()),
        ("⭐⭐ 【N】 ノーマルアイテム（その1）", discord.Color.green()),
        ("⭐ 【N】 ノーマルアイテム（その2）", discord.Color.light_gray())
    ]
    # 重み付きランダム（SSRは低確率、Nは高確率）
    weights = [2, 8, 20, 35, 35]
    item, color = random.choices(pool, weights=weights, k=1)[0]

    embed = discord.Embed(title="🎁 ガチャ結果", description=f"**{interaction.user.mention} さんの結果は…**\n\n# {item}", color=color)
    await interaction.response.send_message(embed=embed)


# ==========================================
# 6. 管理・ユーティリティコマンド 20個
# ==========================================

@bot.tree.command(name="ban", description="1. メンバーをBANします")
@app_commands.checks.has_permissions(ban_members=True)
async def cmd_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member.mention} をBANしました。(理由: {reason})")

@bot.tree.command(name="kick", description="2. メンバーをキックします")
@app_commands.checks.has_permissions(kick_members=True)
async def cmd_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member.mention} をキックしました。(理由: {reason})")

@bot.tree.command(name="timeout", description="3. メンバーをタイムアウトします（分）")
@app_commands.checks.has_permissions(moderate_members=True)
async def cmd_timeout(interaction: discord.Interaction, member: discord.Member, minutes: int):
    duration = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
    await member.timeout(duration)
    await interaction.response.send_message(f"⏱️ {member.mention} を {minutes} 分間タイムアウトしました。")

@bot.tree.command(name="clear", description="4. 指定した数のメッセージを削除します")
@app_commands.checks.has_permissions(manage_messages=True)
async def cmd_clear(interaction: discord.Interaction, count: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=count)
    await interaction.followup.send(f"🧹 {len(deleted)} 件のメッセージを削除しました。", ephemeral=True)

@bot.tree.command(name="slowmode", description="5. チャンネルのスローモードを設定します（秒）")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"⏳ スローモードを {seconds} 秒に設定しました。")

@bot.tree.command(name="lock", description="6. チャンネルをロックします")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 チャンネルをロックしました。")

@bot.tree.command(name="unlock", description="7. チャンネルのロックを解除します")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 チャンネルのロックを解除しました。")

@bot.tree.command(name="nick", description="8. メンバーのニックネームを変更します")
@app_commands.checks.has_permissions(manage_nicknames=True)
async def cmd_nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    await member.edit(nick=nickname)
    await interaction.response.send_message(f"✏️ {member.mention} のニックネームを `{nickname}` に変更しました。")

@bot.tree.command(name="serverinfo", description="9. サーバーの情報を表示します")
async def cmd_serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=f"📊 {g.name} のサーバー情報", color=discord.Color.blue())
    embed.add_field(name="オーナー", value=g.owner.mention)
    embed.add_field(name="メンバー数", value=f"{g.member_count}人")
    embed.add_field(name="作成日", value=g.created_at.strftime("%Y/%m/%d"))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="10. ユーザーの情報を表示します")
async def cmd_userinfo(interaction: discord.Interaction, member: discord.Member = None):
    m = member or interaction.user
    embed = discord.Embed(title=f"👤 {m.name} の情報", color=m.color)
    embed.add_field(name="ID", value=m.id)
    embed.add_field(name="参加日", value=m.joined_at.strftime("%Y/%m/%d") if m.joined_at else "不明")
    embed.set_thumbnail(url=m.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="11. ボットの応答速度を表示します")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="say", description="12. 指定したテキストをボットに喋らせます")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_say(interaction: discord.Interaction, text: str):
    await interaction.channel.send(text)
    await interaction.response.send_message("送信しました。", ephemeral=True)

@bot.tree.command(name="embed_send", description="13. 埋め込みメッセージを送信します")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_embed(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(title=title, description=description, color=discord.Color.purple())
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("埋め込みを送信しました。", ephemeral=True)

@bot.tree.command(name="poll", description="14. 簡易的な投票を作成します")
async def cmd_poll(interaction: discord.Interaction, question: str):
    embed = discord.Embed(title="📊 投票", description=question, color=discord.Color.orange())
    embed.set_footer(text=f"投票者: {interaction.user.name}")
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await interaction.response.send_message("投票を作成しました！", ephemeral=True)

@bot.tree.command(name="role_add", description="15. メンバーにロールを付与します")
@app_commands.checks.has_permissions(manage_roles=True)
async def cmd_role_add(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ {member.mention} にロール `{role.name}` を付与しました。")

@bot.tree.command(name="role_remove", description="16. メンバーからロールを剥奪します")
@app_commands.checks.has_permissions(manage_roles=True)
async def cmd_role_remove(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(f"❌ {member.mention} からロール `{role.name}` を剥奪しました。")

@bot.tree.command(name="mc_ip", description="17. マイクラサーバーのIPを表示します")
async def cmd_mc_ip(interaction: discord.Interaction):
    embed = discord.Embed(title="⛏️ マイクラサーバー情報", description="IP: `play.example.com`\nバージョン: `1.20.4`", color=discord.Color.dark_green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="promo_rule", description="18. 宣伝鯖のルールを表示します")
async def cmd_promo_rule(interaction: discord.Interaction):
    embed = discord.Embed(title="📢 宣伝ルール", description="1. スパム禁止\n2. 規約遵守\n3. クールダウンを守る", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bot_avatar", description="19. ボットのアイコンを表示します")
async def cmd_bot_avatar(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 ボットアイコン", color=discord.Color.blurple())
    embed.set_image(url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="server_rules", description="20. サーバー共通の総合ルールを表示します")
async def cmd_server_rules(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 総合ルール", description="みんなで楽しく安全に利用しましょう！", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)


# エラーハンドリング
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ このコマンドを実行する権限がありません。", ephemeral=True)
    else:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ エラーが発生しました: {error}", ephemeral=True)


# 7. メイン起動処理
async def main():
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("エラー: DISCORD_TOKEN の環境変数が設定されていません。")
        return

    await start_web_server()

    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
