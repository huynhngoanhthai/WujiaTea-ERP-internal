from . import models


def post_init_hook(env):
    """Tính sẵn 2 aggregate công nợ (badge portal) 1 lần lúc cài — tránh badge
    hiện 0 cho tới khi cron daily đầu tiên chạy."""
    env['wujia.franchise.management']._cron_recompute_portal_debt()
