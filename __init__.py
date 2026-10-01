"""Plugin Hermes: trả lời khách qua một tài khoản Zalo cá nhân."""

from .adapter import register as register_platform
from .cli import COMMAND, register_cli


def register(ctx):
    register_platform(ctx)
    ctx.register_cli_command(
        name=COMMAND,
        help="Đăng nhập và vận hành Zalo cá nhân cho profile này",
        setup_fn=register_cli,
    )
