import os

# Invidious インスタンスリスト（優先順位付き）
INVIDIOUS_INSTANCES = [
    # 最優先インスタンス（安定性重視）
    'https://invidious.nikkosphere.com/',
    'https://yewtu.be/',
    'https://invidious.private.coffee/',
    'https://invidious.lunivers.trade/',
    'https://invidious.schenkel.eti.br/',
    # 音楽専用の信頼性の高いインスタンス
    'https://inv.nadeko.net/',
    'https://lekker.gay/',
    # フォールバックインスタンス
    'https://invidious.schenkel.eti.br/',
    'https://siawaseok-wakame-server2.glitch.me/',
    'https://clover-pitch-position.glitch.me/',
    'https://iv.duti.dev/',
    'https://yewtu.be/',
    'https://id.420129.xyz/',
    'https://invidious.f5.si/',
    'https://invidious.nerdvpn.de/',
    'https://invidious.tiekoetter.com/',
    'https://nyc1.iv.ggtyler.dev/',
    'https://iv.ggtyler.dev/',
    'https://iv.melmac.space/',
    'https://cal1.iv.ggtyler.dev/',
    'https://pol1.iv.ggtyler.dev/',
    'https://yt.artemislena.eu/',
    'https://invidious.lunivers.trade/',
    'https://eu-proxy.poketube.fun/',
    'https://invidious.dhusch.de/',
    'https://usa-proxy2.poketube.fun/',
    'https://invidious.darkness.service/',
    'https://iv.datura.network/',
    'https://invidious.private.coffee/',
    'https://invidious.projectsegfau.lt/',
    'https://invidious.perennialte.ch/',
    'https://usa-proxy.poketube.fun/',
    'https://invidious.exma.de/',
    'https://invid-api.poketube.fun/',
    'https://invidious.einfachzocken.eu/',
    'https://inv.zzls.xyz/',
    'https://yt.yoc.ovh/',
    'https://rust.oskamp.nl/',
    'https://invidious.adminforge.de',
    'https://invidious.catspeed.cc/',
    'https://inst1.inv.catspeed.cc/',
    'https://inst2.inv.catspeed.cc/',
    'https://materialious.nadeko.net/',
    'https://inv.us.projectsegfau.lt/',
    'https://invidious.qwik.space/',
    'https://invidious.jing.rocks/',
    'https://yt.thechangebook.org/',
    'https://vro.omcat.info/',
    'https://iv.nboeck.de/',
    'https://youtube.mosesmang.com/',
    'https://iteroni.com/',
    'https://subscriptions.gir.st/',
    'https://invidious.fdn.fr/',
    'https://inv.vern.cc/',
    'https://invi.susurrando.com/',
]

# リクエストタイムアウト設定
REQUEST_TIMEOUT = 10

# yt-dlp設定
YTDL_OPTIONS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'format': 'best[ext=mp4]/best',
}
