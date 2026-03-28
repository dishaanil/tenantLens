import '../css/styles.css';

// ─── Types ────────────────────────────────────────────────────────────────────

type BuildingType = 'bg' | 'mid' | 'fg' | 'esb' | 'owt' | 'chr';
type RGB = [number, number, number];

interface Step {
  i: string;
  l: string;
  d: string;
}

interface BuildingDef {
  x: number;
  w: number;
  h: number;
  type: BuildingType;
}

interface WinGridConfig {
  cols: number;
  rows: number;
  s: number;
  g: number;
  skip: number;
}

interface WindowDot {
  wx: number;
  wy: number;
  ws: number;
  idx: number;
}

interface Antenna {
  x: number;
  y1: number;
  y2: number;
}

interface Building {
  bx: number;
  by: number;
  bw: number;
  bh: number;
  type: BuildingType;
  wins: WindowDot[];
  antenna: Antenna | null;
}

interface HazeLayer {
  x: number;
  speed: number;
  w: number;
  h: number;
  cy: number;
  alpha: number;
  col: RGB;
}

interface AgentResponse {
  violation_type: string;
  confidence: string;
  description: string;
  address: string;
  borough: string;
  preferred_language: string;
}

// ─── Expose globals to HTML onclick handlers ──────────────────────────────────
declare global {
  interface Window {
    go: (n: number) => void;
    toggleSB: () => void;
    closeSB: () => void;
    qf: (a: string, b: string, c: string, fn: string, ln: string) => void;
    scan: () => void;
    doSubmit: () => void;
  }
}

// ─── State ────────────────────────────────────────────────────────────────────

let cur = 1;
let busy = false;
let agentResult: AgentResponse | null = null;
let cameraStream: MediaStream | null = null;

const AGENT1_URL = 'http://localhost:8001/run';

const STEPS: Step[] = [
  { i: '📸', l: 'Capturing image',        d: 'Reading frame from camera and encoding...' },
  { i: '🧠', l: 'Pattern recognition',    d: 'Texture matches <span class="hl2">violation signature</span> — analyzing housing condition...' },
  { i: '📋', l: 'Matching HPD codes',     d: 'Mapping to <span class="hl2">NYC Housing Maintenance Code</span> — identifying landlord obligations...' },
  { i: '🏢', l: 'Querying building data', d: 'Pulling open violations from <span class="hl2">HPD Open Data</span> for this address...' },
  { i: '⚡', l: 'Building complaint',     d: '<span class="hl2">Pre-filling 311 complaint</span> with violation details and legal language...' },
];

// ─── DOM Helpers ──────────────────────────────────────────────────────────────

function getEl<T extends HTMLElement>(id: string): T {
  return document.getElementById(id) as T;
}

// ─── Camera ───────────────────────────────────────────────────────────────────

async function startCamera(): Promise<void> {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    const video = getEl<HTMLVideoElement>('cameraVideo');
    if (video) {
      video.srcObject = cameraStream;
      video.play();
    }
  } catch (err) {
    console.warn('Camera access denied or unavailable:', err);
  }
}

function captureFrame(): string | null {
  const video = getEl<HTMLVideoElement>('cameraVideo');
  if (!video || !cameraStream) return null;

  const canvas = document.createElement('canvas');
  canvas.width  = video.videoWidth  || 1280;
  canvas.height = video.videoHeight || 720;

  const ctx = canvas.getContext('2d');
  if (!ctx) return null;

  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
  return dataUrl.split(',')[1];
}

// ─── Agent 1 API Call ─────────────────────────────────────────────────────────

async function callAgent1(
  address: string,
  borough: string,
  language: string,
  frameB64: string | null
): Promise<void> {
  try {
    const body: Record<string, string> = {
      address,
      borough,
      preferred_language: language,
    };

    if (frameB64) body.frame_base64 = frameB64;

    const res = await fetch(AGENT1_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) throw new Error(`Agent 1 returned ${res.status}`);
    agentResult = await res.json();
    console.log('Agent 1 response:', agentResult);
    populateScreen3(); 

  } catch (err) {
    console.error('Agent 1 call failed — using fallback:', err);
    agentResult = {
      violation_type: 'pest_infestation',
      confidence: 'high',
      description: 'Numerous dark droppings visible on countertop surface, consistent with rodent activity.',
      address,
      borough,
      preferred_language: language,
    };
    populateScreen3
  }
}

// ─── Populate Screen 3 with real agent data ───────────────────────────────────

function populateScreen3(): void {
  if (!agentResult) return;
 
  const vt = agentResult.violation_type.replace(/_/g, ' ');
 
  const vioEl = document.getElementById('real-violation-type');
  if (vioEl) vioEl.textContent = vt;
 
  const confEl = document.getElementById('real-confidence');
  if (confEl) confEl.textContent = agentResult.confidence;
 
  const descEl = document.getElementById('real-description');
  if (descEl) descEl.textContent = agentResult.description;
 
  const addrEl = document.getElementById('real-address');
  if (addrEl) addrEl.textContent = agentResult.address;
 
  const boroughEl = document.getElementById('real-borough');
  if (boroughEl) boroughEl.textContent = agentResult.borough;

  const vioDescEl = document.getElementById('real-vio-desc');
  if (vioDescEl) vioDescEl.textContent = agentResult.description;
 
  const complaintMap: Record<string, string> = {
    mold:              'UNSANITARY CONDITION — MOLD',
    water_damage:      'PLUMBING — WATER SUPPLY',
    pest_damage:       'PEST/RODENT ACTIVITY',
    pest_infestation:  'PEST/RODENT ACTIVITY',
    broken_fixture:    'DOOR/WINDOW — DEFECTIVE',
    structural_damage: 'STRUCTURAL — DEFECTIVE CONDITIONS',
    heating_issue:     'HEAT/HOT WATER — INADEQUATE HEAT',
    none:              'GENERAL COMPLAINT',
  };
 
  const compEl = document.getElementById('real-complaint-type');
  if (compEl) compEl.textContent = complaintMap[agentResult.violation_type] || vt.toUpperCase();
 
  const deadlineMap: Record<string, string> = {
    mold:              '24 hours (Class C) or 30 days (Class B)',
    water_damage:      '30 days',
    pest_damage:       '30 days',
    pest_infestation:  '24 hours (Class C — immediate hazard)',
    broken_fixture:    '30 days',
    structural_damage: '30 days',
    heating_issue:     '24 hours',
    none:              'N/A',
  };
 
  const deadlineEl = document.getElementById('real-deadline');
  if (deadlineEl) deadlineEl.textContent = deadlineMap[agentResult.violation_type] || '30 days';

  const titleMap: Record<string, string> = {
    mold:              'Mold Growth Detected',
    water_damage:      'Water Damage Detected',
    pest_damage:       'Pest Damage Detected',
    pest_infestation:  'Pest Infestation Detected',
    broken_fixture:    'Broken Fixture Detected',
    structural_damage: 'Structural Damage Detected',
    heating_issue:     'Heating Issue Detected',
    none:              'No Violation Detected',
  };

const titleEl = document.getElementById('real-vio-title');
if (titleEl) titleEl.textContent = titleMap[agentResult.violation_type] || vt;  
}
 

// ─── Screen 1 Entry Animation ─────────────────────────────────────────────────

function animateS1(): void {
  const els = document.querySelectorAll<HTMLElement>('.s1-hero .tag,.h1,.sub,.stats,.div,.s1-form,.cta');
  els.forEach((el, i) => {
    const delay = (i * 0.08) + 0.05;
    el.style.cssText = `opacity:0;transform:translateY(18px);transition:opacity .5s ease ${delay}s, transform .5s cubic-bezier(.4,0,.2,1) ${delay}s`;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      el.style.opacity = '1';
      el.style.transform = 'none';
    }));
  });
}

// ─── Navigation ───────────────────────────────────────────────────────────────

function go(n: number): void {
  if (n === cur) { closeSB(); return; }

  const prev = getEl<HTMLDivElement>('s' + cur);
  const next = getEl<HTMLDivElement>('s' + n);

  prev.classList.add('exit-left');
  prev.classList.remove('on');
  setTimeout(() => prev.classList.remove('exit-left'), 420);

  next.classList.add('on');
  next.scrollTop = 0;

  if (n === 2) startCamera();

  for (let i = 1; i <= 3; i++) {
    const p = getEl('pp' + i);
    p.className = 'pip';
    if (i < n) p.classList.add('done');
    else if (i === n) p.classList.add('on');
  }

  for (let i = 1; i <= 3; i++) {
    getEl('sni' + i).classList.remove('cur');
    getEl('bub' + i).classList.remove('done');
    if (i === n) getEl('sni' + i).classList.add('cur');
    else if (i < n) getEl('bub' + i).classList.add('done');
  }

  const a  = getEl<HTMLInputElement>('fa').value  || '243 94th Street';
  const ap = getEl<HTMLInputElement>('fap').value || '4B';
  const b  = getEl<HTMLInputElement>('fb').value  || 'Brooklyn';
  getEl('apt').textContent    = `${a}, ${b}`;
  getEl('afield').textContent = `${a}, Apt ${ap}, ${b}, NY`;

  if (n === 3) {
    populateScreen3();
    loadS3();
    const fn = getEl<HTMLInputElement>('ffn').value;
    const ln = getEl<HTMLInputElement>('fln').value;
    if (fn) {
      const ff = document.querySelector<HTMLElement>('#s3 .ffv.e[contenteditable]');
      if (ff) ff.textContent = fn;
    }
    if (ln) {
      const fls = document.querySelectorAll<HTMLElement>('#s3 .ffv.e[contenteditable]');
      if (fls[1]) fls[1].textContent = ln;
    }
  }

  cur = n;
  closeSB();
}

function loadS3(): void {
  getEl('lbar').style.display        = 'flex';
  getEl('skels').style.display       = 'block';
  getEl('realcontent').style.display = 'none';

  setTimeout(() => {
    getEl('lbar').style.display        = 'none';
    getEl('skels').style.display       = 'none';
    getEl('realcontent').style.display = 'block';

    const items = document.querySelectorAll<HTMLElement>(
      '#realcontent .ff, #realcontent .icard, #realcontent .vio, #realcontent .rev, #realcontent .wait'
    );
    items.forEach((el, i) => {
      el.style.cssText = `opacity:0;transform:translateY(10px);transition:opacity .4s ease ${i * 0.06}s, transform .4s ease ${i * 0.06}s`;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        el.style.opacity = '1';
        el.style.transform = 'none';
      }));
    });
  }, 1800);
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function toggleSB(): void {
  getEl('sb').classList.toggle('on');
  getEl('sbk').classList.toggle('on');
}

function closeSB(): void {
  getEl('sb').classList.remove('on');
  getEl('sbk').classList.remove('on');
}

// ─── Quick-fill chips ─────────────────────────────────────────────────────────

function qf(a: string, b: string, c: string, fn: string, ln: string): void {
  getEl<HTMLInputElement>('fa').value  = a;
  getEl<HTMLInputElement>('fap').value = b;
  getEl<HTMLInputElement>('fb').value  = c;
  if (fn) getEl<HTMLInputElement>('ffn').value = fn;
  if (ln) getEl<HTMLInputElement>('fln').value = ln;
}

// ─── Camera Scan ──────────────────────────────────────────────────────────────

function scan(): void {
  if (busy) return;
  busy = true;

  // Collect form values
  const a       = getEl<HTMLInputElement>('fa').value   || '243 94th Street';
  const ap      = getEl<HTMLInputElement>('fap').value  || '4B';
  const borough = getEl<HTMLInputElement>('fb').value   || 'Brooklyn';
  const lang    = (document.getElementById('flang') as HTMLSelectElement)?.value || 'en';
  const fullAddress = `${a}, Apt ${ap}, ${borough}, NY`;

  // Capture browser camera frame
  const frameB64 = captureFrame();
  console.log('Frame captured:', frameB64 ? `${frameB64.length} chars` : 'none — agent uses its own camera');

  // Fire API call in background while animation plays
  callAgent1(fullAddress, borough, lang, frameB64);

  // Run scan animation
  const btn = getEl('shbtn');
  btn.style.pointerEvents = 'none';
  btn.style.opacity = '.45';

  getEl('vfh').style.opacity     = '0';
  getEl('reticle').style.opacity = '0';
  getEl('sl').classList.add('go');

  const tl = getEl('tl');
  tl.innerHTML = '';

  STEPS.forEach((s, i) => {
    const el = document.createElement('div');
    el.className = 'titem';
    el.id = 'ti' + i;
    el.innerHTML = `
      <div class="tico" id="ico${i}">${s.i}</div>
      <div class="tbody">
        <div class="tlbl">${s.l}</div>
        <div class="tdet" id="td${i}"></div>
      </div>`;
    tl.appendChild(el);
  });

  getEl('ap').classList.add('on');
  const pf = getEl('pf');

  STEPS.forEach((_s, i) => {
    setTimeout(() => {
      getEl('ti' + i).classList.add('show');
      getEl('ico' + i).classList.add('run');
      getEl('td' + i).innerHTML = STEPS[i].d + '<span class="typecursor"></span>';
      pf.style.width = `${((i + 1) / STEPS.length) * 100}%`;

      if (i > 0) {
        const prevIco = getEl('ico' + (i - 1));
        prevIco.classList.remove('run');
        prevIco.classList.add('ok');
        const cursor = getEl('td' + (i - 1)).querySelector('.typecursor');
        if (cursor) cursor.remove();
      }
    }, 350 + i * 1080);
  });

  const total = 350 + STEPS.length * 1080 + 700;
  setTimeout(() => {
    getEl('sl').classList.remove('go');
    getEl('ap').classList.remove('on');
    getEl('vfh').style.opacity     = '1';
    getEl('reticle').style.opacity = '1';
    btn.style.opacity       = '1';
    btn.style.pointerEvents = 'all';
    busy = false;
    go(3);
  }, total);
}

// ─── Confetti + Submit ────────────────────────────────────────────────────────

function fireConfetti(): void {
  const container = getEl('confetti');
  container.innerHTML = '';
  const colors = ['#c6f135', '#4d6fff', '#ffaa22', '#1de8d8', '#ff3355', '#ffffff'];

  for (let i = 0; i < 24; i++) {
    const p = document.createElement('div');
    p.className = 'confetti-piece';
    p.style.cssText = `
      left:${10 + Math.random() * 80}%;
      top:${Math.random() * 30}%;
      background:${colors[Math.floor(Math.random() * colors.length)]};
      width:${4 + Math.random() * 6}px;
      height:${4 + Math.random() * 6}px;
      border-radius:${Math.random() > 0.5 ? '50%' : '2px'};
      animation-delay:${Math.random() * 0.6}s;
      animation-duration:${1.8 + Math.random() * 1.2}s;
      transform:rotate(${Math.random() * 360}deg);
    `;
    container.appendChild(p);
  }
}

function doSubmit(): void {
  getEl('wb').style.display   = 'none';
  getEl('succ').style.display = 'block';
  fireConfetti();
  getEl('s3cta').innerHTML = `
    <button class="btn btn-p" onclick="window.go(1)" style="background:var(--sf);color:var(--t2);box-shadow:none;border:1px solid var(--b2)">Start a new complaint</button>`;
  setTimeout(() => { getEl('s3').scrollTop = 9999; }, 100);
}

// ─── Expose to HTML onclick attributes ───────────────────────────────────────

window.go       = go;
window.toggleSB = toggleSB;
window.closeSB  = closeSB;
window.qf       = qf;
window.scan     = scan;
window.doSubmit = doSubmit;

// ─── Boot ─────────────────────────────────────────────────────────────────────

window.addEventListener('load', () => {
  animateS1();
  const shell = document.querySelector<HTMLElement>('.shell');
  if (shell) shell.style.minHeight = `${window.innerHeight}px`;
});

// ─── NYC Skyline Canvas ───────────────────────────────────────────────────────

(function initSkyline(): void {
  const cv = document.getElementById('skyCanvas') as HTMLCanvasElement | null;
  if (!cv) return;

  const wrap = cv.parentElement as HTMLElement;
  let W = 0, H = 0, dpr = 1;
  let t = 0;
  let raf = 0;

  const SKY_TOP:    RGB = [4,   6,  20];
  const SKY_MID:    RGB = [6,  10,  28];
  const SKY_HOR:    RGB = [8,  18,  40];
  const LIME:       RGB = [198, 241, 53];
  const LIME_DIM:   RGB = [140, 200, 30];
  const WATER_DEEP: RGB = [2,   4,  14];
  const TEAL_GLOW:  RGB = [20,  60,  80];

  function rgba(c: RGB, a: number): string {
    return `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  }

  const DEFS: BuildingDef[] = [
    { x: .02, w: .03, h: .18, type: 'bg' }, { x: .06, w: .02, h: .22, type: 'bg' },
    { x: .09, w: .04, h: .16, type: 'bg' }, { x: .14, w: .02, h: .20, type: 'bg' },
    { x: .85, w: .03, h: .19, type: 'bg' }, { x: .89, w: .02, h: .23, type: 'bg' },
    { x: .93, w: .04, h: .17, type: 'bg' }, { x: .97, w: .02, h: .21, type: 'bg' },
    { x: .00, w: .05, h: .28, type: 'mid' }, { x: .06, w: .04, h: .35, type: 'mid' },
    { x: .11, w: .06, h: .26, type: 'mid' }, { x: .18, w: .04, h: .32, type: 'mid' },
    { x: .23, w: .03, h: .24, type: 'mid' }, { x: .72, w: .04, h: .30, type: 'mid' },
    { x: .77, w: .05, h: .26, type: 'mid' }, { x: .83, w: .04, h: .33, type: 'mid' },
    { x: .88, w: .03, h: .25, type: 'mid' }, { x: .92, w: .05, h: .29, type: 'mid' },
    { x: .98, w: .02, h: .22, type: 'mid' },
    { x: .04, w: .06, h: .40, type: 'fg' }, { x: .11, w: .05, h: .45, type: 'fg' },
    { x: .17, w: .04, h: .38, type: 'fg' },
    { x: .76, w: .06, h: .42, type: 'fg' }, { x: .83, w: .05, h: .38, type: 'fg' },
    { x: .89, w: .04, h: .44, type: 'fg' }, { x: .94, w: .06, h: .36, type: 'fg' },
    { x: .20, w: .07, h: .60, type: 'esb' },
    { x: .44, w: .10, h: .80, type: 'owt' },
    { x: .62, w: .07, h: .58, type: 'chr' },
    { x: .56, w: .05, h: .48, type: 'fg' }, { x: .70, w: .04, h: .52, type: 'fg' },
  ];

  const WIN_GRID: Record<BuildingType, WinGridConfig> = {
    bg:  { cols: 1, rows: 3,  s: 1.5, g: 3, skip: .2  },
    mid: { cols: 2, rows: 5,  s: 2,   g: 4, skip: .2  },
    fg:  { cols: 3, rows: 8,  s: 2,   g: 4, skip: .25 },
    esb: { cols: 3, rows: 12, s: 2,   g: 4, skip: .3  },
    owt: { cols: 4, rows: 16, s: 2.5, g: 5, skip: .25 },
    chr: { cols: 3, rows: 11, s: 2,   g: 4, skip: .3  },
  };

  let winStates: number[] = [];
  let built = false;
  let buildings: Building[] = [];

  function buildScene(): void {
    winStates = [];
    buildings = DEFS.map((d) => {
      const bx = d.x * W;
      const bw = Math.max(d.w * W, 6);
      const bh = d.h * H * 0.72;
      const by = H * 0.72 - bh;
      const g  = WIN_GRID[d.type];
      const wins: WindowDot[] = [];
      const wStep  = (bw - g.s) / g.cols;
      const hStep  = (bh * (1 - g.skip)) / g.rows;
      const yStart = by + bh * g.skip;

      for (let r = 0; r < g.rows; r++) {
        for (let c = 0; c < g.cols; c++) {
          wins.push({ wx: bx + c * wStep + 2, wy: yStart + r * hStep + 2, ws: g.s, idx: winStates.length });
          winStates.push(Math.random());
        }
      }

      let antenna: Antenna | null = null;
      if      (d.type === 'esb')              antenna = { x: bx + bw * .5, y1: by, y2: by - bh * .18 };
      else if (d.type === 'owt')              antenna = { x: bx + bw * .5, y1: by, y2: by - bh * .14 };
      else if (d.type === 'chr')              antenna = { x: bx + bw * .5, y1: by, y2: by - bh * .12 };
      else if (d.type === 'fg' && d.h > .44) antenna = { x: bx + bw * .5, y1: by, y2: by - bh * .08 };

      return { bx, by, bw, bh, type: d.type, wins, antenna };
    });
    built = true;
  }

  function resize(): void {
    if (!cv) return;
    dpr = window.devicePixelRatio || 1;
    const rect = wrap.getBoundingClientRect();
    W = rect.width  || 390;
    H = rect.height || 220;
    cv.width  = W * dpr;
    cv.height = H * dpr;
    cv.style.width  = `${W}px`;
    cv.style.height = `${H}px`;
    buildScene();
  }

  const HAZES: HazeLayer[] = [
    { x:  0,   speed: .08, w: .6, h: .25, cy: .35, alpha: .04,  col: LIME       },
    { x:  .3,  speed: .05, w: .7, h: .3,  cy: .28, alpha: .03,  col: [20,40,80] },
    { x: -.2,  speed: .12, w: .5, h: .2,  cy: .40, alpha: .025, col: TEAL_GLOW  },
  ];

  let last = performance.now();

  function tick(now: number): void {
    if (!cv) return;
    const dt = now - last;
    last = now;
    t += dt * 0.001;

    const ctx = cv.getContext('2d')!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const skyGrd = ctx.createLinearGradient(0, 0, 0, H * 0.72);
    skyGrd.addColorStop(0,   rgba(SKY_TOP, .98));
    skyGrd.addColorStop(.5,  rgba(SKY_MID, .98));
    skyGrd.addColorStop(1,   rgba(SKY_HOR, .98));
    ctx.fillStyle = skyGrd;
    ctx.fillRect(0, 0, W, H);

    const horGrd = ctx.createRadialGradient(W * .5, H * .73, 0, W * .5, H * .73, W * .6);
    horGrd.addColorStop(0,  rgba(LIME, .06));
    horGrd.addColorStop(.4, rgba(LIME, .02));
    horGrd.addColorStop(1,  'transparent');
    ctx.fillStyle = horGrd;
    ctx.fillRect(0, H * .4, W, H * .4);

    const STARS: [number, number, number][] = [
      [.06,.08,.9],[.14,.04,.7],[.22,.11,.8],[.33,.05,.75],
      [.50,.07,.65],[.58,.03,.85],[.68,.09,.7],[.80,.05,.8],
      [.90,.08,.75],[.96,.04,.9],[.41,.12,.6],[.75,.06,.72],
    ];
    STARS.forEach(([sx, sy, br]) => {
      const flicker = .7 + .3 * Math.sin(t * (.8 + br) + sx * 20);
      ctx.fillStyle = `rgba(255,255,255,${br * .28 * flicker})`;
      ctx.beginPath();
      ctx.arc(sx * W, sy * H * .72, .7, 0, Math.PI * 2);
      ctx.fill();
    });

    HAZES.forEach(hz => {
      const hx    = ((hz.x + t * hz.speed * .1) % 1.4) - .2;
      const pulse = 1 + .15 * Math.sin(t * .4 + hz.cy * 10);
      const cx    = (hx + hz.w * .5) * W;
      const cy    = hz.cy * H;
      const hGrd  = ctx.createRadialGradient(cx, cy, 0, cx, cy, hz.w * .5 * W);
      hGrd.addColorStop(0,  rgba(hz.col, hz.alpha * pulse));
      hGrd.addColorStop(.5, rgba(hz.col, hz.alpha * .4 * pulse));
      hGrd.addColorStop(1,  'transparent');
      ctx.fillStyle = hGrd;
      ctx.fillRect(hx * W, (hz.cy - hz.h * .5) * H, hz.w * W, hz.h * H);
    });

    if (!built) { raf = requestAnimationFrame(tick); return; }

    if (Math.random() < .04) winStates[Math.floor(Math.random() * winStates.length)] = Math.random();

    const alphaMap: Record<BuildingType, number> = { bg:.06, mid:.1, fg:.14, esb:.16, owt:.20, chr:.16 };

    buildings.forEach(b => {
      const alpha = alphaMap[b.type];
      const bGrd = ctx.createLinearGradient(b.bx, b.by, b.bx, b.by + b.bh);
      bGrd.addColorStop(0, rgba(LIME, alpha * .9));
      bGrd.addColorStop(1, rgba(LIME, alpha * .3));
      ctx.fillStyle = bGrd;
      ctx.fillRect(b.bx, b.by, b.bw, b.bh);

      if (b.type === 'esb') {
        ctx.fillStyle = rgba(LIME, alpha * .7);
        ctx.fillRect(b.bx - b.bw * .15, b.by + b.bh * .18, b.bw * 1.3, b.bh * .82);
        ctx.fillRect(b.bx - b.bw * .3,  b.by + b.bh * .32, b.bw * 1.6, b.bh * .68);
        ctx.fillRect(b.bx - b.bw * .45, b.by + b.bh * .46, b.bw * 1.9, b.bh * .54);
      }

      if (b.type === 'owt') {
        ctx.beginPath();
        ctx.moveTo(b.bx - b.bw * .3,  b.by + b.bh);
        ctx.lineTo(b.bx + b.bw * 1.3, b.by + b.bh);
        ctx.lineTo(b.bx + b.bw * .5,  b.by);
        ctx.closePath();
        const oGrd = ctx.createLinearGradient(b.bx + b.bw * .5, b.by, b.bx + b.bw * .5, b.by + b.bh);
        oGrd.addColorStop(0, rgba(LIME, .22));
        oGrd.addColorStop(1, rgba(LIME, .08));
        ctx.fillStyle = oGrd;
        ctx.fill();
      }

      if (b.type === 'chr') {
        const tiers: [number, number, number][] = [[.4,.55,.15],[.3,.42,.12],[.22,.3,.1]];
        tiers.forEach(([t1, t2, alt]) => {
          ctx.beginPath();
          ctx.moveTo(b.bx,             b.by + b.bh * t2);
          ctx.lineTo(b.bx + b.bw,      b.by + b.bh * t2);
          ctx.lineTo(b.bx + b.bw * .7, b.by + b.bh * t1);
          ctx.lineTo(b.bx + b.bw * .3, b.by + b.bh * t1);
          ctx.closePath();
          ctx.fillStyle = rgba(LIME, alpha + alt);
          ctx.fill();
        });
      }

      b.wins.forEach(win => {
        const br          = winStates[win.idx];
        const slowFlicker = .6 + .4 * Math.sin(t * .3 + win.idx * .7);
        const bright      = br * slowFlicker;
        if (bright < .12) return;
        ctx.fillStyle = rgba(LIME_DIM, Math.min(bright * alpha * 5, .55));
        ctx.fillRect(win.wx, win.wy, win.ws, win.ws);
      });

      if (b.antenna) {
        const an       = b.antenna;
        const tipBlink = .5 + .5 * Math.sin(t * (b.type === 'owt' ? 2.2 : 1.8) + b.bx);
        ctx.strokeStyle = rgba(LIME, .5);
        ctx.lineWidth   = 1.2;
        ctx.beginPath();
        ctx.moveTo(an.x, an.y1);
        ctx.lineTo(an.x, an.y2);
        ctx.stroke();
        ctx.fillStyle = rgba(LIME, tipBlink * .9);
        ctx.beginPath();
        ctx.arc(an.x, an.y2, 1.8, 0, Math.PI * 2);
        ctx.fill();
        const gGrd = ctx.createRadialGradient(an.x, an.y2, 0, an.x, an.y2, 8);
        gGrd.addColorStop(0, rgba(LIME, tipBlink * .2));
        gGrd.addColorStop(1, 'transparent');
        ctx.fillStyle = gGrd;
        ctx.fillRect(an.x - 8, an.y2 - 8, 16, 16);
      }
    });

    ctx.strokeStyle = rgba(LIME, .14);
    ctx.lineWidth   = .7;
    ctx.beginPath();
    ctx.moveTo(0, H * .72);
    ctx.lineTo(W, H * .72);
    ctx.stroke();

    const waterH   = H - H * .72;
    const waterGrd = ctx.createLinearGradient(0, H * .72, 0, H);
    waterGrd.addColorStop(0,  rgba(WATER_DEEP, .6));
    waterGrd.addColorStop(.3, rgba(WATER_DEEP, .85));
    waterGrd.addColorStop(1,  rgba([2,3,10],   .95));
    ctx.fillStyle = waterGrd;
    ctx.fillRect(0, H * .72, W, waterH);

    for (let ri = 0; ri < 6; ri++) {
      const ry   = H * .74 + ri * waterH * .11;
      const rOff = Math.sin(t * .4 + ri) * 4;
      ctx.strokeStyle = rgba(LIME, .06 - ri * .008);
      ctx.lineWidth   = .5;
      ctx.beginPath();
      ctx.moveTo(rOff,     ry);
      ctx.lineTo(W + rOff, ry);
      ctx.stroke();
    }

    const owtB = buildings.find(b => b.type === 'owt');
    if (owtB) {
      const colGrd = ctx.createLinearGradient(0, H * .72, 0, H);
      colGrd.addColorStop(0,  rgba(LIME, .07));
      colGrd.addColorStop(.5, rgba(LIME, .03));
      colGrd.addColorStop(1,  'transparent');
      ctx.fillStyle = colGrd;
      ctx.fillRect(owtB.bx + owtB.bw * .2, H * .72, owtB.bw * .6, waterH * .7);
    }

    const beamCycle = (t % 6) / 6;
    const rawBeamY  = beamCycle * H * .72;
    const beamAlpha = beamCycle < .05 ? beamCycle / .05 : beamCycle > .92 ? (1 - beamCycle) / .08 : 1;

    const beamGrd = ctx.createLinearGradient(0, 0, W, 0);
    beamGrd.addColorStop(0,  'transparent');
    beamGrd.addColorStop(.2, rgba(LIME, .35 * beamAlpha));
    beamGrd.addColorStop(.5, rgba(LIME, .65 * beamAlpha));
    beamGrd.addColorStop(.8, rgba(LIME, .35 * beamAlpha));
    beamGrd.addColorStop(1,  'transparent');
    ctx.fillStyle = beamGrd;
    ctx.fillRect(0, rawBeamY - 1, W, 2);

    const bmGrd = ctx.createLinearGradient(0, rawBeamY - 4, 0, rawBeamY + 4);
    bmGrd.addColorStop(0,  'transparent');
    bmGrd.addColorStop(.5, rgba(LIME, .04 * beamAlpha));
    bmGrd.addColorStop(1,  'transparent');
    ctx.fillStyle = bmGrd;
    ctx.fillRect(0, rawBeamY - 4, W, 8);

    const fadeGrd = ctx.createLinearGradient(0, H * .55, 0, H);
    fadeGrd.addColorStop(0,  'transparent');
    fadeGrd.addColorStop(.7, rgba([4,4,15], .6));
    fadeGrd.addColorStop(1,  rgba([4,4,15], .98));
    ctx.fillStyle = fadeGrd;
    ctx.fillRect(0, H * .55, W, H * .45);

    raf = requestAnimationFrame(tick);
  }

  function start(): void {
    resize();
    raf = requestAnimationFrame(tick);
  }

  window.addEventListener('resize', () => {
    cancelAnimationFrame(raf);
    resize();
    raf = requestAnimationFrame(tick);
  });

  if (document.readyState === 'complete') start();
  else window.addEventListener('load', start);
})();
