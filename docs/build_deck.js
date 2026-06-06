/* SolarFit 화면 데이터 설명서 — 밝고 미니멀(화이트 + 딥틸 단일 액센트) */
const pptxgen = require("pptxgenjs");
const path = require("path");

const SHOTS = path.join(__dirname, "shots");
const DIM = {
  "01_site_good.png":      [739, 1245],
  "02_revenue_good.png":   [735, 986],
  "03_site_limited.png":   [742, 1225],
  "04_revenue_limited.png":[731, 972],
  "05_list_top.png":       [730, 1501],
  "06_list_rest.png":      [729, 1145],
};

// ── 팔레트 (밝은 톤, 단일 액센트) ──
const C = {
  bg:    "FFFFFF",
  ink:   "1B2733",   // 제목
  body:  "3C4A54",   // 본문
  muted: "8B98A3",   // 보조
  line:  "E4E9ED",   // 테두리
  panel: "F5F7F9",   // 카드 배경
  accent:"0E7C86",   // 딥 틸 (단일 액센트)
  soft:  "E2F0F1",   // 틸 틴트
  green: "2E9E6B",
  amber: "B8860B",
  red:   "C0564C",
};
const F = "Malgun Gothic";
const W = 13.3, H = 7.5, MX = 0.62;

const pres = new pptxgen();
pres.defineLayout({ name: "WIDE", width: W, height: H });
pres.layout = "WIDE";
pres.author = "SolarFit";
pres.title = "SolarFit 화면 데이터 설명서";

const shadow = () => ({ type: "outer", color: "9AA7B0", blur: 7, offset: 3, angle: 90, opacity: 0.18 });

function bg(s) { s.background = { color: C.bg }; }

function footer(s, n) {
  s.addShape(pres.shapes.LINE, { x: MX, y: 7.06, w: W - 2 * MX, h: 0, line: { color: C.line, width: 1 } });
  s.addText("SolarFit · 화면 데이터 설명서", { x: MX, y: 7.1, w: 6, h: 0.3, fontFace: F, fontSize: 9, color: C.muted, align: "left", margin: 0 });
  s.addText(String(n), { x: W - MX - 0.6, y: 7.1, w: 0.6, h: 0.3, fontFace: F, fontSize: 9, color: C.muted, align: "right", margin: 0 });
}

function header(s, kicker, title) {
  s.addText(kicker.toUpperCase(), { x: MX, y: 0.42, w: W - 2 * MX, h: 0.3, fontFace: F, fontSize: 12, bold: true, color: C.accent, charSpacing: 2, margin: 0 });
  s.addText(title, { x: MX, y: 0.72, w: W - 2 * MX, h: 0.7, fontFace: F, fontSize: 27, bold: true, color: C.ink, margin: 0 });
}

// 출처 태그 (작은 틸 틴트)
function srcTag(s, x, y, text) {
  const w = Math.min(0.42 + text.length * 0.125, 7.5);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.32, rectRadius: 0.06, fill: { color: C.soft }, line: { color: C.soft } });
  s.addText([{ text: "출처  ", options: { bold: true, color: C.accent } }, { text, options: { color: "0B5D64" } }],
    { x: x + 0.12, y, w: w - 0.2, h: 0.32, fontFace: F, fontSize: 9.5, valign: "middle", margin: 0 });
  return w;
}

// 좌측 스크린샷 (높이 맞춤)
function shot(s, file, x, y, maxH) {
  const [ow, oh] = DIM[file];
  const w = maxH * (ow / oh);
  s.addImage({ path: path.join(SHOTS, file), x, y, w, h: maxH });
  // 얇은 테두리 프레임
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h: maxH, fill: { type: "none" }, line: { color: C.line, width: 1 } });
  return w;
}

// 우측 설명 카드
function infoCard(s, x, y, w, h, title, lines, src) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07, fill: { color: C.panel }, line: { color: C.line, width: 1 } });
  s.addShape(pres.shapes.RECTANGLE, { x, y: y + 0.16, w: 0.07, h: h - 0.32, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText(title, { x: x + 0.26, y: y + 0.14, w: w - 0.45, h: 0.5, fontFace: F, fontSize: 13, bold: true, color: C.ink, margin: 0, valign: "top" });
  const body = lines.map((t) => ({ text: t, options: { breakLine: true, color: C.body, paraSpaceAfter: 3 } }));
  s.addText(body, { x: x + 0.26, y: y + 0.64, w: w - 0.5, h: h - (src ? 1.15 : 0.78), fontFace: F, fontSize: 11, color: C.body, valign: "top", margin: 0, lineSpacingMultiple: 1.03 });
  if (src) srcTag(s, x + 0.26, y + h - 0.45, src);
}

// ════════════════════════════ S1 표지 ════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: H, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText("소형 태양광(99kW) 입지·수익 진단", { x: 1.1, y: 2.35, w: 11, h: 0.4, fontFace: F, fontSize: 15, color: C.accent, bold: true, margin: 0 });
  s.addText("SolarFit 화면 데이터 설명서", { x: 1.05, y: 2.75, w: 11.5, h: 1.0, fontFace: F, fontSize: 44, bold: true, color: C.ink, margin: 0 });
  s.addText("화면에 보이는 모든 숫자의 출처와 계산 방식", { x: 1.1, y: 3.85, w: 11, h: 0.5, fontFace: F, fontSize: 18, color: C.body, margin: 0 });
  s.addText("발표 첨부 자료 · 공공데이터 7종 + RAG(AI)", { x: 1.1, y: 4.45, w: 11, h: 0.4, fontFace: F, fontSize: 12.5, color: C.muted, margin: 0 });
  s.addNotes("이 자료는 SolarFit 화면에 보이는 모든 항목의 데이터 출처와 계산 방식을 정리한 발표 첨부 설명서입니다. 핵심 메시지: 모든 숫자는 공공데이터에서 계산하고, AI(RAG)는 '말로 된 조례'를 검색·요약·판정하는 데만 씁니다. 도메인을 모르는 분도 이해할 수 있도록 구성했습니다.");
}

// ════════════════════════════ S2 3화면 한눈에 ════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  header(s, "한눈에", "입력 한 줄 → 세 화면으로 자동 분기");
  const cards = [
    ["지번 입력", "충남 논산시 … 충곡리 200", "부지 단일 진단", "이 땅, 태양광 돼? 뭐가 걸려?"],
    ["시군구명 포함", "당진에 변전소 여유 있어?", "지역 단위 진단", "이 지역 규제·계통·지원은?"],
    ["일반 질문", "충남에서 좋은 곳 추천해줘", "추천 리스트", "충남 어디가 제일 좋아?"],
  ];
  const cw = (W - 2 * MX - 2 * 0.4) / 3;
  cards.forEach((c, i) => {
    const x = MX + i * (cw + 0.4), y = 1.75;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: 3.5, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: C.line, width: 1.2 }, shadow: shadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: cw, h: 0.12, fill: { color: C.accent }, line: { color: C.accent } });
    s.addText(c[0], { x: x + 0.28, y: y + 0.35, w: cw - 0.5, h: 0.4, fontFace: F, fontSize: 15, bold: true, color: C.accent, margin: 0 });
    s.addText("예) " + c[1], { x: x + 0.28, y: y + 0.85, w: cw - 0.5, h: 0.6, fontFace: F, fontSize: 12, italic: true, color: C.muted, margin: 0 });
    s.addText(c[2], { x: x + 0.28, y: y + 1.6, w: cw - 0.5, h: 0.5, fontFace: F, fontSize: 18, bold: true, color: C.ink, margin: 0 });
    s.addText(c[3], { x: x + 0.28, y: y + 2.2, w: cw - 0.5, h: 0.9, fontFace: F, fontSize: 12.5, color: C.body, margin: 0 });
  });
  s.addText("흩어진 공공데이터를 한 부지 기준으로 모아 자동 종합합니다.", { x: MX, y: 5.6, w: W - 2 * MX, h: 0.5, fontFace: F, fontSize: 14, bold: true, color: C.ink, align: "center", margin: 0 });
  s.addNotes("입력 한 줄로 자동 분기합니다. (1) 끝에 번지 숫자가 있으면 '지번'으로 보고 부지 단일 진단, (2) 질문에 충남 시군구명(당진·천안 등)이 있으면 그 지역 단위 진단, (3) 그 외 일반 질문은 충남 추천 랭킹. 화면이 하나라 사용자는 검색창에 자연어로 묻기만 하면 됩니다. 추천 리스트에서 일조/발전 관련 질문은 수익성 화면으로 연결됩니다.");
  footer(s, 2);
}

// ════════════════════════════ S3 데이터 출처 한눈에 ════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  header(s, "데이터 출처", "화면의 모든 숫자는 공공데이터에서");
  const rows = [
    ["연 일사량 (5년·경사면)", "KMAPP .nc (기상청)", "발전량 · 일조 점수"],
    ["계통 여유용량", "한국전력 KEPCO 빅데이터", "계통 충분 / 부족"],
    ["자치법규 본문", "국가법령정보 (law.go.kr)", "지자체 지원 (RAG)"],
    ["조례 별표 (이격 수치)", "조례 첨부 HWP → 추출", "이격거리 기준"],
    ["토지이용계획", "VWorld (국토교통부)", "용도지역 · 농지"],
    ["SMP / REC 단가 (2025)", "전력거래소 KPX", "수익 계산"],
    ["행정 · 법정동 코드", "행정안전부 code.go.kr", "지역키 · 지번→PNU"],
  ];
  const head = [
    { text: "데이터", options: { bold: true, color: "FFFFFF", fill: { color: C.accent }, align: "left" } },
    { text: "원천 (공공)", options: { bold: true, color: "FFFFFF", fill: { color: C.accent }, align: "left" } },
    { text: "화면에서 쓰이는 곳", options: { bold: true, color: "FFFFFF", fill: { color: C.accent }, align: "left" } },
  ];
  const body = rows.map((r, i) => r.map(t => ({ text: t, options: { color: C.body, fill: { color: i % 2 ? "FFFFFF" : C.panel }, align: "left" } })));
  s.addTable([head, ...body], {
    x: MX, y: 1.7, w: W - 2 * MX, colW: [4.3, 4.0, 3.76], rowH: 0.46,
    fontFace: F, fontSize: 12.5, valign: "middle", border: { type: "solid", pt: 1, color: C.line },
    margin: [3, 8, 3, 8],
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 6.0, w: W - 2 * MX, h: 0.82, rectRadius: 0.07, fill: { color: C.soft }, line: { color: C.soft } });
  s.addText([
    { text: "AI 모델  ", options: { bold: true, color: C.accent } },
    { text: "text-embedding-3-small (의미검색) · gpt-4o-mini (답변·종합판정)", options: { color: "0B5D64" } },
    { text: "      AI는 검색·요약·판정만, 숫자는 전부 공공데이터 계산.", options: { bold: true, color: C.ink } },
  ], { x: MX + 0.25, y: 6.0, w: W - 2 * MX - 0.5, h: 0.82, fontFace: F, fontSize: 12.5, valign: "middle", margin: 0 });
  s.addNotes("7종 출처 상세 — ① KMAPP 경사면 일사량(.nc, SWDN_topo, 2016~2021 5년 평균·전국 시군구 격자). ② 한국전력 KEPCO 빅데이터 분산전원 API(변전소·변압기·배전선로 여유용량). ③ 국가법령정보 자치법규 본문검색(search=2)으로 수집해 4,251개 조항을 벡터DB(ChromaDB)에 적재. ④ 이격 수치는 조례 '별표'가 HWP 첨부라 olefile로 직접 추출. ⑤ VWorld(국토부) 토지이용계획 API는 필지 PNU로 조회(domain 파라미터 필수). ⑥ 전력거래소 KPX SMP/REC 2025 단가. ⑦ 행정안전부 코드로 시군구키(229건)·지번→PNU 변환. AI 비용은 질문당 약 0.9원.");
  footer(s, 3);
}

// 공통: 좌측 스크린샷 + 우측 2×2 카드 그리드
function shotSlide(n, kicker, title, file, cards, footnote, notes) {
  const s = pres.addSlide(); bg(s);
  header(s, kicker, title);
  const imgY = 1.62, imgH = footnote ? 4.55 : 5.0;
  const iw = shot(s, file, MX, imgY, imgH);
  const rx = MX + iw + 0.5;
  const rw = W - rx - MX;
  const cols = 2, rows = Math.ceil(cards.length / cols);
  const gx = 0.28, gy = 0.26;
  const cw = (rw - (cols - 1) * gx) / cols;
  const ch = (imgH - (rows - 1) * gy) / rows;
  cards.forEach((c, i) => {
    const cx = rx + (i % cols) * (cw + gx);
    const cy = imgY + Math.floor(i / cols) * (ch + gy);
    infoCard(s, cx, cy, cw, ch, c[0], c[1], c[2]);
  });
  if (footnote) {
    s.addText(footnote, { x: MX, y: imgY + imgH + 0.14, w: W - 2 * MX, h: 0.5, fontFace: F, fontSize: 11.5, italic: true, color: C.muted, align: "center", margin: 0 });
  }
  if (notes) s.addNotes(notes);
  footer(s, n);
  return s;
}

// ════════════════════════════ S4 입지진단 개요 ════════════════════════════
shotSlide(4, "화면 ① 입지 진단", "한 부지를 통째로 — 4가지를 한 번에", "01_site_good.png", [
  ["① 종합 판정 (AI)", ["gpt-4o-mini가 이격·용도지역·지원을 종합", "‘가능/조건부/어려움 + 근거 + 확인필요’"], "gpt-4o-mini (RAG 근거)"],
  ["② 입지 규제 6칸", ["이격 4종 + 용도지역 + 농지", "법으로 정한 기준과 토지 정보"], "조례·별표 + VWorld"],
  ["③ 지자체 지원", ["조례를 검색해 보조금·융자 안내", "근거 조항까지 표기"], "자치법규 RAG"],
  ["④ 계통 여유용량", ["그 지역 변전소·배전선로 여유(kW)", "99kW 연계 가능 여부"], "한국전력 KEPCO"],
], "주소 한 줄 → 5개 출처를 모아 → AI가 마지막에 종합합니다.",
"화면은 diagnose(주소)를 한 번 호출하고 결과 dict를 카드에 매핑만 합니다. 내부에서 주소→지역코드 변환, 이격(별표 데이터 조회), 지자체 지원(RAG 검색), 용도지역(VWorld), 종합판정(LLM)을 모두 처리합니다. 즉 흩어진 5개 출처를 모아 AI가 마지막에 2~3문장으로 종합합니다. 용도지역/농지는 실존 필지(PNU)가 있어야 나오므로, 시군구 단위 진단에서는 '지번 입력 시'로 안내합니다.");

// ════════════════════════════ S5 입지 규제 기준 vs 실측 ════════════════════════════
shotSlide(5, "화면 ① 입지 규제", "‘기준’은 제공하고, ‘실측’은 정직하게 표시", "01_site_good.png", [
  ["이격거리 (4종)", ["도로·주거·관광지·부지경계", "조문(AI 검색)+별표(HWP) / 값=최소 기준거리"], "조례 조문 + 별표 HWP"],
  ["용도지역 · 농지", ["계획관리=가능 / 농림·농업진흥=불가", "필지(PNU) 단위 실시간 조회"], "VWorld 토지이용계획"],
  ["★ 기준 vs 실측", ["기준거리는 제공 ✅  /  실제 거리는 GIS 필요", "→ ‘실측 필요’로 과장 없이 표시"], null],
  ["별표까지 판 차별점", ["당진·보령·홍성·태안은 조문엔 없고", "별표(HWP)에만 있던 규제 — 끝까지 추출"], null],
], null,
"이격 기준은 data/byeolpyo/setback.json(충남 15개 시군구)에서 옵니다. 난이도는 주거밀집 최대 이격 기준으로 분류(500m↑=높음 / 300m=보통 / 200m↓·없음=낮음). 조문에 있는 곳도 있고, 당진·보령·홍성·태안처럼 조문엔 없고 별표(HWP 첨부)에만 있어 olefile로 직접 추출한 곳도 있습니다. 용도지역·농지는 VWorld 토지이용계획에서 가져와 계획관리=가능/농림·농업진흥=불가로 매핑. 핵심: 기준거리는 제공하지만 실제 이격거리는 GIS가 있어야 재므로 '실측 필요'로 정직하게 표기합니다.");

// ════════════════════════════ S6 좋은 vs 제약 ════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  header(s, "화면 ① 대조", "같은 엔진, 부지마다 다른 판정");
  const imgH = 4.5, y = 1.7;
  const x1 = 1.6, w1 = shot(s, "01_site_good.png", x1, y, imgH);
  const x2 = 7.5, w2 = shot(s, "03_site_limited.png", x2, y, imgH);
  // 라벨 칩
  function chip(x, w, text, col) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + (w - 3.0) / 2, y: y - 0.02, w: 3.0, h: 0.42, rectRadius: 0.1, fill: { color: col }, line: { color: col } });
    s.addText(text, { x: x + (w - 3.0) / 2, y: y - 0.02, w: 3.0, h: 0.42, fontFace: F, fontSize: 12, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0 });
  }
  s.addText("충곡리 200 — 계획관리지역", { x: x1 - 0.3, y: y + imgH + 0.12, w: w1 + 0.6, h: 0.4, fontFace: F, fontSize: 14, bold: true, color: C.green, align: "center", margin: 0 });
  s.addText("농지 규제 없음 · 태양광 가능", { x: x1 - 0.3, y: y + imgH + 0.5, w: w1 + 0.6, h: 0.4, fontFace: F, fontSize: 12, color: C.body, align: "center", margin: 0 });
  s.addText("서산 부장리 100 — 농림지역", { x: x2 - 0.3, y: y + imgH + 0.12, w: w2 + 0.6, h: 0.4, fontFace: F, fontSize: 14, bold: true, color: C.red, align: "center", margin: 0 });
  s.addText("농지 해당 · 제약 큼 (실데이터)", { x: x2 - 0.3, y: y + imgH + 0.5, w: w2 + 0.6, h: 0.4, fontFace: F, fontSize: 12, color: C.body, align: "center", margin: 0 });
  s.addNotes("같은 엔진이 부지에 따라 다르게 판정함을 보여줍니다. 왼쪽 충곡리 200은 계획관리지역·농지 없음이라 '가능' 쪽. 오른쪽 서산 부장리 100은 '농림지역'(태양광 원칙 불가)·농지 해당이라 제약이 큰 부지입니다. 둘 다 실제 VWorld·조례 데이터로 나온 결과입니다. 참고: 현재 LLM 종합판정이 농림지역도 '조건부 가능'으로 다소 약하게 보는 경향이 있어, 발표 전 '농림/농업진흥=원칙 불가' 규칙 보강을 검토 중입니다.");
  footer(s, 6);
}

// ════════════════════════════ S7 RAG & 계통 흐름 (다이어그램) ════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  header(s, "화면 ① 작동 원리", "지자체 지원(RAG) · 계통 여유(KEPCO)");
  // 좌: RAG flow
  const steps = ["질문", "의미검색 + 키워드검색", "조례 조항 회수", "AI 답변 + 근거 조항"];
  const bx = MX, by = 2.0, bw = 5.5, bh = 0.7, bgap = 0.3;
  s.addText("지자체 지원 — RAG (검색증강생성)", { x: bx, y: 1.55, w: 6, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: C.accent, margin: 0 });
  steps.forEach((t, i) => {
    const yy = by + i * (bh + bgap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: yy, w: bw, h: bh, rectRadius: 0.07, fill: { color: i === steps.length - 1 ? C.soft : C.panel }, line: { color: C.line, width: 1 } });
    s.addText(t, { x: bx + 0.2, y: yy, w: bw - 0.4, h: bh, fontFace: F, fontSize: 13, bold: i === steps.length - 1, color: C.ink, valign: "middle", margin: 0 });
    if (i < steps.length - 1) s.addText("▼", { x: bx + bw / 2 - 0.2, y: yy + bh + 0.02, w: 0.4, h: bgap, fontFace: F, fontSize: 12, color: C.accent, align: "center", margin: 0 });
  });
  s.addText("시군구 60% + 광역 40% 쿼터로 그 지역 자체 조례를 반드시 포함", { x: bx, y: by + 4 * (bh + bgap) - 0.05, w: bw, h: 0.5, fontFace: F, fontSize: 10.5, italic: true, color: C.muted, margin: 0 });
  // 우: 계통 계산
  const rx = 7.2, rw = W - rx - MX;
  s.addText("계통 여유 — KEPCO", { x: rx, y: 1.55, w: rw, h: 0.35, fontFace: F, fontSize: 14, bold: true, color: C.accent, margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: rx, y: 2.0, w: rw, h: 1.5, rectRadius: 0.08, fill: { color: C.panel }, line: { color: C.line, width: 1 } });
  s.addText([
    { text: "한 지점 연계가능 용량 = ", options: { color: C.body } },
    { text: "min(변전소, 변압기, 배전선로)", options: { bold: true, color: C.ink } },
  ], { x: rx + 0.25, y: 2.2, w: rw - 0.5, h: 0.5, fontFace: F, fontSize: 13, margin: 0 });
  s.addText("→ 그 시군구의 최댓값 = 단일 연계 가능 최대량 (kW)", { x: rx + 0.25, y: 2.75, w: rw - 0.5, h: 0.5, fontFace: F, fontSize: 12, color: C.body, margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: rx, y: 3.7, w: rw, h: 1.5, rectRadius: 0.08, fill: { color: C.soft }, line: { color: C.soft } });
  s.addText("99kW 연계 기준 판정", { x: rx + 0.25, y: 3.85, w: rw - 0.5, h: 0.4, fontFace: F, fontSize: 13, bold: true, color: C.accent, margin: 0 });
  s.addText([
    { text: "충분", options: { bold: true, color: C.green } }, { text: " (≥9,000kW)   ", options: { color: C.body } },
    { text: "보통", options: { bold: true, color: C.amber } }, { text: "   ", options: {} },
    { text: "부족", options: { bold: true, color: C.red } },
  ], { x: rx + 0.25, y: 4.3, w: rw - 0.5, h: 0.5, fontFace: F, fontSize: 13, margin: 0 });
  s.addText("DB 적재 없이 KEPCO 응답(JSON)을 직접 조회", { x: rx + 0.25, y: 4.75, w: rw - 0.5, h: 0.4, fontFace: F, fontSize: 11, italic: true, color: C.muted, margin: 0 });
  s.addNotes("지자체 지원은 하이브리드 검색(의미 임베딩 + 키워드)을 RRF로 합쳐 정답 조항을 회수하고, 시군구 60% + 광역 40% 쿼터로 그 지역 자체 조례를 반드시 포함합니다. 답변 끝 [N] 번호로 실제 인용한 조항만 출처로 표기해 환각을 줄입니다. 계통은 KEPCO 응답에서 각 지점의 연계가능량 = min(변전소·변압기·배전선로) 여유로 보고, 그 시군구 최댓값을 단일 연계 최대량으로 씁니다. 99kW 기준 약 9,000kW 이상이면 '충분'.");
  footer(s, 7);
}

// ════════════════════════════ S8 수익성 발전량 ════════════════════════════
shotSlide(8, "화면 ② 수익성", "발전량은 이렇게 나온다", "02_revenue_good.png", [
  ["① 연 일사량 → 발전시간", ["연 일사량(MJ/㎡) ÷ 3.6 = 표준 발전시간(h)"], "기상청 ASOS"],
  ["② 시스템 효율 반영", ["× PR 0.85 (손실 보정) = 연간 발전시간"], null],
  ["③ 설비 용량 곱", ["× 99kW = 연간 발전량(kWh)"], null],
  ["한 줄 요약", ["햇빛(기상청) → 발전시간 → 용량 곱 → 1년 발전량"], null],
], null,
"발전량 공식: 연 일사량(MJ/㎡) ÷ 3.6 = 표준 발전시간(h), × PR 0.85(시스템효율 보정), × 99kW = 연간 발전량(kWh). 예) 충곡리 200(논산)은 약 1,428h, 약 141,300kWh, 이용률 약 16%. 일조량은 KMAPP 경사면 일사량(전국 시군구·5년 평균)이라 시군구마다 고유값이며, 과거 ASOS 방식의 '인근 관측소 보강'이 불필요해졌습니다.");

// ════════════════════════════ S9 수익·투자지표 + 가정치 ════════════════════════════
shotSlide(9, "화면 ② 수익성", "수익 · 투자지표 + 가정치(정직하게)", "04_revenue_limited.png", [
  ["SMP 수익", ["발전량 × SMP 단가 (KPX 2025 연평균)"], "전력거래소 KPX"],
  ["REC 수익", ["(발전량/1000) × 가중치 1.2 × REC 단가"], "전력거래소 KPX"],
  ["투자 지표", ["연수익 → 손익분기 · 20년 총수익 · 예금 대비"], null],
  ["⚠ 가정치 (협의 대기)", ["투자비 2.2억 · PR 0.85", "일사량 보정(+1,014만)은 이중계산 소지로 제거"], null],
], null,
"SMP 수익 = 발전량 × SMP 단가(KPX 2025 연평균 약 112.68원/kWh). REC 수익 = (발전량/1000) × 가중치 1.2 × REC 단가. 연 예상수익에서 손익분기(투자비÷연수익)·20년 총수익·예금(3%) 대비를 계산합니다. 투자비 2.2억·PR 0.85는 가정치이며 팀 협의 대기. 과거 '일사량 보정(+1,014만)'은 발전량에 일조가 이미 반영돼 이중계산 소지가 있어 제거했습니다 — '가정은 가정이라고 밝힌다'가 신뢰 포인트입니다.");

// ════════════════════════════ S10 추천 점수 공식 ════════════════════════════
shotSlide(10, "화면 ③ 추천", "종합점수 = 일조 40 + 계통 35 + 규제 25", "05_list_top.png", [
  ["가중치 (합 100)", ["일조량 40% · 계통 여유 35% · 규제 난이도 25%"], null],
  ["정규화 (충남 내 상대평가)", ["일조·계통 = (값−최저)/(최고−최저)×100", "규제 = 난이도(낮음100 / 보통60 / 높음25)"], null],
  ["화면의 작은 숫자", ["‘일조 40 · 계통 35 · 규제 25’ = 항목별 기여분", "세 기여분의 합 = 종합점수"], null],
  ["한 줄 요약", ["충남 15개 시군구를 같은 잣대로 줄 세움"], "기상청·KEPCO·조례"],
], null,
"종합점수 = 0.40×일조 + 0.35×계통 + 0.25×규제. 일조·계통은 충남 15개 시군구 안에서 (값−최저)/(최고−최저)×100으로 정규화한 상대점수, 규제는 난이도 등급(낮음 100/보통 60/높음 25). 화면의 작은 '일조 40·계통 35·규제 25'는 각 항목 기여분이며 그 합이 종합점수입니다. 전국 절대평가가 아니라 충남 내 상대 줄세우기입니다.");

// ════════════════════════════ S11 정렬·동점·색상 ════════════════════════════
shotSlide(11, "화면 ③ 추천", "정렬 · 동점 · 색상으로 읽기", "06_list_rest.png", [
  ["정렬 의도 자동 인식", ["질문에 ‘규제/계통/일조’가 있으면 그 기준으로 정렬"], null],
  ["동점 처리", ["규제가 다 같으면(예: 다 ‘낮음’) 종합점수로 가름", "→ 천안 1위"], null],
  ["색상 의미", ["일조 ±%(충남 평균 대비, +초록/−노랑)", "계통 충분/보통/부족 · 규제 낮음/보통/높음"], null],
  ["바로 이동", ["카드 우하단 ↗ → 그 시군구 지역 진단으로"], null],
], null,
"질문에 '규제/계통/일조' 같은 의도 키워드가 있으면 그 기준으로 정렬합니다. 규제가 모두 같으면(예: 다 '낮음') 종합점수(일조+계통)로 동점을 가립니다 — 그래서 천안이 1위. 일조량 옆 ±%는 충남 평균 대비 편차로 +는 초록·−는 노랑. (전국 경사면 데이터라 시군구마다 일조가 달라 색이 갈림 — 예: 아산·천안 높음(+), 보령·서천 낮음(−)) 카드 우하단 ↗는 그 시군구 지역 진단으로 이동(내부적으로 URL 파라미터 라우팅)합니다.");

// ════════════════════════════ S12 RAG O/X 경계 ════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  header(s, "설계 원칙", "무엇이 AI이고, 무엇이 데이터인가");
  const colW = (W - 2 * MX - 0.5) / 2;
  const y = 1.8, hh = 3.7;
  // RAG
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y, w: colW, h: hh, rectRadius: 0.08, fill: { color: C.soft }, line: { color: C.soft } });
  s.addText("RAG (AI 검색·생성)", { x: MX + 0.3, y: y + 0.25, w: colW - 0.6, h: 0.45, fontFace: F, fontSize: 17, bold: true, color: C.accent, margin: 0 });
  s.addText([
    { text: "지자체 지원 (보조금·융자)", options: { bullet: true, breakLine: true } },
    { text: "이격 ‘기준’ 해석", options: { bullet: true, breakLine: true } },
    { text: "종합 판정문 (가능/조건부/어려움)", options: { bullet: true } },
  ], { x: MX + 0.3, y: y + 0.9, w: colW - 0.6, h: hh - 1.1, fontFace: F, fontSize: 14, color: C.body, margin: 0, paraSpaceAfter: 8 });
  // 정형
  const x2 = MX + colW + 0.5;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x2, y, w: colW, h: hh, rectRadius: 0.08, fill: { color: C.panel }, line: { color: C.line, width: 1 } });
  s.addText("정형 데이터 (계산)", { x: x2 + 0.3, y: y + 0.25, w: colW - 0.6, h: 0.45, fontFace: F, fontSize: 17, bold: true, color: C.ink, margin: 0 });
  s.addText([
    { text: "일조량 (기상청)", options: { bullet: true, breakLine: true } },
    { text: "계통 여유 (한국전력)", options: { bullet: true, breakLine: true } },
    { text: "용도지역·농지 (VWorld)", options: { bullet: true, breakLine: true } },
    { text: "수익 (공식 계산)", options: { bullet: true } },
  ], { x: x2 + 0.3, y: y + 0.9, w: colW - 0.6, h: hh - 1.1, fontFace: F, fontSize: 14, color: C.body, margin: 0, paraSpaceAfter: 8 });
  s.addText("AI는 ‘말로 된 조례’를 읽는 데만, 숫자는 전부 공공데이터 계산 — 환각(없는 수치 지어내기) 방지 설계", { x: MX, y: 5.85, w: W - 2 * MX, h: 0.6, fontFace: F, fontSize: 14, bold: true, color: C.ink, align: "center", margin: 0 });
  s.addNotes("설계 원칙: AI(RAG)는 '말로 된 조례'를 읽어 지자체 지원·이격 기준 해석·종합 판정문을 만드는 데만 쓰고, 일조·계통·용도지역·수익 같은 숫자는 전부 공공데이터로 계산합니다. 이렇게 역할을 나눠 AI가 없는 수치를 지어내는 '환각'을 막습니다. 임베딩은 text-embedding-3-small, 생성은 gpt-4o-mini를 씁니다.");
  footer(s, 12);
}

// ════════════════════════════ S13 신뢰성 & 한계 ════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  header(s, "신뢰성", "한계를 숨기지 않는다");
  const items = [
    ["실측은 미제공", "이격 실거리·진입로·변전소 매칭은 GIS 필요 → ‘확인 필요’로 표시(기준만 제공)"],
    ["일조량 정밀도", "전국 경사면(KMAPP 5년)이라 시군구 고유값 — 단 부지 미시지형·차폐는 미반영"],
    ["수익 가정치", "투자비 2.2억·PR 0.85는 팀 협의 대기값 (일사량 보정은 이중계산 소지로 제거)"],
    ["범위", "현재 충남 15개 시군구 (전국 확장 가능한 구조)"],
  ];
  const y0 = 1.8, ih = 1.05, ig = 0.2;
  items.forEach((it, i) => {
    const y = y0 + i * (ih + ig);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y, w: W - 2 * MX, h: ih, rectRadius: 0.07, fill: { color: C.panel }, line: { color: C.line, width: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x: MX, y: y + 0.14, w: 0.07, h: ih - 0.28, fill: { color: C.accent }, line: { color: C.accent } });
    s.addText(it[0], { x: MX + 0.3, y, w: 3.3, h: ih, fontFace: F, fontSize: 15, bold: true, color: C.ink, valign: "middle", margin: 0 });
    s.addText(it[1], { x: MX + 3.7, y, w: W - 2 * MX - 4.0, h: ih, fontFace: F, fontSize: 12.5, color: C.body, valign: "middle", margin: 0 });
  });
  s.addNotes("한계를 명확히 합니다. ① 이격 실거리·진입로·인근 변전소 매칭은 GIS가 없어 미제공('확인 필요'로 표시). ② 일조량은 전국 시군구 경사면 일사량(KMAPP 5년 평균) — 시군구 평균이라 부지 미시지형·차폐는 미반영. ③ 투자비·PR은 가정치(일사량 보정은 이중계산 소지로 제거). ④ 현재 충남 15개 시군구 대상(전국 확장 가능 구조). 의사결정 보조도구로서 한계를 숨기지 않는 것이 신뢰의 핵심입니다.");
  footer(s, 13);
}

// ════════════════════════════ S14 마무리 ════════════════════════════
{
  const s = pres.addSlide(); bg(s);
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: H, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText("주소 한 줄로 시작하는", { x: 1.1, y: 1.7, w: 11, h: 0.7, fontFace: F, fontSize: 28, color: C.body, margin: 0 });
  s.addText("태양광 사업성 진단", { x: 1.05, y: 2.35, w: 11.5, h: 1.0, fontFace: F, fontSize: 46, bold: true, color: C.ink, margin: 0 });
  const stats = [["공공 API", "7종"], ["1주 운영비", "약 200원"], ["구동 환경", "로컬 PC + 인터넷"]];
  const cw = 3.6, gap = 0.5, total = stats.length * cw + (stats.length - 1) * gap, sx = 1.1;
  stats.forEach((st, i) => {
    const x = sx + i * (cw + gap), y = 4.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: 1.5, rectRadius: 0.08, fill: { color: C.panel }, line: { color: C.line, width: 1 } });
    s.addText(st[1], { x: x + 0.2, y: y + 0.25, w: cw - 0.4, h: 0.7, fontFace: F, fontSize: 26, bold: true, color: C.accent, margin: 0 });
    s.addText(st[0], { x: x + 0.2, y: y + 1.0, w: cw - 0.4, h: 0.4, fontFace: F, fontSize: 13, color: C.muted, margin: 0 });
  });
  s.addText("SolarFit", { x: 1.1, y: 6.2, w: 6, h: 0.5, fontFace: F, fontSize: 16, bold: true, color: C.accent, margin: 0 });
  s.addNotes("마무리: 공공 API 7종 + 로컬 ChromaDB + OpenAI로 로컬 PC와 인터넷만으로 동작하고, 1주 운영비는 약 200원입니다. 확장 방향은 전국 시군구, 발전소 허가·보급현황 데이터, GIS 연계(이격 실측 거리)입니다.");
}

const OUT = path.join(__dirname, process.env.DECK_OUT || "SolarFit_화면설명서.pptx");
pres.writeFile({ fileName: OUT }).then(() => console.log("WROTE", OUT));
