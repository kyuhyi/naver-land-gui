# -*- coding: utf-8 -*-
"""
hud.py — 크롬 창 안에 진행 상황을 그려 넣는다.

조회는 여전히 페이지 안의 fetch() 로 일어난다. 이 파일은 그 위에 패널을
얹어 "지금 무엇을 하고 있는지" 를 눈에 보이게 만들 뿐이다.
요청을 더 보내지 않으므로 속도와 차단 위험에 영향이 없다.

패널은 Shadow DOM 안에 그린다. 네이버 페이지의 CSS 와 섞이지 않는다.
"""

# 페이지 안에서 도는 코드. payload 하나를 받아 종류별로 처리한다.
# window.__bsdHud 가 없으면 만들고(새로고침·이동 후에도 되살아난다),
# 있으면 그대로 갱신한다.
HUD_JS = r"""
(payload) => {
  const ACCENT = '#E74339', DIM = '#9AA1B4', MUTE = '#6B7285';

  function build() {
    const host = document.createElement('div');
    host.id = '__bsd_hud_host';
    host.style.cssText = 'position:fixed;top:0;right:0;z-index:2147483647;';
    (document.body || document.documentElement).appendChild(host);
    const root = host.attachShadow({ mode: 'open' });

    root.innerHTML = `
      <style>
        :host { all: initial; }
        * { box-sizing: border-box; margin: 0; font-family: "Malgun Gothic",
            "Apple SD Gothic Neo", system-ui, sans-serif; }
        .panel {
          position: fixed; top: 14px; right: 14px; bottom: 14px; width: 392px;
          background: rgba(11,12,16,.94);
          border: 1px solid #242835; border-radius: 16px;
          box-shadow: 0 24px 60px rgba(0,0,0,.55);
          color: #E7E9EF; display: flex; flex-direction: column;
          overflow: hidden; backdrop-filter: blur(10px);
          transition: height .18s ease;
        }
        .panel.min { height: 52px; bottom: auto; }
        .panel.min .body { display: none; }

        .head {
          display: flex; align-items: center; gap: 9px;
          padding: 15px 16px; border-bottom: 1px solid #242835; flex: none;
        }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: ${MUTE}; flex: none; }
        .dot.on { background: ${ACCENT}; animation: pulse 1.1s ease-in-out infinite; }
        .dot.ok { background: #3FBF7F; }
        .dot.err { background: ${ACCENT}; }
        @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)}
                           50%{opacity:.35;transform:scale(.78)} }
        .brand { font-size: 12.5px; font-weight: 700; letter-spacing: -.01em; }
        .live { font-size: 9.5px; letter-spacing: .14em; color: ${MUTE};
                border: 1px solid #2E3444; border-radius: 999px; padding: 2px 7px; }
        .fold { margin-left: auto; cursor: pointer; color: ${MUTE};
                font-size: 15px; line-height: 1; padding: 2px 6px; border-radius: 6px;
                user-select: none; }
        .fold:hover { color: #E7E9EF; background: #191C24; }

        .body { display: flex; flex-direction: column; flex: 1; min-height: 0; }

        .status { padding: 15px 16px 12px; flex: none; }
        .phase { font-size: 10px; letter-spacing: .14em; color: ${MUTE}; margin-bottom: 7px; }
        .now { font-size: 15px; font-weight: 600; line-height: 1.4; word-break: break-all; }

        .bar { height: 4px; background: #191C24; margin: 13px 16px 0; border-radius: 2px;
               overflow: hidden; flex: none; }
        .bar i { display: block; height: 100%; width: 0%; background: ${ACCENT};
                 border-radius: 2px; transition: width .25s ease; }
        .bar.indet i { width: 34% !important; animation: slide 1.15s ease-in-out infinite; }
        @keyframes slide { 0%{margin-left:-34%} 100%{margin-left:100%} }

        .counts { display: flex; gap: 8px; padding: 13px 16px; flex: none; }
        .c { flex: 1; background: #14161D; border: 1px solid #242835;
             border-radius: 10px; padding: 9px 11px; }
        .c .k { font-size: 9.5px; color: ${MUTE}; letter-spacing: .06em; }
        .c .v { font-size: 17px; font-weight: 700; margin-top: 2px;
                font-variant-numeric: tabular-nums; }

        .req { margin: 0 16px 12px; padding: 8px 11px; border-radius: 9px;
               background: #101218; border: 1px solid #242835; flex: none; }
        .req .k { font-size: 9.5px; color: ${MUTE}; letter-spacing: .1em; }
        .req .p { font-family: Consolas, Menlo, monospace; font-size: 11px;
                  color: #7FD9D0; margin-top: 3px; word-break: break-all; }
        .req.flash { border-color: ${ACCENT}; }

        .sect { font-size: 9.5px; letter-spacing: .14em; color: ${MUTE};
                padding: 0 16px 7px; flex: none; }

        .cards { padding: 0 16px; overflow-y: auto; flex: 0 0 auto;
                 max-height: 33%; display: flex; flex-direction: column; gap: 6px; }
        .card { background: #14161D; border: 1px solid #242835; border-radius: 10px;
                padding: 9px 11px; display: flex; align-items: baseline; gap: 9px; }
        .card .n { font-size: 12px; font-weight: 600; flex: 1; overflow: hidden;
                   text-overflow: ellipsis; white-space: nowrap; }
        .card .pr { font-size: 13.5px; font-weight: 700; color: #FFFFFF;
                    font-variant-numeric: tabular-nums; }
        .card .m { font-size: 10.5px; color: ${DIM}; font-family: Consolas, monospace; }

        .log { flex: 1; min-height: 0; overflow-y: auto; padding: 0 16px 14px;
               font-family: Consolas, Menlo, monospace; font-size: 10.5px;
               line-height: 1.7; color: ${DIM}; }
        .log div { word-break: break-all; }
        .log .t { color: ${MUTE}; }
        .log .hit { color: #7FD9D0; }
        .log .warn { color: #E2B33C; }
        .log .err { color: ${ACCENT}; }

        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-thumb { background: #2B3040; border-radius: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
      </style>

      <div class="panel">
        <div class="head">
          <span class="dot on"></span>
          <span class="brand">BSD 매물 조회기</span>
          <span class="live">LIVE</span>
          <span class="fold" title="접기/펴기">—</span>
        </div>
        <div class="body">
          <div class="status">
            <div class="phase">준비</div>
            <div class="now">연결 중…</div>
          </div>
          <div class="bar indet"><i></i></div>
          <div class="counts">
            <div class="c"><div class="k">단지</div><div class="v cx">0</div></div>
            <div class="c"><div class="k">매물</div><div class="v ar">0</div></div>
            <div class="c"><div class="k">경과</div><div class="v el">0:00</div></div>
          </div>
          <div class="req"><div class="k">지금 요청</div><div class="p">—</div></div>
          <div class="sect">방금 찾은 매물</div>
          <div class="cards"></div>
          <div class="sect" style="padding-top:10px">기록</div>
          <div class="log"></div>
        </div>
      </div>`;

    const $ = (s) => root.querySelector(s);
    const el = {
      panel: $('.panel'), dot: $('.dot'), phase: $('.phase'), now: $('.now'),
      bar: $('.bar'), fill: $('.bar i'), cx: $('.cx'), ar: $('.ar'), el: $('.el'),
      req: $('.req'), reqp: $('.req .p'), cards: $('.cards'), log: $('.log'),
    };
    $('.fold').onclick = () => el.panel.classList.toggle('min');

    const hud = {
      t0: Date.now(),
      set(s) {
        if (s.phase !== undefined) el.phase.textContent = s.phase;
        if (s.status !== undefined) {
          el.now.textContent = s.status;
          document.title = s.status;
        }
        if (s.complexes !== undefined) el.cx.textContent = s.complexes;
        if (s.articles !== undefined) el.ar.textContent = s.articles;
        if (s.total !== undefined) {
          if (s.total > 0) {
            el.bar.classList.remove('indet');
            el.fill.style.width = Math.min(100, (s.current / s.total) * 100) + '%';
          } else {
            el.bar.classList.add('indet');
          }
        }
        if (s.state === 'done') { el.dot.className = 'dot ok'; }
        else if (s.state === 'error') { el.dot.className = 'dot err'; }
        else { el.dot.className = 'dot on'; }
      },
      ping(path) {
        el.reqp.textContent = path;
        el.req.classList.add('flash');
        setTimeout(() => el.req.classList.remove('flash'), 260);
      },
      log(text, kind) {
        const d = document.createElement('div');
        const ts = new Date().toTimeString().slice(0, 8);
        d.innerHTML = '<span class="t">' + ts + '</span> ';
        const s = document.createElement('span');
        if (kind) s.className = kind;
        s.textContent = text;
        d.appendChild(s);
        el.log.appendChild(d);
        while (el.log.childElementCount > 300) el.log.removeChild(el.log.firstChild);
        el.log.scrollTop = el.log.scrollHeight;
      },
      cards(items) {
        for (const it of items) {
          const c = document.createElement('div');
          c.className = 'card';
          const n = document.createElement('div'); n.className = 'n'; n.textContent = it.name || '';
          const p = document.createElement('div'); p.className = 'pr'; p.textContent = it.price || '';
          const m = document.createElement('div'); m.className = 'm'; m.textContent = it.meta || '';
          c.append(n, p, m);
          el.cards.insertBefore(c, el.cards.firstChild);
        }
        while (el.cards.childElementCount > 40) el.cards.removeChild(el.cards.lastChild);
      },
    };
    setInterval(() => {
      const s = Math.floor((Date.now() - hud.t0) / 1000);
      el.el.textContent = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
    }, 500);
    return hud;
  }

  if (!window.__bsdHud || !document.getElementById('__bsd_hud_host')) {
    try { window.__bsdHud = build(); } catch (e) { return 'build failed: ' + e; }
  }
  const h = window.__bsdHud;
  const t = payload && payload.type;
  if (t === 'set') h.set(payload);
  else if (t === 'ping') h.ping(payload.path);
  else if (t === 'log') h.log(payload.text, payload.kind);
  else if (t === 'cards') h.cards(payload.items || []);
  else if (t === 'reset') { h.t0 = Date.now(); h.set(payload); }
  return 'ok';
}
"""


class Hud:
    """크롬 페이지 안의 패널을 조종한다. 실패해도 조회를 방해하지 않는다."""

    def __init__(self, page, enabled=True):
        self.page = page
        self.enabled = enabled
        self.broken = False

    def _send(self, payload):
        if not self.enabled or self.broken:
            return
        try:
            self.page.evaluate(HUD_JS, payload)
        except Exception:
            # 페이지가 닫혔거나 이동 중이면 조용히 포기한다.
            self.broken = True

    # ── 바깥에서 쓰는 것들 ──────────────────────────────────
    def start(self, status="시작하는 중…", phase="준비"):
        self._send({"type": "reset", "status": status, "phase": phase,
                    "complexes": 0, "articles": 0, "total": 0, "state": "run"})

    def set(self, **kw):
        kw["type"] = "set"
        self._send(kw)

    def ping(self, path):
        self._send({"type": "ping", "path": path})

    def log(self, text, kind=None):
        self._send({"type": "log", "text": str(text), "kind": kind})

    def cards(self, items):
        """items: [{'name':..., 'price':..., 'meta':...}, ...]"""
        if items:
            self._send({"type": "cards", "items": items[:12]})

    def done(self, ok, message):
        # 막대는 채워 둔다. total=0 이면 불확정 애니메이션이 계속 돈다.
        self._send({"type": "set", "status": message,
                    "phase": "완료" if ok else "중단",
                    "state": "done" if ok else "error",
                    "current": 1, "total": 1})
        self.log(message, None if ok else "warn")
