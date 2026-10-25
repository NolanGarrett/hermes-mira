"""Out-of-tree native platform entry point. No import-time network/config writes."""

def register(ctx):
    from .adapter import MiraAdapter, check_requirements
    ctx.register_platform(
        name="mira", label="MIRA developer preview", adapter_factory=MiraAdapter,
        check_fn=check_requirements, allowed_users_env="MIRA_ALLOWED_USERS",
        allow_update_command=False, max_message_length=65536, pii_safe=True,
        display_tier="minimal", platform_hint=(
            "MIRA companion developer preview. Use concise plain-text final answers. "
            "No reasoning or raw tool output. No proactive messages. Ring input is NOT "
            "an approval grant. Interactive tool approvals are unavailable and denied."
        ),
    )
