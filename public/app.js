const defaultSeoNotes = `AI 检索曝光内容策略：
1. 首段给出可被引用的直接答案，避免空泛开场。
2. 明确商品实体：商品类型、品牌、目标用户、使用场景、规格、替代品。
3. 使用自然语言问题作为 H2/H3，覆盖购买前常见追问。
4. 增加证据密度：规格、材质、价格区间、测试方法、客户反馈、限制条件。
5. 使用表格、清单、FAQ、适用/不适用人群，让 AI 更容易抽取结构化答案。
6. 保持人类编辑口吻：写具体场景、取舍、限制，减少模板化营销词。
7. 输出 Markdown，标题层级稳定，方便发布到 Shopify 或博客系统。`;

const PRODUCT_SUGGESTION_SETS = {
  zh: [
    ["手摇咖啡磨豆机", "家用咖啡器具购买指南", "突出研磨一致性、便携、和电动磨豆机对比"],
    ["不锈钢保温杯", "通勤与户外场景种草", "突出保温时长、容量、杯盖、防漏和清洁"],
    ["护肤精华", "成分科普 + 购买建议", "突出适用肤质、核心成分、使用顺序和敏感肌限制"],
    ["露营灯", "露营装备清单型 Blog", "突出续航、亮度、防水、挂装方式和安全性"],
    ["人体工学办公椅", "久坐人群改善指南", "突出腰托、坐垫、调节范围和不同身高适配"],
    ["宠物自动喂食器", "养宠省心方案", "突出定时投喂、容量、防卡粮、清洁和远程控制"],
    ["儿童学习桌", "成长型家具选购", "突出高度调节、桌面角度、收纳和用眼距离"],
    ["空气炸锅", "小厨房健康烹饪内容", "突出容量、温控、清洁、食谱和油烟减少"],
    ["智能门锁", "家庭安全升级 Blog", "突出指纹识别、临时密码、电池续航和应急开锁"],
    ["瑜伽垫", "居家运动入门推荐", "突出厚度、防滑、材质、收纳和不同运动强度"],
    ["蓝牙降噪耳机", "通勤办公效率提升", "突出降噪、佩戴舒适、麦克风、续航和多设备连接"],
    ["母婴背带", "新手爸妈出行指南", "突出承托、安全扣、透气和不同月龄适配"],
    ["便携投影仪", "租房和露营影音场景", "突出亮度、分辨率、系统、音响和投射距离"],
    ["家用筋膜枪", "运动恢复科普", "突出力度档位、噪音、按摩头、禁忌人群"],
    ["旅行收纳袋", "行李整理效率指南", "突出分区、防水、压缩、不同旅行天数搭配"],
    ["猫砂盆", "除臭和清洁体验内容", "突出空间、除臭、清理方式和猫咪适应期"],
    ["厨房刀具套装", "家庭料理升级", "突出钢材、握柄、刀型组合和维护方式"],
    ["电动牙刷", "口腔护理对比指南", "突出刷头、模式、压力提醒、续航和敏感牙适配"]
  ],
  en: [
    ["manual coffee grinder", "home coffee buying guide", "focus on grind consistency, portability, electric grinder comparison"],
    ["insulated water bottle", "commute and outdoor product story", "focus on temperature retention, capacity, leak resistance, cleaning"],
    ["vitamin C serum", "ingredient education and buying guide", "focus on skin type, actives, routine order, sensitivity limits"],
    ["camping lantern", "camping gear checklist blog", "focus on runtime, brightness, waterproofing, mounting, safety"],
    ["ergonomic office chair", "long-sitting comfort guide", "focus on lumbar support, cushion, adjustability, body fit"],
    ["automatic pet feeder", "stress-free pet care guide", "focus on schedule, capacity, anti-jam design, cleaning, app control"],
    ["kids study desk", "grow-with-me furniture guide", "focus on height adjustment, tilt, storage, eye distance"],
    ["air fryer", "healthy small-kitchen cooking guide", "focus on capacity, temperature control, cleaning, recipes"],
    ["smart door lock", "home security upgrade blog", "focus on fingerprint, temporary codes, battery life, emergency access"],
    ["yoga mat", "home workout starter guide", "focus on thickness, grip, material, storage, workout style"],
    ["noise-canceling earbuds", "commute and office productivity guide", "focus on ANC, comfort, mic quality, battery, multipoint"],
    ["baby carrier", "new parent travel guide", "focus on support, buckles, breathability, age fit"],
    ["portable projector", "apartment and camping entertainment guide", "focus on brightness, resolution, OS, audio, throw distance"],
    ["massage gun", "sports recovery education", "focus on intensity, noise, attachments, contraindications"],
    ["travel packing cubes", "luggage organization guide", "focus on compartments, waterproofing, compression, trip length"],
    ["self-cleaning litter box", "odor and cleaning experience blog", "focus on space, odor control, cleaning, cat adaptation"],
    ["kitchen knife set", "home cooking upgrade guide", "focus on steel, handle, knife types, care"],
    ["electric toothbrush", "oral care comparison guide", "focus on brush heads, modes, pressure alerts, battery, sensitive teeth"]
  ],
};

const SEARCH_SUGGESTION_SETS = {
  zh: [
    "适合/不适合人群",
    "和热门竞品表格对比",
    "规格、材质、价格区间",
    "维护成本和使用寿命",
    "真实使用场景",
    "购买前常见顾虑",
    "首段给出可引用答案",
    "限制条件和避坑说明",
    "FAQ 覆盖长尾问题",
    "品牌差异化卖点"
  ],
  en: [
    "best fit / not a fit",
    "comparison table with competitors",
    "specs, materials, price range",
    "maintenance cost and lifespan",
    "real use cases",
    "pre-purchase concerns",
    "AI-citable opening answer",
    "limitations and caveats",
    "FAQ for long-tail questions",
    "brand differentiation points"
  ],
};

function suggestion(product, angle, audience, market, goal, note, keywords) {
  return { product, angle, audience, market, goal, note, keywords };
}

function normalizeProductSuggestion(item, language) {
  if (Array.isArray(item)) {
    const [product, angle, note] = item;
    return suggestion(
      product,
      angle,
      language === "en" ? "online shoppers comparing product options" : "正在比较同类产品的电商买家",
      language === "en" ? "United States / English-speaking markets" : "中国 / 北美 / 跨境电商市场",
      angle,
      note,
      language === "en"
        ? `${product}; ${angle}; specs; comparison; FAQ; buying guide; limitations`
        : `${product}；${angle}；规格参数；竞品对比；FAQ；购买建议；限制说明`
    );
  }
  return item;
}

function productSuggestionPool(language) {
  const base = PRODUCT_SUGGESTION_SETS[language] || PRODUCT_SUGGESTION_SETS.zh;
  const extras = language === "en" ? [
    suggestion("standing desk converter", "workspace upgrade guide", "remote workers, freelancers, and small office buyers", "United States / Canada", "SEO blog for ergonomic work setup conversion", "cover height range, desktop space, monitor compatibility, stability, and who should avoid it", "standing desk converter; ergonomic office setup; remote work accessories; comparison table; cable management; warranty"),
    suggestion("portable power station", "outdoor and emergency power guide", "campers, RV owners, and homeowners preparing for outages", "United States / Australia", "AI-search visibility for outdoor power products", "cover battery capacity, AC output, solar charging, appliance runtime, and safety limits", "portable power station; solar generator; camping power; emergency backup; runtime chart; watt-hour"),
    suggestion("protein shaker bottle", "fitness routine product blog", "gym beginners, meal-prep users, and supplement buyers", "United States / Europe", "content-led product promotion for fitness ecommerce", "cover leak resistance, mixing ball design, odor control, capacity, and cleaning", "protein shaker; gym bottle; leak-proof; BPA-free; odor control; supplement routine"),
    suggestion("smart plant watering kit", "indoor gardening automation guide", "apartment renters, busy plant owners, and gift buyers", "United States / UK", "educational blog for smart home gardening", "cover watering schedules, pot compatibility, sensors, app alerts, and plant types", "smart plant watering; indoor gardening; self-watering system; plant care; app control"),
    suggestion("compression packing cubes", "travel organization guide", "business travelers, family vacation planners, and carry-on-only travelers", "United States / Europe", "blog for travel accessory conversion", "cover compression ratio, fabric, zippers, suitcase fit, and trip-length bundles", "packing cubes; compression travel organizer; carry-on packing; luggage space; travel checklist")
  ] : [
    suggestion("便携储能电源", "露营与应急用电指南", "露营玩家、房车用户、家庭应急备电人群", "中国 / 北美 / 澳大利亚", "提升户外电源类目在 AI 搜索中的曝光", "覆盖电池容量、输出功率、太阳能充电、可带动设备、航空/安全限制", "便携储能电源；户外电源；太阳能充电；露营用电；应急备电；功率表"),
    suggestion("升降桌", "居家办公效率升级 Blog", "远程办公、程序员、设计师、久坐办公人群", "中国 / 北美 / 欧洲", "用内容教育推动办公家具转化", "覆盖承重、升降范围、桌板尺寸、电机噪音、稳定性和适合身高", "升降桌；人体工学办公；久坐改善；桌面收纳；双电机；承重"),
    suggestion("蛋白摇摇杯", "健身补剂日常使用指南", "健身新手、通勤健身人群、补剂消费者", "中国 / 北美", "推广健身配件并覆盖长尾搜索", "覆盖防漏、搅拌结构、异味清洁、容量、材质安全和使用场景", "蛋白摇摇杯；健身水杯；防漏；BPA-free；清洁除味；补剂"),
    suggestion("智能植物浇水器", "室内绿植自动养护指南", "公寓租客、忙碌上班族、绿植礼品买家", "中国 / 北美 / 欧洲", "推广智能家居园艺产品", "覆盖浇水计划、花盆兼容、传感器、App 提醒和适用植物", "智能浇水器；室内绿植；自动浇水；植物养护；App 控制"),
    suggestion("压缩旅行收纳袋", "行李空间整理指南", "商务差旅、家庭旅行、只带登机箱的用户", "中国 / 北美 / 欧洲", "推广旅行收纳配件并增加搜索索引", "覆盖压缩比例、面料、拉链、箱型适配、不同天数套装建议", "压缩收纳袋；旅行收纳；登机箱整理；防水面料；行李空间")
  ];
  return [...base.map((item) => normalizeProductSuggestion(item, language)), ...extras];
}

const state = {
  config: null,
  currentBlog: null,
  blogs: [],
  productFileText: "",
  images: [],
  imageMode: "manual",
  searchResults: [],
  analysisSearchResults: [],
  intentOptions: [],
  selectedIntentId: "",
  titleOptions: [],
  titleStrategy: null,
  selectedTitleId: "",
  selectedTitleText: "",
  selectedTitleTrack: "both",
  selectedCitationRefs: new Set(),
  compareSelectedBlogIds: new Set(),
  compareResult: null,
  apiProfiles: [],
  customerSources: [],
  outline: null,
  trainingResult: null,
  wizardStep: 0,
  selectedTrainingBlog: null,
  recommendationHistory: [],
  outlineSubStep: "search",
  editingPromptIds: new Set()
};

const busyTasks = new Set();
const taskTimers = new Map();
const taskControllers = new Map();
const openLibraryGroups = new Set();
const openTrainingGroups = new Set();
let renameDialogState = null;
let messageDialogState = null;
let titleTooltipEl = null;

function normalizeElementId(id) {
  const language = document.getElementById("language")?.value === "en" ? "en" : "zh";
  const suffix = language === "en" ? "En" : "Zh";
  const legacyPromptIds = {
    outlinePrompt: `outlinePrompt${suffix}`,
    articlePrompt: `articlePrompt${suffix}`,
    optimizerPrompt: `optimizerPrompt${suffix}`,
    revisionPrompt: `revisionPrompt${suffix}`,
    trainingEvaluatorPrompt: `trainingEvaluatorPrompt${suffix}`,
    promptModifierPrompt: `promptModifierPrompt${suffix}`,
    searchPlannerPrompt: `searchPlannerPrompt${suffix}`,
    entityExtractorPrompt: `entityExtractorPrompt${suffix}`,
    titlePrompt: `titlePrompt${suffix}`,
  };
  return legacyPromptIds[id] || id;
}

const $ = (id) => document.getElementById(normalizeElementId(id));

function requireEl(id) {
  const element = $(id);
  if (!element) {
    throw new Error(`页面结构未加载完整，缺少 #${id}。请刷新页面后重试。`);
  }
  return element;
}

function on(id, eventName, handler, options) {
  const element = $(id);
  if (!element) {
    console.warn(`[bindEvents] missing #${id}`);
    return false;
  }
  element.addEventListener(eventName, handler, options);
  return true;
}

function bindAll(selector, eventName, handler, root = document) {
  root.querySelectorAll(selector).forEach((element) => {
    element.addEventListener(eventName, handler);
  });
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fullTitleTip(value) {
  const text = String(value || "Untitled").trim() || "Untitled";
  return `<span class="fullTitleTip" data-full-title="${escapeHtml(text)}" tabindex="0">${escapeHtml(text)}</span>`;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString();
}

function dateOnlyTimestamp(value, endOfDay = false) {
  if (!value) return null;
  const date = new Date(`${value}T${endOfDay ? "23:59:59.999" : "00:00:00"}`);
  const time = date.getTime();
  return Number.isNaN(time) ? null : time;
}

function blogSearchText(blog) {
  return [
    blog.title,
    blog.groupName,
    blog.productType,
    blog.versionLabel,
    blog.score,
    ...(blog.tags || []),
  ].join(" ").toLowerCase();
}

function filteredBlogGroups({ query = "", dateField = "updatedAt", from = "", to = "" } = {}) {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  const fromTime = dateOnlyTimestamp(from);
  const toTime = dateOnlyTimestamp(to, true);
  const blogs = state.blogs.filter((blog) => {
    if (normalizedQuery && !blogSearchText(blog).includes(normalizedQuery)) return false;
    const rawDate = blog[dateField] || blog.createdAt;
    const blogTime = rawDate ? new Date(rawDate).getTime() : null;
    if (fromTime && (!blogTime || blogTime < fromTime)) return false;
    if (toTime && (!blogTime || blogTime > toTime)) return false;
    return true;
  });
  const groups = [];
  const groupMap = new Map();
  blogs.forEach((blog) => {
    const groupId = blog.groupId || blog.id;
    if (!groupMap.has(groupId)) {
      const group = { id: groupId, name: blog.groupName || blog.title || "Untitled", blogs: [], createdAt: blog.createdAt, updatedAt: blog.updatedAt || blog.createdAt };
      groupMap.set(groupId, group);
      groups.push(group);
    }
    const group = groupMap.get(groupId);
    group.blogs.push(blog);
    const createdTime = new Date(blog.createdAt || 0).getTime();
    const groupCreatedTime = new Date(group.createdAt || 0).getTime();
    if (createdTime && (!groupCreatedTime || createdTime < groupCreatedTime)) group.createdAt = blog.createdAt;
    const updatedTime = new Date(blog.updatedAt || blog.createdAt || 0).getTime();
    const groupUpdatedTime = new Date(group.updatedAt || 0).getTime();
    if (updatedTime && updatedTime > groupUpdatedTime) group.updatedAt = blog.updatedAt || blog.createdAt;
  });
  return groups;
}

function toDisplayList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => {
      if (item && typeof item === "object") return JSON.stringify(item);
      return String(item || "").trim();
    }).filter(Boolean);
  }
  if (value && typeof value === "object") {
    return Object.entries(value).map(([key, item]) => `${key}: ${typeof item === "object" ? JSON.stringify(item) : item}`).filter(Boolean);
  }
  if (typeof value === "string") {
    return value.split(/\n|；|;|。/).map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function listHtml(items, wrapper = "span") {
  const safeItems = toDisplayList(items);
  if (!safeItems.length) return "";
  return safeItems.map((item) => `<li><${wrapper}>${escapeHtml(item)}</${wrapper}></li>`).join("");
}

function uid() {
  return `api_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function createProgress(label = "请求处理中...") {
  return `
    <div class="progressBox" role="status" aria-live="polite">
      <div class="progressMeta">
        <span>${escapeHtml(label)}</span>
        <b class="progressPercent">0%</b>
      </div>
      <div class="progressTrack"><span style="width:0%"></span></div>
    </div>`;
}

function attachStopButton(task, progressEl) {
  if (!progressEl || progressEl.querySelector(".stopTaskButton")) return;
  const button = document.createElement("button");
  button.className = "dangerButton stopTaskButton";
  button.type = "button";
  button.textContent = "停止";
  button.addEventListener("click", () => stopTask(task));
  progressEl.querySelector(".progressBox")?.appendChild(button);
}

function setProgress(container, percent, label = "") {
  if (!container) return;
  const bar = container.querySelector(".progressTrack span");
  const text = container.querySelector(".progressMeta span");
  const number = container.querySelector(".progressPercent");
  const value = Math.max(0, Math.min(100, Math.round(percent)));
  if (bar) bar.style.width = `${value}%`;
  if (number) number.textContent = `${value}%`;
  if (label && text) text.textContent = label;
}

// ── training progress state ──────────────────────────────────────────────────
const _trainProgress = { startTime: null, timerHandle: null };

function _trainElapsed() {
  if (!_trainProgress.startTime) return "";
  const s = Math.floor((Date.now() - _trainProgress.startTime) / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s/60)}m${s%60}s`;
}

function resetTrainProgress() {
  if (_trainProgress.timerHandle) { clearInterval(_trainProgress.timerHandle); _trainProgress.timerHandle = null; }
  _trainProgress.startTime = null;
}

function renderTrainingProgress(event) {
  const progress = requireEl("trainingProgress");
  progress.hidden = false;

  // Init on first event
  if (!_trainProgress.startTime) {
    _trainProgress.startTime = Date.now();
    progress.innerHTML =
      `<div class="progressBox" role="status" aria-live="polite">` +
      `<div class="progressMeta"><span class="trainMsg">准备迭代…</span><span class="trainElapsed"></span><b class="progressPercent">0%</b></div>` +
      `<div class="progressTrack"><span style="width:0%"></span></div>` +
      `</div>`;
    attachStopButton("training", progress);
    _trainProgress.timerHandle = setInterval(() => {
      const el = progress.querySelector(".trainElapsed");
      if (el) el.textContent = _trainElapsed();
    }, 1000);
  }

  const total = Number(event.totalRounds || requireEl("trainingRounds")?.value || 1);
  const round = Math.max(0, Number(event.round || 0));
  const stageWeights = { outline: 0, generate: 0.15, evaluate: 0.38, modify: 0.62, modify_segment: 0.62, modify_segment_done: 0.62, round_done: 1, done: 1 };
  let stageWeight = stageWeights[event.stage] ?? 0.05;
  if ((event.stage === "modify_segment" || event.stage === "modify_segment_done") && event.totalSegments) {
    const segment = Math.max(0, Number(event.segment || 0) - (event.stage === "modify_segment" ? 1 : 0));
    stageWeight = 0.62 + (segment / Number(event.totalSegments)) * 0.33;
  }
  const percent = event.stage === "done" ? 100 : ((Math.max(0, round - 1) + stageWeight) / total) * 100;

  const stageLabels = {
    outline: "准备样本",
    generate: "生成文章（大模型生成中）",
    evaluate: "评价打分（调用评分模型 + GPTZero）",
    modify: "优化正文（大模型修改中）",
    modify_segment: "分段优化正文",
    modify_segment_done: "分段优化完成",
    round_done: "本轮完成",
    done: "迭代完成",
    error: "迭代出错"
  };
  const stageName = stageLabels[event.stage] || event.message || "迭代中";
  const scoreText = event.score != null ? ` · 得分 ${event.score}` : "";
  const roundText = event.round ? `第 ${event.round}/${total} 轮` : "准备";
  const segmentText = event.totalSegments ? ` · 第 ${event.segment}/${event.totalSegments} 段` : "";

  const bar = progress.querySelector(".progressTrack span");
  const text = progress.querySelector(".trainMsg");
  const num  = progress.querySelector(".progressPercent");
  const elapsed = progress.querySelector(".trainElapsed");
  const value = Math.max(0, Math.min(100, Math.round(percent)));
  if (bar)  bar.style.width = value + "%";
  if (text) text.textContent = `${roundText} · ${stageName}${segmentText}${scoreText}`;
  if (num)  num.textContent  = value + "%";
  if (elapsed) elapsed.textContent = _trainElapsed();

  if (event.stage === "done") {
    if (_trainProgress.timerHandle) { clearInterval(_trainProgress.timerHandle); _trainProgress.timerHandle = null; }
  }

  renderTrainingStageList(event, total);
}

function renderTrainingStageList(event, total) {
  let panel = $("trainingStageList");
  if (!panel) {
    panel = document.createElement("div");
    panel.id = "trainingStageList";
    panel.className = "stageList";
    requireEl("trainingProgress").appendChild(panel);
  }
  if (event.stage === "outline") {
    panel.innerHTML = "";
  }
  const key = `${event.round || 0}-${event.stage}-${event.segment || 0}`;
  if (panel.querySelector(`[data-stage-key="${key}"]`)) return;
  const item = document.createElement("div");
  item.className = `stageItem ${event.type === "error" || event.stage === "error" ? "stageError" : ""}`;
  item.dataset.stageKey = key;
  item.innerHTML = `<b>${escapeHtml(event.round ? `第 ${event.round}/${total} 轮` : "准备")}</b><span>${escapeHtml(event.message || "处理中")}${event.score ? ` · 分数 ${escapeHtml(event.score)}` : ""}</span>`;
  panel.prepend(item);
}

// ── generate progress state ──────────────────────────────────────────────────
const _genProgress = {
  startTime: null,
  timerHandle: null,
  steps: [],        // [{key, label, status: pending|running|done}]
  currentStep: null,
};

const _GEN_STEPS = [
  { key: "outline",            label: "准备大纲" },
  { key: "seo_article",        label: "生成 SEO 正文" },
  { key: "geo_article",        label: "生成 GEO 正文" },
  { key: "auto_iter_score0",   label: "初始版本评分" },
  { key: "auto_iter_revise",   label: "AI 优化正文" },
  { key: "auto_iter_score1",   label: "优化版本重新评分" },
  { key: "done",               label: "完成" },
];

function _genElapsed() {
  if (!_genProgress.startTime) return "";
  const s = Math.floor((Date.now() - _genProgress.startTime) / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s/60)}m${s%60}s`;
}

function _renderGenStepList() {
  const progress = requireEl("generateProgress");
  let panel = progress.querySelector(".genStepList");
  if (!panel) {
    panel = document.createElement("div");
    panel.className = "genStepList";
    progress.appendChild(panel);
  }
  panel.innerHTML = _genProgress.steps.map(step => {
    const icon = step.status === "done" ? "✓" : step.status === "running" ? "⏳" : "○";
    const cls  = step.status === "done" ? "genStepDone" : step.status === "running" ? "genStepRunning" : "genStepPending";
    const elapsed = step.elapsed;
    const timeStr = elapsed != null
      ? (elapsed < 1000 ? ` ${elapsed}ms` : ` ${(elapsed/1000).toFixed(1)}s`)
      : "";
    const timeHtml = step.status === "done" && timeStr
      ? `<em class="stepTime">${timeStr}</em>` : "";
    return `<span class="${cls}">${icon} ${escapeHtml(step.label)}${timeHtml}</span>`;
  }).join("");
}

function _startGenTimer(progressEl) {
  if (_genProgress.timerHandle) return;
  _genProgress.timerHandle = setInterval(() => {
    const el = progressEl.querySelector(".genElapsed");
    if (el) el.textContent = _genElapsed();
  }, 1000);
}

function _stopGenTimer() {
  if (_genProgress.timerHandle) { clearInterval(_genProgress.timerHandle); _genProgress.timerHandle = null; }
}

function resetGenProgress() {
  _stopGenTimer();
  _genProgress.startTime = null;
  _genProgress.steps = [];
  _genProgress.currentStep = null;
}

function renderGenerateProgress(event) {
  const progress = requireEl("generateProgress");
  progress.hidden = false;

  // Init on first event
  if (!_genProgress.startTime) {
    _genProgress.startTime = Date.now();
    _genProgress.steps = _GEN_STEPS.map(s => ({ ...s, status: "pending" }));
    progress.innerHTML =
      `<div class="progressBox" role="status" aria-live="polite">` +
      `<div class="progressMeta"><span class="genMsg">正在初始化…</span><span class="genElapsed"></span><b class="progressPercent">0%</b></div>` +
      `<div class="progressTrack"><span style="width:0%"></span></div>` +
      `</div>`;
    attachStopButton("generate", progress);
    _startGenTimer(progress);
  }

  // Map backend stage → step key
  const stageToKey = {
    outline: "outline", outline_done: "outline",
    seo_article: "seo_article", article_whole: "seo_article", article_whole_done: "seo_article",
    geo_article: "geo_article",
    auto_iter_score0: "auto_iter_score0",
    auto_iter_revise: "auto_iter_revise",
    auto_iter_score1: "auto_iter_score1",
    done: "done",
  };
  const stepKey = stageToKey[event.stage];

  // Update step statuses
  if (stepKey) {
    let passed = false;
    _genProgress.steps = _genProgress.steps.map(s => {
      if (s.key === stepKey) { passed = true; return { ...s, status: "running", startedAt: Date.now() }; }
      if (!passed) return { ...s, status: "done", elapsed: s.startedAt ? Date.now() - s.startedAt : s.elapsed };
      return s;
    });
    if (event.stage === "done") {
      _genProgress.steps = _genProgress.steps.map(s => ({ ...s, status: "done", elapsed: s.elapsed || (s.startedAt ? Date.now() - s.startedAt : undefined) }));
    }
  }

  // Percent
  let percent = Number(event.percent || 0);
  if (event.stage === "done") percent = 100;

  // Label — show backend message as primary, append elapsed
  const msg = event.message || "正在生成正文";
  const scoreHint = event.score != null ? ` (得分 ${Number(event.score).toFixed(1)})` : "";
  const elapsedEl = progress.querySelector(".genElapsed");
  if (elapsedEl) elapsedEl.textContent = _genElapsed();

  // Update bar + text
  const bar = progress.querySelector(".progressTrack span");
  const text = progress.querySelector(".genMsg");
  const num  = progress.querySelector(".progressPercent");
  const value = Math.max(0, Math.min(100, Math.round(percent)));
  if (bar) bar.style.width = value + "%";
  if (text) text.textContent = msg + scoreHint;
  if (num)  num.textContent  = value + "%";

  // Render step list
  _renderGenStepList();

  if (event.stage === "done") _stopGenTimer();
}

function startBusy(task, button, progressEl, label) {
  if (busyTasks.has(task)) return false;
  busyTasks.add(task);
  const controller = new AbortController();
  taskControllers.set(task, controller);
  button.dataset.originalText = button.textContent;
  button.disabled = true;
  button.textContent = label;
  if (progressEl) {
    progressEl.hidden = false;
    progressEl.innerHTML = createProgress(label);
    attachStopButton(task, progressEl);
    let value = 3;
    setProgress(progressEl, value, label);
    if (task !== "training") {
      taskTimers.set(task, setInterval(() => {
        value = Math.min(72, value + Math.max(1, Math.ceil((72 - value) / 18)));
        setProgress(progressEl, value, label);
      }, 2200));
    }
  }
  return true;
}

function taskSignal(task) {
  return taskControllers.get(task)?.signal;
}

function stopTask(task) {
  const controller = taskControllers.get(task);
  if (!controller || controller.signal.aborted) return;
  controller.abort();
}

function isAbortError(error) {
  return error?.name === "AbortError";
}

function finishBusy(task, button, progressEl, label = "完成") {
  clearInterval(taskTimers.get(task));
  taskTimers.delete(task);
  taskControllers.delete(task);
  if (progressEl) {
    setProgress(progressEl, 100, label);
    setTimeout(() => {
      progressEl.hidden = true;
      progressEl.innerHTML = "";
    }, 700);
  }
  button.disabled = false;
  button.textContent = button.dataset.originalText || button.textContent;
  busyTasks.delete(task);
}

function failBusy(task, button, progressEl, message = "请求失败") {
  clearInterval(taskTimers.get(task));
  taskTimers.delete(task);
  taskControllers.delete(task);
  if (progressEl) {
    setProgress(progressEl, 100, message);
    setTimeout(() => {
      progressEl.hidden = true;
      progressEl.innerHTML = "";
    }, 1500);
  }
  button.disabled = false;
  button.textContent = button.dataset.originalText || button.textContent;
  busyTasks.delete(task);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || "Request failed");
  return data;
}

async function streamApi(path, body, onEvent, signal) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || data.error || "Request failed");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.split("\n").find((item) => item.startsWith("data: "));
      if (!line) continue;
      onEvent(JSON.parse(line.slice(6)));
    }
  }
}

function inlineMarkdown(text) {
  return String(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(.+?)\]\((https?:\/\/.+?)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
}

function renderMarkdown(markdown) {
  let html = escapeHtml(markdown || "");
  const blocks = [];
  html = html.replace(/```([\s\S]*?)```/g, (_, code) => {
    const id = blocks.push(`<pre><code>${code}</code></pre>`) - 1;
    return `@@BLOCK${id}@@`;
  });
  html = html.replace(/^\|(.+)\|\n\|([\s:-]+\|)+\n((?:\|.*\|\n?)+)/gm, (match) => {
    const rows = match.trim().split("\n");
    const heads = rows[0].split("|").slice(1, -1).map((cell) => cell.trim());
    const body = rows.slice(2).map((row) => row.split("|").slice(1, -1).map((cell) => cell.trim()));
    return `<table><thead><tr>${heads.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${body
      .map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`)
      .join("")}</tbody></table>`;
  });
  html = html
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^> (.+)$/gm, "<blockquote>$1</blockquote>")
    .replace(/^\d+\.\s+(.+)$/gm, "<li>$1</li>")
    .replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html
    .split(/\n{2,}/)
    .map((chunk) => {
      if (/^<\/?(h1|h2|h3|table|blockquote|pre|ul|li)/.test(chunk) || chunk.includes("<table>")) return chunk;
      if (/^<li>/.test(chunk)) return `<ul>${chunk}</ul>`;
      return `<p>${inlineMarkdown(chunk).replace(/\n/g, "<br>")}</p>`;
    })
    .join("\n");
  return html.replace(/@@BLOCK(\d+)@@/g, (_, id) => blocks[Number(id)]);
}

function extractJsonLdBlocks(markdown) {
  const blocks = [];
  const cleaned = String(markdown || "").replace(/## JSON-LD Schema\s*```json\s*([\s\S]*?)```/g, (_, jsonText) => {
    const trimmed = jsonText.trim();
    try {
      JSON.parse(trimmed);
      blocks.push(trimmed);
    } catch {
      blocks.push(trimmed);
    }
    return "";
  });
  return { markdown: cleaned.trim(), jsonLdBlocks: blocks };
}

function markdownToHtmlDocument(markdown, title = "Blog Preview") {
  const extracted = extractJsonLdBlocks(markdown);
  const bodyHtml = renderMarkdown(extracted.markdown || markdown || "");
  const scripts = extracted.jsonLdBlocks
    .map((block) => `<script type="application/ld+json">${block.replace(/<\/script/gi, "<\\/script")}</script>`)
    .join("\n");
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(title)}</title>
  ${scripts}
  <style>
    body { margin: 0; background: #fbf7ed; color: #26231d; font-family: Inter, "Microsoft YaHei", Arial, sans-serif; line-height: 1.72; }
    main { max-width: 880px; margin: 0 auto; padding: 42px 28px 72px; background: rgba(255,255,255,.72); min-height: 100vh; box-sizing: border-box; }
    h1 { font-size: 34px; line-height: 1.18; margin: 0 0 24px; }
    h2 { font-size: 24px; margin: 34px 0 12px; }
    h3 { font-size: 19px; margin: 24px 0 10px; }
    p { margin: 0 0 16px; }
    a { color: #2164d8; }
    table { width: 100%; border-collapse: collapse; margin: 18px 0; background: #fff; }
    th, td { border: 1px solid #ded7c8; padding: 10px; text-align: left; }
    pre { white-space: pre-wrap; overflow: auto; background: #1f2937; color: #f8fafc; padding: 16px; border-radius: 12px; }
    img { max-width: 100%; border-radius: 14px; }
  </style>
</head>
<body>
  <main>${bodyHtml}</main>
</body>
</html>`;
}

function renderArticleView(mode = state.articleViewMode || "markdown") {
  const article = requireEl("markdownOutput").value || state.currentBlog?.article || "";
  const preview = requireEl("markdownPreview");
  state.articleViewMode = mode === "html" ? "html" : "markdown";
  document.querySelectorAll(".articleViewSwitch button").forEach((button) => {
    button.classList.toggle("isActive", button.dataset.view === state.articleViewMode);
  });
  if (state.articleViewMode === "html") {
    const title = state.currentBlog?.title || state.currentBlog?.groupName || "Blog Preview";
    const doc = markdownToHtmlDocument(article, title);
    preview.innerHTML = `<iframe class="htmlPreviewFrame" title="HTML 预览"></iframe>`;
    const frame = preview.querySelector("iframe");
    frame.srcdoc = doc;
  } else {
    preview.innerHTML = renderMarkdown(article);
  }
}

function activePrompts() {
  const language = $("language").value;
  return state.config?.prompts?.[language] || {};
}

function promptFieldIds(language) {
  const suffix = language === "en" ? "En" : "Zh";
  return {
    outline: `outlinePrompt${suffix}`,
    title: `titlePrompt${suffix}`,
    entity_extractor: `entityExtractorPrompt${suffix}`,
    article: `articlePrompt${suffix}`,
    optimizer: `optimizerPrompt${suffix}`,
    revision: `revisionPrompt${suffix}`,
    training_evaluator: `trainingEvaluatorPrompt${suffix}`,
    prompt_modifier: `promptModifierPrompt${suffix}`,
    search_planner: `searchPlannerPrompt${suffix}`,
  };
}

function setPromptSystemFields(language, prompts = {}) {
  const ids = promptFieldIds(language);
  Object.entries(ids).forEach(([key, id]) => {
    if ($(id)) {
      requireEl(id).value = prompts[key] || "";
      setPromptEditMode(id, false, { silent: true });
    }
  });
}

function collectPromptSystem(language) {
  const ids = promptFieldIds(language);
  return {
    outline: $(ids.outline)?.value || "",
    title: $(ids.title)?.value || "",
    entity_extractor: $(ids.entity_extractor)?.value || "",
    article: $(ids.article)?.value || "",
    optimizer: $(ids.optimizer)?.value || "",
    revision: $(ids.revision)?.value || "",
    training_evaluator: $(ids.training_evaluator)?.value || "",
    prompt_modifier: $(ids.prompt_modifier)?.value || "",
    search_planner: $(ids.search_planner)?.value || "",
  };
}

function setPromptEditMode(id, editing, options = {}) {
  const textarea = $(id);
  if (!textarea) return;
  const card = textarea.closest(".promptEditorCard");
  const button = card?.querySelector(".promptEditToggle");
  textarea.readOnly = !editing;
  card?.classList.toggle("isEditing", editing);
  if (button) button.textContent = editing ? "完成修改" : "修改";
  if (editing) {
    state.editingPromptIds.add(id);
    textarea.focus();
  } else {
    state.editingPromptIds.delete(id);
  }
  if (!options.silent && !editing) {
    showMessage("Prompt 修改已暂存，点击“保存全局设置”后正式生效。", { title: "修改完成", eyebrow: "Prompt", variant: "success" });
  }
}

function togglePromptEditor(button) {
  const id = button?.dataset?.target;
  if (!id || !$(id)) return;
  setPromptEditMode(id, requireEl(id).readOnly);
}

function closePromptEditors() {
  document.querySelectorAll(".promptEditToggle[data-target]").forEach((button) => {
    const id = button.dataset.target;
    if (id) setPromptEditMode(id, false, { silent: true });
  });
}

function selectSettingsPage(page) {
  const target = page || "basic";
  document.querySelectorAll(".settingsTab").forEach((button) => {
    button.classList.toggle("isActive", button.dataset.settingsPage === target);
  });
  document.querySelectorAll(".settingsPage").forEach((panel) => {
    panel.classList.toggle("isActive", panel.dataset.settingsPagePanel === target);
  });
}

function prettyJson(value, fallback = {}) {
  try {
    return JSON.stringify(value && typeof value === "object" ? value : fallback, null, 2);
  } catch {
    return JSON.stringify(fallback, null, 2);
  }
}

function parseJsonField(id, fallback = {}) {
  const raw = $(id)?.value?.trim() || "";
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : fallback;
  } catch {
    throw new Error(`${id} 不是有效 JSON。`);
  }
}

function parseCustomerSourceText(raw) {
  return String(raw || "").split(/\r?\n/).map((line) => {
    const trimmed = line.trim();
    if (!trimmed) return null;
    const parts = trimmed.split(/\s*[,\t|]\s*/).map((part) => part.trim()).filter(Boolean);
    const url = parts.find((part) => /^https?:\/\//i.test(part)) || (trimmed.match(/https?:\/\/[^\s,|]+/i)?.[0] || "");
    if (!url) return null;
    const rest = parts.filter((part) => part !== url);
    return { url, title: rest[0] || "", note: rest[1] || "" };
  }).filter(Boolean);
}

function customerSourceToText(source) {
  return (source?.urls || []).map((item) => [item.url, item.title, item.note].filter(Boolean).join(" | ")).join("\n");
}

function setPromptFields() {
  const prompts = state.config?.prompts || {};
  setPromptSystemFields("zh", prompts.zh || {});
  setPromptSystemFields("en", prompts.en || {});
  const search = state.config?.searchSettings || {};
  if ($("searxngEndpoint")) requireEl("searxngEndpoint").value = search.searxngEndpoint || "";
  if ($("rankerEndpoint")) requireEl("rankerEndpoint").value = search.rankerEndpoint || "";
  if ($("searchMaxResults")) requireEl("searchMaxResults").value = search.maxResults || 15;
  if ($("searchTimeoutSeconds")) requireEl("searchTimeoutSeconds").value = search.timeoutSeconds || 25;
  if ($("searxngEnabled")) requireEl("searxngEnabled").checked = search.searxngEnabled !== false;
  if ($("rankerEnabled")) requireEl("rankerEnabled").checked = search.rankerEnabled !== false;
  if ($("domainWeights")) requireEl("domainWeights").value = prettyJson(search.domainWeights, {});
  state.customerSources = Array.isArray(search.customerSources) ? search.customerSources : [];
  renderCustomerSources();
  const gptzero = state.config?.gptZeroSettings || {};
  if ($("gptZeroEnabled")) requireEl("gptZeroEnabled").checked = Boolean(gptzero.enabled);
  if ($("gptZeroEndpoint")) requireEl("gptZeroEndpoint").value = gptzero.endpoint || "";
  if ($("gptZeroApiKey")) {
    const keyEl = requireEl("gptZeroApiKey");
    // contenteditable div — use textContent, not .value
    keyEl.textContent = gptzero.apiKey || "";
  }
  if ($("gptZeroWeight")) requireEl("gptZeroWeight").value = gptzero.weight ?? 0.35;
  if ($("gptZeroTimeoutSeconds")) requireEl("gptZeroTimeoutSeconds").value = gptzero.timeoutSeconds || 60;
  if ($("gptZeroHeadChars")) requireEl("gptZeroHeadChars").value = gptzero.headChars || 500;
  if ($("gptZeroTailChars")) requireEl("gptZeroTailChars").value = gptzero.tailChars || 500;
}

function seededShuffle(items) {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
  }
  return copy;
}

function renderSearchSuggestions() {
  const language = requireEl("outputLanguage").value || "zh";
  const productSuggestions = seededShuffle(productSuggestionPool(language)).slice(0, 5);
  requireEl("productSuggestionCards").innerHTML = productSuggestions
    .map((item) => `
      <button class="productSuggestionCard" type="button"
        data-product="${escapeHtml(item.product)}"
        data-angle="${escapeHtml(item.angle)}"
        data-audience="${escapeHtml(item.audience)}"
        data-market="${escapeHtml(item.market)}"
        data-goal="${escapeHtml(item.goal)}"
        data-note="${escapeHtml(item.note)}"
        data-keywords="${escapeHtml(item.keywords)}">
        <span>${escapeHtml(item.product)}</span>
        <b>${escapeHtml(item.angle)}</b>
        <small>${escapeHtml(item.market)} · ${escapeHtml(item.audience)}</small>
      </button>`)
    .join("");
  document.querySelectorAll(".productSuggestionCard").forEach((button) => {
    button.addEventListener("click", () => applyProductSuggestion(button.dataset));
  });
  const suggestions = seededShuffle(SEARCH_SUGGESTION_SETS[language] || SEARCH_SUGGESTION_SETS.zh).slice(0, 8);
  requireEl("searchSuggestionChips").innerHTML = suggestions
    .map((text) => `<button class="suggestionChip" type="button" data-suggestion="${escapeHtml(text)}">${escapeHtml(text)}</button>`)
    .join("");
  document.querySelectorAll(".suggestionChip").forEach((button) => {
    button.addEventListener("click", () => addSuggestionToKeywords(button.dataset.suggestion));
  });
}

function generationFormSnapshot() {
  return {
    brief: requireEl("brief").value,
    productType: requireEl("productType").value,
    productName: requireEl("productName").value,
    targetAudience: requireEl("targetAudience").value,
    promotionGoal: requireEl("promotionGoal").value,
    market: requireEl("market").value,
    keywords: requireEl("keywords").value,
  };
}

function restoreGenerationSnapshot(snapshot) {
  if (!snapshot) return;
  Object.entries(snapshot).forEach(([id, value]) => {
    if ($(id)) requireEl(id).value = value || "";
  });
  clearGeneratedOutlineOnInputChange();
}

function applyProductSuggestion({ product = "", angle = "", audience = "", market = "", goal = "", note = "", keywords = "" }) {
  state.recommendationHistory.push(generationFormSnapshot());
  if (state.recommendationHistory.length > 20) state.recommendationHistory.shift();
  const isEnglish = requireEl("outputLanguage").value === "en";
  requireEl("productType").value = product;
  requireEl("productName").value = "";
  requireEl("targetAudience").value = audience;
  requireEl("promotionGoal").value = goal || angle;
  requireEl("market").value = market;
  requireEl("brief").value = isEnglish
    ? `Create a product-led ecommerce blog for ${product}.\nPositioning: ${angle}.\nTarget audience: ${audience}.\nMarket: ${market}.\nPromotion goal: ${goal || angle}.\nContent focus: ${note}.\nThis is a demo article for merchants who want to publish useful product content online and increase AI-search indexing.`
    : `围绕「${product}」生成一篇产品导向的电商 Blog。\n定位方向：${angle}。\n目标用户：${audience}。\n目标市场：${market}。\n推广目标：${goal || angle}。\n内容重点：${note}。\n这是一个给电商商家演示用的推广 Demo，用于发布到网上增加商品相关内容索引和 AI 检索曝光。`;
  requireEl("keywords").value = isEnglish
    ? `Product: ${product}\nAngle: ${angle}\nAudience: ${audience}\nMarket: ${market}\nContent points: ${note}\nSEO / AI-search notes: ${keywords}`
    : `产品：${product}\n方向：${angle}\n目标用户：${audience}\n目标市场：${market}\n内容重点：${note}\nSEO / AI 检索补充：${keywords}`;
  ["brief", "productType", "productName", "targetAudience", "promotionGoal", "market", "keywords"].forEach((id) => {
    requireEl(id).dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function undoRecommendationFill() {
  const snapshot = state.recommendationHistory.pop();
  if (!snapshot) return false;
  restoreGenerationSnapshot(snapshot);
  return true;
}

function handleRecommendationUndo(event) {
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "z" || event.shiftKey) return;
  const target = event.target;
  const formIds = new Set(["brief", "productType", "productName", "targetAudience", "promotionGoal", "market", "keywords"]);
  if (!target?.id || !formIds.has(target.id)) return;
  if (!state.recommendationHistory.length) return;
  event.preventDefault();
  undoRecommendationFill();
}

function addSuggestionToKeywords(text) {
  const keywords = requireEl("keywords");
  const current = keywords.value.trim();
  const line = `- ${text}`;
  if (current.includes(text)) return;
  keywords.value = current ? `${current}\n${line}` : line;
  keywords.dispatchEvent(new Event("input", { bubbles: true }));
  keywords.focus();
}

function selectedReferenceItems(type) {
  const selected = state.selectedCitationRefs;
  return state.searchResults.filter((item) => selected.has(item.id));
}

function buildManualReferenceQuery() {
  return $("referenceQuery")?.value?.trim() || "";
}

function normalizeReferenceItems(items = []) {
  return (Array.isArray(items) ? items : []).map((item, index) => ({
    ...item,
    id: item.id || item.url || `ref-${index + 1}`,
    rank: item.rank || index + 1,
    weightedRank: item.weightedRank || item.rank || index + 1,
  }));
}

function adoptReferenceResults(items, options = {}) {
  const normalized = normalizeReferenceItems(items);
  if (!normalized.length) return false;
  state.searchResults = normalized;
  state.analysisSearchResults = normalizeReferenceItems(options.analysisItems || normalized);
  if (options.selectTop !== false) {
    state.selectedCitationRefs = new Set(state.searchResults.slice(0, 3).map((item) => item.id));
  }
  renderReferenceCards();
  return true;
}

function renderReferenceCards() {
  const container = requireEl("referenceCards");
  if (!state.searchResults.length) {
    container.innerHTML = `<article class="emptyState"><h3>还没有参考结果</h3><p>点击“搜索参考”后，会展示可用于引用的 Top Blog 链接。</p></article>`;
    renderReferenceSummary();
    return;
  }
  container.innerHTML = state.searchResults.map((item) => {
    const citationChecked = state.selectedCitationRefs.has(item.id) ? "checked" : "";
    const image = item.thumbnail
      ? `<img src="${escapeHtml(item.thumbnail)}" alt="" loading="lazy" />`
      : `<div class="referenceThumbFallback" style="background:${escapeHtml(item.thumbnailFallback || "linear-gradient(135deg,#e9f2ff,#fff3d4)")};"></div>`;
    return `
      <article class="referenceCard" data-id="${escapeHtml(item.id)}">
        <div class="referenceThumb">${image}<span>#${escapeHtml(item.weightedRank || item.rank || "-")}</span></div>
        <div class="referenceBody">
          <div class="referenceMeta">
            <b>${escapeHtml(item.domain || "unknown")}</b>
            <em>匹配度 ${escapeHtml(item.displayScore ?? "-")}</em>
          </div>
          <h3>${escapeHtml(item.title || "Untitled")}</h3>
          <p>${escapeHtml(item.snippet || "没有摘要，仍可作为标题和链接参考。")}</p>
          ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.url)}</a>` : ""}
          ${item.reason ? `<small>${escapeHtml(item.reason)}</small>` : ""}
          <div class="referenceActions">
            <label><input type="checkbox" class="referenceCitation" data-id="${escapeHtml(item.id)}" ${citationChecked} /> 引用链接</label>
          </div>
        </div>
      </article>`;
  }).join("");
  container.querySelectorAll(".referenceCitation").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) state.selectedCitationRefs.add(input.dataset.id);
      else state.selectedCitationRefs.delete(input.dataset.id);
      renderReferenceSummary();
    });
  });
  renderReferenceSummary();
}

function renderReferenceSummary() {
  const citationCount = state.selectedCitationRefs.size;
  if ($("referenceStatus")) {
    requireEl("referenceStatus").textContent = state.searchResults.length
      ? `已获取 ${state.searchResults.length} 个参考：引用 ${citationCount} 个。`
      : "根据当前需求搜索 Top Blog 链接，选择后会在正文段落和文末参考来源中使用。";
  }
  if ($("generationReferenceSummary")) {
    requireEl("generationReferenceSummary").innerHTML = `
      <article><b>引用链接</b><span>${citationCount || "未选择"}</span></article>
      <article><b>搜索结果</b><span>${state.searchResults.length || "未搜索"}</span></article>`;
  }
  if (state.outline) renderOutline(state.outline, { preserveEditor: true, preserveReferenceCards: true });
}

function selectedIntentOption() {
  return state.intentOptions.find((item) => item.id === state.selectedIntentId) || null;
}

function referencesForIntent(intent) {
  const ids = new Set(intent?.referenceIds || []);
  return state.searchResults.filter((item) => ids.has(item.id));
}

function compactSearchResultsForPlanning(limit = 20) {
  return (state.analysisSearchResults?.length ? state.analysisSearchResults : state.searchResults || []).slice(0, limit).map((item, index) => ({
    id: item.id || `ref-${index + 1}`,
    rank: item.weightedRank || item.rank || index + 1,
    title: item.title || "",
    url: item.url || "",
    domain: item.domain || "",
  }));
}

function setOutlineFlowStep(step) {
  const normalized = step === "search" || step === "title" ? "research" : step;
  if (["research", "outline"].includes(normalized)) {
    setOutlineSubStep(normalized);
  }
  document.querySelectorAll("[data-flow-step]").forEach((item) => {
    const value = item.dataset.flowStep;
    item.classList.toggle("active", value === normalized);
    item.classList.toggle("done", step === "done" || (normalized === "outline" && value === "research"));
  });
}

function setOutlineSubStep(step) {
  const next = step === "search" || step === "title" ? "research" : ["research", "outline"].includes(step) ? step : "research";
  state.outlineSubStep = next;
  document.querySelectorAll(".outlineSubPage").forEach((page) => {
    page.classList.toggle("active", page.dataset.outlineSubpage === next);
  });
  document.querySelectorAll("[data-flow-step]").forEach((item) => {
    item.classList.toggle("active", item.dataset.flowStep === next);
  });
  const back = $("outlineSubBack");
  const nextButton = $("outlineSubNext");
  const headerBtn = $("prepareOutlineBtn");
  if (back) back.hidden = next === "research";
  // outlineSubNext 只在 outline 子步骤显示
  if (nextButton) {
    nextButton.hidden = next === "research";
    nextButton.textContent = "生成正文 →";
    nextButton.classList.toggle("outlineCtaActive", next === "outline");
  }
  // header 按钮：research 阶段负责搜索，outline 阶段变成生成正文 CTA
  if (headerBtn) {
    if (next === "outline") {
      headerBtn.textContent = "生成正文 →";
      headerBtn.classList.add("outlineCtaActive");
    } else {
      headerBtn.textContent = state.titleOptions.length || state.selectedTitleText
        ? "按标题生成大纲" : "搜索并生成标题";
      headerBtn.classList.remove("outlineCtaActive");
    }
  }
}

function applyIntentReferenceSelection(intent) {
  const refs = referencesForIntent(intent);
  if (!refs.length) return 0;
  refs.forEach((item) => state.selectedCitationRefs.add(item.id));
  renderReferenceCards();
  renderReferenceSummary();
  return refs.length;
}

function selectedTitleOption() {
  return state.titleOptions.find((item) => item.id === state.selectedTitleId) || null;
}

function setSelectedTitle(option) {
  if (!option) return;
  state.selectedTitleId = option.id || "";
  state.selectedTitleText = option.title || "";
  // Auto-detect SEO/GEO track from card ID (e.g. "zh-seo-1" / "zh-geo-2")
  const cardId = option.id || "";
  if (/-seo-\d+$/.test(cardId)) {
    state.selectedTitleTrack = "seo";
  } else if (/-geo-\d+$/.test(cardId)) {
    state.selectedTitleTrack = "geo";
  } else {
    state.selectedTitleTrack = "both";
  }
  if ($("selectedTitleInput")) requireEl("selectedTitleInput").value = state.selectedTitleText;
  clearGeneratedOutlineOnInputChange();
  renderTitleOptions();
}

function adoptDualAnchorTitles() {
  const primary = state.titleStrategy?.primary;
  const seoTitle = primary?.seo?.recommended?.title || "";
  const geoTitle = primary?.geo?.recommended?.title || "";
  if (!geoTitle && !seoTitle) return;
  const option = state.titleOptions.find((item) => item.title === geoTitle) || state.titleOptions.find((item) => item.title === seoTitle);
  state.selectedTitleId = option?.id || "dual-anchor";
  state.selectedTitleText = geoTitle || seoTitle;
  state.selectedTitleTrack = "both";
  state.dualAnchorSelection = {
    seoTitle,
    geoTitle,
    mode: "dual",
  };
  if ($("selectedTitleInput")) requireEl("selectedTitleInput").value = state.selectedTitleText;
  clearGeneratedOutlineOnInputChange();
  renderTitleOptions();
}

function trackLabel(track) {
  return track === "seo" ? "SEO 标题" : track === "geo" ? "GEO 标题" : "标题";
}

function renderTitleOptions() {
  const container = $("titleCards");
  if (!container) return;
  const options = state.titleOptions || [];
  const strategy = state.titleStrategy || null;
  if ($("titleStatus")) {
    const trackHint = state.selectedTitleTrack === "seo"
      ? " · 已选择 SEO 标题 → 将仅生成 SEO 版文章"
      : state.selectedTitleTrack === "geo"
        ? " · 已选择 GEO 标题 → 将仅生成 GEO 版文章"
        : "";
    requireEl("titleStatus").textContent = options.length
      ? `已生成 SEO/GEO 双轨标题候选。当前标题可手动修改。${trackHint}`
      : "搜索和内部意图识别完成后，会生成可选择和可手动修改的标题。";
  }
  if ($("selectedTitleInput")) requireEl("selectedTitleInput").value = state.selectedTitleText || "";
  if (!options.length) {
    container.innerHTML = `<article class="emptyState"><h3>等待标题生成</h3><p>先点击“搜索并生成标题”，这里会出现标题候选。</p></article>`;
    return;
  }
  if (strategy?.primary) {
    const blocks = [strategy.primary].filter(Boolean);
    container.innerHTML = `
      <div class="dualAnchorBar">
        <div>
          <strong>双锚点策略</strong>
          <span>SEO 推荐用于网页 title，GEO 推荐用于 H1 和 Schema headline。</span>
        </div>
        <button class="secondaryButton" id="adoptDualAnchorTitles" type="button">同时采用两个版本</button>
      </div>
      ${blocks.map((block) => `
      <section class="titleTrackGroup">
        <div class="titleTrackHeader">
          <strong>${escapeHtml((block.language || "").toUpperCase())} 双轨标题</strong>
          <small>${escapeHtml(block.strategyNote || "SEO 用于网页标题，GEO 用于 H1 和 AI 引用锚点。")}</small>
        </div>
        <div class="titleTrackGrid">
          ${["seo", "geo"].map((track) => {
            const candidates = block[track]?.candidates || [];
            return `
              <div class="titleTrackPanel">
                <div class="titleTrackName">${trackLabel(track)}</div>
                ${candidates.map((option, index) => {
                  const id = `${block.language}-${track}-${index + 1}`;
                  const active = id === state.selectedTitleId || option.title === state.selectedTitleText;
                  return `
                    <button class="titleOptionCard ${active ? "active" : ""}" type="button" data-id="${escapeHtml(id)}">
                      <span>${escapeHtml(option.score || "-")}</span>
                      <strong>${escapeHtml(option.title || "未命名标题")}</strong>
                      ${option.reason ? `<p>${escapeHtml(option.reason)}</p>` : ""}
                      <small>${escapeHtml(trackLabel(track))}</small>
                    </button>`;
                }).join("")}
              </div>`;
          }).join("")}
        </div>
      </section>`).join("")}`;
  } else {
    container.innerHTML = options.map((option) => `
      <button class="titleOptionCard ${option.id === state.selectedTitleId ? "active" : ""}" type="button" data-id="${escapeHtml(option.id)}">
        <span>${escapeHtml(option.score || "-")}</span>
        <strong>${escapeHtml(option.title || "未命名标题")}</strong>
        ${option.reason ? `<p>${escapeHtml(option.reason)}</p>` : ""}
        ${option.angle ? `<small>${escapeHtml(option.angle)}</small>` : ""}
      </button>`).join("");
  }
  container.querySelectorAll(".titleOptionCard").forEach((card) => {
    card.addEventListener("click", () => setSelectedTitle(state.titleOptions.find((item) => item.id === card.dataset.id)));
  });
  container.querySelector("#adoptDualAnchorTitles")?.addEventListener("click", adoptDualAnchorTitles);
  setOutlineSubStep(state.outlineSubStep);
}

async function generateTitleOptions() {
  const input = collectInput();
  const result = await api("/api/title-options", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      selectedIntent: selectedIntentOption(),
      searchResults: compactSearchResultsForPlanning(20),
    }),
    signal: taskSignal("outlineResearch"),
  });
  state.titleOptions = result.titles || [];
  state.titleStrategy = result.titleStrategy || null;
  const refs = result.searchResults || result.serpIntelligence?.referencePages || result.titleStrategy?.serpIntelligence?.referencePages || [];
  if (refs.length) adoptReferenceResults(refs, { analysisItems: result.analysisSearchResults || result.serpIntelligence?.analysisItems || refs });
  const recommended = state.titleOptions[0];
  if (recommended) {
    state.selectedTitleId = recommended.id;
    state.selectedTitleText = recommended.title;
  }
  renderTitleOptions();
}

function renderIntentOptions() {
  const container = requireEl("intentCards");
  const options = state.intentOptions || [];
  if ($("intentStatus")) {
    requireEl("intentStatus").textContent = options.length
      ? `已分析 ${options.length} 个可能意图。当前选择：${selectedIntentOption()?.title || "未选择"}。`
      : "搜索完成后，让 AI 结合需求和参考结果列出几种可能的写作方向。";
  }
  if (!options.length) {
    container.innerHTML = `<article class="emptyState"><h3>等待意图分析</h3><p>搜索参考后点击“分析意图”，这里会出现可选择的写作方向。</p></article>`;
    return;
  }
  container.innerHTML = options.map((intent, index) => {
    const active = intent.id === state.selectedIntentId ? "active" : "";
    const refs = referencesForIntent(intent);
    const probability = Math.max(1, Math.min(99, Number(intent.probability || intent.score || 0) || (index === 0 ? 58 : 24)));
    return `
      <button class="intentCard ${active}" type="button" data-id="${escapeHtml(intent.id)}">
        <span class="intentScore">${probability}%</span>
        ${intent.recommended ? `<em class="recommendedBadge">Recommended</em>` : ""}
        <strong>${escapeHtml(intent.title || `意图 ${index + 1}`)}</strong>
        <p>${escapeHtml(intent.summary || intent.outlineFocus || "AI 将按这个方向生成更聚焦的大纲。")}</p>
        ${intent.outlineFocus ? `<small>${escapeHtml(intent.outlineFocus)}</small>` : ""}
        ${refs.length ? `
          <div class="intentReferences">
            ${refs.slice(0, 4).map((ref) => `<span title="点击意图卡片会自动勾选该引用">#${escapeHtml(ref.weightedRank || ref.rank || "-")} ${escapeHtml(ref.title || ref.domain || "Reference")}</span>`).join("")}
          </div>` : ""}
      </button>`;
  }).join("");
  container.querySelectorAll(".intentCard").forEach((card) => {
    card.addEventListener("click", () => {
      const intent = state.intentOptions.find((item) => item.id === card.dataset.id);
      if (state.selectedIntentId === card.dataset.id) {
        applyIntentReferenceSelection(intent);
        return;
      }
      state.selectedIntentId = card.dataset.id || "";
      applyIntentReferenceSelection(intent);
      clearGeneratedOutlineOnInputChange();
      renderIntentOptions();
    });
  });
}

function renderInternalIntentStatus() {
  if ($("internalIntentStatus")) {
    requireEl("internalIntentStatus").textContent = state.intentOptions.length
      ? `内部意图已识别：${selectedIntentOption()?.title || "已选择推荐方向"}。`
      : "内部意图识别将在搜索后自动完成，不展示给客户。";
  }
}

async function analyzeIntents() {
  const button = requireEl("analyzeIntentBtn");
  const progress = requireEl("intentProgress");
  if (!startBusy("intent", button, progress, "正在分析可能的写作意图...")) return;
  try {
    const input = collectInput();
    validateBrief(input);
    const result = await api("/api/intent-analysis", {
      method: "POST",
      body: JSON.stringify({
        ...input,
        searchResults: compactSearchResultsForPlanning(20),
      }),
      signal: taskSignal("intent"),
    });
    state.intentOptions = result.intents || [];
    const recommended = state.intentOptions.find((item) => item.recommended) || state.intentOptions[0];
    state.selectedIntentId = recommended?.id || "";
    renderInternalIntentStatus();
    clearGeneratedOutlineOnInputChange();
    finishBusy("intent", button, progress, "意图分析完成");
  } catch (error) {
    failBusy("intent", button, progress, isAbortError(error) ? "已停止意图分析" : "意图分析失败");
    if (isAbortError(error)) return;
    throw error;
  }
}

async function searchReferences({ skipAutoIntent = false } = {}) {
  const button = requireEl("searchReferencesBtn");
  const progress = requireEl("referenceProgress");
  if (!startBusy("references", button, progress, "正在联网搜索参考...")) return;
  let shouldAnalyze = false;
  try {
    const input = collectInput();
    validateBrief(input);
    const manualQuery = buildManualReferenceQuery();
    const result = await api("/api/search-references", {
      method: "POST",
      body: JSON.stringify({
        ...input,
        ...(manualQuery ? { manualQuery } : {}),
        maxResults: Number($("searchMaxResults")?.value || 15),
      }),
      signal: taskSignal("references"),
    });
    adoptReferenceResults(result.items || [], { analysisItems: result.analysisItems || result.items || [] });
    if (!(result.items || []).length) {
      const rawCount = (result.analysisItems || []).length;
      const errPart = result.errors?.length ? `（错误：${result.errors.join('；')}）` : '';
      const hint = rawCount > 0
        ? `共抓取 ${rawCount} 条候选，过滤后无符合相关性要求的结果。可尝试：换一个关键词、或检查 SearXNG 是否能正常访问目标站点。${errPart}`
        : `未抓取到任何原始结果，请检查 SearXNG 连通性或关键词是否过于冷门。${errPart}`;
      await showMessage(hint, { title: '搜索结果为空' });
    }
    state.intentOptions = [];
    state.selectedIntentId = "";
    state.titleOptions = [];
    state.titleStrategy = null;
    state.selectedTitleId = "";
    state.selectedTitleText = "";
    renderReferenceCards();
    renderTitleOptions();
    clearGeneratedOutlineOnInputChange();
    finishBusy("references", button, progress, "参考搜索完成");
    if (result.errors?.length) {
      await showMessage(`搜索完成，但部分来源不可用：${result.errors.join("；")}`, { title: "搜索提示" });
    }
    shouldAnalyze = !skipAutoIntent && state.searchResults.length > 0;
  } catch (error) {
    failBusy("references", button, progress, isAbortError(error) ? "已停止搜索" : "参考搜索失败");
    if (isAbortError(error)) return;
    throw error;
  }
  if (shouldAnalyze) {
    await analyzeIntents();
  }
}

async function prepareOutlineResearch() {
  const button = requireEl("prepareOutlineBtn");
  const progress = requireEl("outlineProgress");
  if (!startBusy("outlineResearch", button, progress, "正在搜索并分析意图...")) return;
  try {
    const input = collectInput();
    validateBrief(input);
    setOutlineFlowStep("search");
    setProgress(progress, 12, "1/2 正在搜索参考链接...");
    await searchReferences({ skipAutoIntent: true });

    setOutlineFlowStep("research");
    setProgress(progress, 45, "2/3 正在内部识别用户意图...");
    await analyzeIntents();
    applyIntentReferenceSelection(selectedIntentOption());

    setOutlineFlowStep("research");
    setProgress(progress, 78, "3/3 正在生成标题候选...");
    await generateTitleOptions();
    setOutlineSubStep("research");
    setProgress(progress, 100, "搜索完成，标题已生成；确认标题后点击“按标题生成大纲”");
    finishBusy("outlineResearch", button, progress, "搜索和标题生成完成");
  } catch (error) {
    failBusy("outlineResearch", button, progress, isAbortError(error) ? "已停止搜索分析" : "搜索分析失败");
    if (isAbortError(error)) return;
    throw error;
  }
}

function clearReferenceSelection() {
  state.selectedCitationRefs.clear();
  renderReferenceCards();
}

async function generateImagePlaceholder() {
  const result = await api("/api/generate-image", {
    method: "POST",
    body: JSON.stringify({ mode: state.imageMode, prompt: $("imagePrompt")?.value || "", article: $("markdownOutput")?.value || "", brief: $("brief")?.value || "" }),
  });
  requireEl("imagePlanStatus").textContent = `${result.message} Prompt：${result.prompt || "-"}`;
}

function collectInput() {
  let outline = state.outline;
  if ($("outlineEditor") && outline) {
    outline = collectOutlineEditor({ silent: true }) || outline;
  }
  const rawOutline = $("outlineJson").value.trim();
  if (!outline && rawOutline) {
    try {
      outline = JSON.parse(rawOutline);
    } catch {
      throw new Error("大纲 JSON 格式无效，请先修正。");
    }
  }
  return {
    language: $("outputLanguage").value,
    brief: $("brief").value.trim(),
    market: $("market").value.trim(),
    productType: $("productType").value.trim(),
    productName: $("productName").value.trim(),
    targetAudience: $("targetAudience").value.trim(),
    promotionGoal: $("promotionGoal").value.trim(),
    keywords: $("keywords").value.trim(),
    productFileText: state.productFileText,
    images: state.images,
    imagePlan: {
      mode: state.imageMode,
      prompt: $("imagePrompt")?.value?.trim() || "",
    },
    searchResults: state.searchResults,
    analysisSearchResults: state.analysisSearchResults,
    intentOptions: state.intentOptions,
    selectedIntent: selectedIntentOption(),
    titleOptions: state.titleOptions,
    titleStrategy: state.titleStrategy,
    dualAnchorSelection: state.dualAnchorSelection || null,
    selectedTitle: ($("selectedTitleInput")?.value?.trim() || state.selectedTitleText || selectedTitleOption()?.title || "").trim(),
    seoGeoPreference: state.selectedTitleTrack && state.selectedTitleTrack !== "both" ? state.selectedTitleTrack : ($("seoGeoPreference")?.value || "both"),
    selectedCitationReferences: selectedReferenceItems("citation"),
    seoNotes: defaultSeoNotes,
    humanFeedback: "",
    scenarioName: $("scenarioName")?.value?.trim() || "",
    outline,
    promptOverrides: {
      [ $("language").value ]: {
        ...collectPromptSystem($("language").value)
      }
    }
  };
}

function validateBrief(input) {
  if (!input.brief && !input.productType && !input.productName) {
    throw new Error("请至少填写用户需求、商品类型或商品名称。");
  }
}

function asList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    return value.split(/\r?\n|；|;/).map((item) => item.trim()).filter(Boolean);
  }
  if (typeof value === "object") {
    return Object.entries(value).map(([key, item]) => `${key}: ${typeof item === "string" ? item : JSON.stringify(item)}`);
  }
  return [String(value)];
}

function asText(value) {
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map(asText).filter(Boolean).join("；");
  if (typeof value === "object") {
    return value.heading || value.title || value.h1 || value.h2 || value.h3 || value.name || value.question || value.summary || value.description || value.content || "";
  }
  return String(value).trim();
}

function subsectionTexts(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(asText).filter(Boolean);
  if (typeof value === "string") return asList(value);
  if (typeof value === "object") return Object.values(value).map(asText).filter(Boolean);
  return [];
}

function normalizeOutlineNode(value, level = 2, fallback = "") {
  if (typeof value === "string") {
    return { h2: level <= 2 ? value.trim() : fallback, summary: "", h3: level <= 2 ? [] : [value.trim()] };
  }
  if (!value || typeof value !== "object") {
    return { h2: fallback, summary: "", h3: [] };
  }
  const h2 = asText(value.h2 || value.heading || value.title || value.name || value.section || value.question || fallback);
  const summary = asText(value.summary || value.description || value.content || value.detail || value.type || "");
  const h3Source = value.h3 || value.subsections || value.children || value.points || value.items || value.questions || value.subheadings;
  const h3 = subsectionTexts(h3Source);
  return { h2, summary, h3 };
}

function outlineStructureItems(outline) {
  const normalized = normalizeOutlineForDisplay(outline);
  return normalized.sections;
}

function normalizeOutlineForDisplay(outline) {
  if (!outline) return { title: "", sections: [], raw: null };
  const rawOutline = outline.outline || outline.structure || outline.sections || {};
  const title = asText(
    rawOutline?.title
    || rawOutline?.h1
    || rawOutline?.heading
    || rawOutline?.H1
    || outline.title
    || outline.selectedTopic
    || ""
  );
  let raw = rawOutline;
  if (raw && typeof raw === "object") {
    raw = raw.sections || raw.structure || raw.outline || raw.items || raw.children || raw.H2 || raw.h2 || raw;
  }
  let sections = [];
  if (Array.isArray(raw)) {
    sections = raw.map((item, index) => normalizeOutlineNode(item, 2, `Section ${index + 1}`));
  } else if (raw && typeof raw === "object") {
    sections = Object.entries(raw)
      .filter(([key]) => !["title", "h1", "H1", "metaDescription", "meta_description", "keywords", "slug", "language"].includes(key))
      .map(([key, value]) => {
        if (value && typeof value === "object" && !Array.isArray(value)) {
          return normalizeOutlineNode({ heading: key, ...value }, 2, key);
        }
        return { h2: key, summary: typeof value === "string" ? value : "", h3: typeof value === "string" ? [] : subsectionTexts(value) };
      });
  } else {
    sections = asList(raw).map((item, index) => ({ h2: item, summary: "", h3: [] }));
  }
  if (!sections.length && (outline.heading || outline.H2 || outline.content)) {
    sections.push(normalizeOutlineNode(outline, 2, title || "Section 1"));
  }
  return {
    title: title || sections[0]?.h2 || "",
    sections: sections.filter((item) => item.h2 || item.summary || item.h3.length),
    raw: outline,
  };
}

function outlineText(value) {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return String(value || "");
  return value.h2 || value.heading || value.title || value.name || value.question || value.description || JSON.stringify(value);
}

function applyOutlineJson() {
  const rawOutline = requireEl("outlineJson").value.trim();
  if (!rawOutline) {
    renderOutline(null);
    return;
  }
  try {
    renderOutline(JSON.parse(rawOutline), { preserveEditor: true, source: "manual" });
  } catch {
    throw new Error("大纲 JSON 格式无效，请先修正。");
  }
}

function outlineFromEditor(baseOutline = state.outline) {
  const title = requireEl("outlineTitleInput").value.trim();
  const sections = Array.from(document.querySelectorAll(".outlineSectionEditor")).map((section) => {
    const h2 = section.querySelector(".outlineH2Input").value.trim();
    const summary = section.querySelector(".outlineSummaryInput").value.trim();
    const h3 = Array.from(section.querySelectorAll(".outlineH3Input")).map((input) => input.value.trim()).filter(Boolean);
    return { h2, summary, h3 };
  }).filter((item) => item.h2 || item.summary || item.h3.length);
  return {
    ...(baseOutline || {}),
    selectedTopic: title || baseOutline?.selectedTopic || "",
    outline: {
      ...(baseOutline?.outline && typeof baseOutline.outline === "object" && !Array.isArray(baseOutline.outline) ? baseOutline.outline : {}),
      title,
      sections,
    },
  };
}

function collectOutlineEditor({ silent = false } = {}) {
  if (!state.outline || !$("outlineTitleInput")) return state.outline;
  const outline = outlineFromEditor(state.outline);
  state.outline = outline;
  requireEl("outlineJson").value = JSON.stringify(outline, null, 2);
  if (!silent) renderOutline(outline, { preserveEditor: false, source: "manual" });
  return outline;
}

function renderOutlineEditor(outline) {
  const container = requireEl("outlineEditor");
  if (!outline) {
    container.innerHTML = `<article class="emptyState"><h3>等待大纲</h3><p>生成大纲后，这里会出现可编辑的 H1、H2、H3 标题。</p></article>`;
    return;
  }
  const normalized = normalizeOutlineForDisplay(outline);
  const sections = normalized.sections.length ? normalized.sections : [{ h2: "", summary: "", h3: [] }];
  container.innerHTML = `
    <label class="outlineTitleEdit">H1 大标题
      <input id="outlineTitleInput" value="${escapeHtml(normalized.title)}" placeholder="文章主标题" />
    </label>
    <div class="outlineSectionEditors">
      ${sections.map((section, index) => `
        <article class="outlineSectionEditor" data-index="${index}">
          <div class="outlineEditorRow">
            <label>H2 一级章节
              <input class="outlineH2Input" value="${escapeHtml(section.h2)}" placeholder="章节标题" />
            </label>
            <button class="textButton removeOutlineSection" type="button">删除</button>
          </div>
          <label>写作提示
            <textarea class="outlineSummaryInput" rows="2" placeholder="这一节要写什么">${escapeHtml(section.summary)}</textarea>
          </label>
          <div class="outlineH3List">
            ${(section.h3.length ? section.h3 : [""]).map((item) => `
              <label>H3 小标题
                <input class="outlineH3Input" value="${escapeHtml(item)}" placeholder="小标题，可留空" />
              </label>`).join("")}
          </div>
          <button class="secondaryButton addOutlineH3" type="button">添加 H3</button>
        </article>`).join("")}
    </div>
    <button class="secondaryButton" id="addOutlineSection" type="button">添加 H2 章节</button>`;
  container.querySelector("#addOutlineSection")?.addEventListener("click", () => {
    collectOutlineEditor({ silent: true });
    const next = outlineFromEditor(state.outline);
    next.outline.sections.push({ h2: "", summary: "", h3: [] });
    renderOutline(next, { preserveEditor: false, source: "manual" });
  });
  container.querySelectorAll(".addOutlineH3").forEach((button) => {
    button.addEventListener("click", () => {
      const section = button.closest(".outlineSectionEditor");
      const list = section.querySelector(".outlineH3List");
      list.insertAdjacentHTML("beforeend", `<label>H3 小标题<input class="outlineH3Input" placeholder="小标题，可留空" /></label>`);
    });
  });
  container.querySelectorAll(".removeOutlineSection").forEach((button) => {
    button.addEventListener("click", () => {
      button.closest(".outlineSectionEditor").remove();
      collectOutlineEditor();
    });
  });
}

function outlineReferenceHtml() {
  const selected = selectedReferenceItems("citation");
  if (!selected.length) return "";
  return `
    <article class="miniCard outlineReferenceCard">
      <h4>已选引用来源</h4>
      <div class="outlineReferenceList">
        ${selected.slice(0, 8).map((item, index) => `
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">
            <span>#${index + 1}</span>
            <b>${escapeHtml(item.title || item.domain || "Reference")}</b>
            <small>${escapeHtml(item.domain || "")}</small>
          </a>`).join("")}
      </div>
    </article>`;
}

function outlineIntentHtml() {
  const intent = selectedIntentOption();
  if (!intent) return "";
  return `
    <article class="miniCard outlineIntentCard">
      <h4>已选意图</h4>
      <p><b>${escapeHtml(intent.title || "未命名意图")}</b></p>
      ${intent.summary ? `<p>${escapeHtml(intent.summary)}</p>` : ""}
      ${intent.outlineFocus ? `<small>${escapeHtml(intent.outlineFocus)}</small>` : ""}
    </article>`;
}

function renderOutline(outline, options = {}) {
  state.outline = outline;
  if (!options.preserveEditor) {
    requireEl("outlineJson").value = outline ? JSON.stringify(outline, null, 2) : "";
  }
  if (!options.preserveEditor) renderOutlineEditor(outline);
  const normalizedOutline = normalizeOutlineForDisplay(outline);
  const topics = asList(outline?.topics);
  const outlineItems = normalizedOutline.sections;
  const exposureNotes = asList(outline?.aiExposureNotes);
  const selectedTopic = normalizedOutline.title || outline?.selectedTopic || "";
  const searchIntent = outline?.searchIntent || "";
  const audience = outline?.audience || "";
  requireEl("outlineStatus").textContent = outline
    ? `${options.source === "manual" ? "已应用手动编辑的大纲" : "已生成新大纲"}：${selectedTopic || "未命名主题"}`
    : "当前还没有新大纲。先生成结构，确认或编辑后再进入正文。";
  const cards = [];
  if (selectedTopic || searchIntent || audience) {
    cards.push(`
      <article class="outlinePrimaryCard">
        <span>推荐主题</span>
        <h3>${escapeHtml(selectedTopic || "未命名主题")}</h3>
        ${searchIntent ? `<p><b>搜索意图</b>${escapeHtml(searchIntent)}</p>` : ""}
        ${audience ? `<p><b>目标读者</b>${escapeHtml(audience)}</p>` : ""}
      </article>`);
  }
  if (topics.length) {
    cards.push(`<article class="miniCard outlineTopicCard"><h4>候选主题</h4>${topics.slice(0, 6).map((topic) => {
      const title = typeof topic === "string" ? topic : topic.title || topic.name || JSON.stringify(topic);
      const reason = typeof topic === "string" ? "" : topic.reason || topic.description || "";
      return `<p><b>${escapeHtml(title)}</b>${reason ? `<span>${escapeHtml(reason)}</span>` : ""}</p>`;
    }).join("")}</article>`);
  }
  if (outlineItems.length) {
    cards.push(`<article class="miniCard outlineStructureCard"><h4>标题结构</h4>${outlineItems.map((item, index) => `
      <section class="outlineHeadingBlock">
        <span>H2 · ${index + 1}</span>
        <h5>${escapeHtml(item.h2 || `Section ${index + 1}`)}</h5>
        ${item.summary ? `<p>${escapeHtml(item.summary)}</p>` : ""}
        ${item.h3?.length ? `<ul>${item.h3.map((h3) => `<li><b>H3</b>${escapeHtml(h3)}</li>`).join("")}</ul>` : ""}
      </section>`).join("")}</article>`);
  }
  if (exposureNotes.length) {
    cards.push(`<article class="miniCard outlineExposureCard"><h4>AI 曝光要点</h4><ul>${exposureNotes.slice(0, 8).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article>`);
  }
  cards.push(outlineIntentHtml());
  cards.push(outlineReferenceHtml());
  requireEl("outlineCards").innerHTML = cards.filter(Boolean).join("") || `<article class="emptyState"><h3>等待生成大纲</h3><p>填写需求后点击“生成大纲”，这里会显示推荐主题、标题结构和引用来源。</p></article>`;
  bindTitleTooltips();
}

function showBlog(blog) {
  state.currentBlog = blog;
  state.articleViewMode = state.articleViewMode || "markdown";
  openLibraryGroups.add(blog.groupId || blog.id);
  requireEl("markdownOutput").value = blog.article || "";
  renderArticleView(state.articleViewMode);
  requireEl("blogDialogTitle").textContent = blog.groupName || blog.title || "Untitled";
  requireEl("blogDialogMeta").textContent = `${blog.versionLabel || `v${blog.versionIndex || 1}`} · 创建 ${formatDateTime(blog.createdAt)} · 修改 ${formatDateTime(blog.updatedAt || blog.createdAt)}`;
  requireEl("resultMeta").textContent = `正在查看：${blog.groupName || blog.title || "Untitled"} · ${blog.versionLabel || `v${blog.versionIndex || 1}`}`;
  if (!requireEl("blogArticleDialog").open) requireEl("blogArticleDialog").showModal();
  updateLibrarySelection();
}

function collapseBlogPreview() {
  state.currentBlog = null;
  if (requireEl("blogArticleDialog").open) requireEl("blogArticleDialog").close();
  requireEl("markdownOutput").value = "";
  requireEl("markdownPreview").innerHTML = "";
  requireEl("resultMeta").textContent = "选择一篇本地文章后查看 Markdown。";
  requireEl("blogDialogMeta").textContent = "选择一篇本地文章后查看 Markdown。";
  updateLibrarySelection();
}

function updateLibrarySelection() {
  document.querySelectorAll(".libraryItem").forEach((item) => {
    item.classList.toggle("active", state.currentBlog?.id === item.dataset.id);
  });
}

function ensureTitleTooltip() {
  if (titleTooltipEl) return titleTooltipEl;
  titleTooltipEl = document.createElement("div");
  titleTooltipEl.className = "floatingTitleTooltip";
  document.body.appendChild(titleTooltipEl);
  return titleTooltipEl;
}

function showTitleTooltip(target) {
  const text = target?.dataset?.fullTitle || "";
  if (!text) return;
  const tip = ensureTitleTooltip();
  tip.textContent = text;
  tip.classList.add("show");
  const rect = target.getBoundingClientRect();
  const maxLeft = window.innerWidth - Math.min(560, window.innerWidth - 28) - 14;
  const left = Math.max(14, Math.min(rect.left, maxLeft));
  const top = Math.min(window.innerHeight - 80, rect.bottom + 10);
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
}

function hideTitleTooltip() {
  if (titleTooltipEl) titleTooltipEl.classList.remove("show");
}

function bindTitleTooltips(root = document) {
  root.querySelectorAll(".fullTitleTip").forEach((item) => {
    if (item.dataset.tooltipBound) return;
    item.dataset.tooltipBound = "1";
    item.addEventListener("mouseenter", () => showTitleTooltip(item));
    item.addEventListener("focus", () => showTitleTooltip(item));
    item.addEventListener("mouseleave", hideTitleTooltip);
    item.addEventListener("blur", hideTitleTooltip);
  });
}

function openRenameDialog({ title, label, value, eyebrow = "Rename", onConfirm }) {
  renameDialogState = { onConfirm };
  requireEl("renameDialogEyebrow").textContent = eyebrow;
  requireEl("renameDialogTitle").textContent = title;
  requireEl("renameDialogLabel").textContent = label;
  requireEl("renameDialogInput").value = value || "";
  requireEl("renameDialog").showModal();
  requireEl("renameDialogInput").focus();
}

function closeRenameDialog() {
  requireEl("renameDialog").close();
  renameDialogState = null;
}

async function confirmRenameDialog() {
  const value = requireEl("renameDialogInput").value.trim();
  if (!value) {
    await showMessage("名称不能为空。", { title: "需要填写名称" });
    return;
  }
  const handler = renameDialogState?.onConfirm;
  closeRenameDialog();
  if (handler) await handler(value);
}

function openMessageDialog({ title = "提示", message = "", eyebrow = "Notice", variant = "info", confirmText = "确定", cancelText = "取消", showCancel = false } = {}) {
  const dialog = requireEl("messageDialog");
  dialog.classList.toggle("isDanger", variant === "danger");
  dialog.classList.toggle("isSuccess", variant === "success");
  dialog.classList.toggle("isError", variant === "error");
  requireEl("messageDialogEyebrow").textContent = eyebrow;
  requireEl("messageDialogTitle").textContent = title;
  requireEl("messageDialogBody").textContent = message;
  requireEl("messageDialogConfirm").textContent = confirmText;
  requireEl("messageDialogCancel").textContent = cancelText;
  requireEl("messageDialogCancel").hidden = !showCancel;
  dialog.showModal();
  requireEl("messageDialogConfirm").focus();
  return new Promise((resolve) => {
    messageDialogState = { resolve };
  });
}

function closeMessageDialog(result = false) {
  const dialog = requireEl("messageDialog");
  if (dialog.open) dialog.close();
  const resolver = messageDialogState?.resolve;
  messageDialogState = null;
  if (resolver) resolver(result);
}

function showMessage(message, options = {}) {
  return openMessageDialog({
    title: options.title || "提示",
    message,
    eyebrow: options.eyebrow || "Notice",
    variant: options.variant || "info",
    confirmText: options.confirmText || "知道了",
    showCancel: false,
  });
}

function showError(error) {
  const message = error?.message || String(error || "操作失败");
  return showMessage(message, { title: "操作失败", eyebrow: "Error", variant: "error" });
}

function confirmMessage(message, options = {}) {
  return openMessageDialog({
    title: options.title || "确认操作",
    message,
    eyebrow: options.eyebrow || "Confirm",
    variant: options.variant || "danger",
    confirmText: options.confirmText || "确认",
    cancelText: options.cancelText || "取消",
    showCancel: true,
  });
}

function renderProfileOptions() {
  const options = buildModelOptions();
  ["outlineProfile", "articleProfile", "evaluatorProfile", "revisionProfile", "entityExtractorProfile", "searchPlannerProfile", "imageProfile"].forEach((id) => {
    requireEl(id).innerHTML = `<option value="">未分配</option>${options}`;
  });
  const assignments = state.config?.taskAssignments || {};
  $("outlineProfile").value = assignmentValue(assignments.outline);
  $("articleProfile").value = assignmentValue(assignments.article);
  $("evaluatorProfile").value = assignmentValue(assignments.evaluator || assignments.optimizer);
  $("revisionProfile").value = assignmentValue(assignments.revision || assignments.optimizer);
  $("entityExtractorProfile").value = assignmentValue(assignments.entity_extractor || assignments.outline);
  $("imageProfile").value = assignmentValue(assignments.image || assignments.article);
  $("searchPlannerProfile").value = assignmentValue(assignments.search_planner || assignments.outline);
}

function profileModels(profile) {
  const list = Array.isArray(profile.availableModels) ? profile.availableModels : [];
  const legacy = Object.values(profile.models || {}).filter(Boolean);
  return Array.from(new Set([...list, ...legacy].map((item) => String(item).trim()).filter(Boolean)));
}

function buildModelOptions() {
  return state.apiProfiles
    .flatMap((profile) => profileModels(profile).map((model) => ({
      value: `${profile.id}::${model}`,
      label: `${profile.name || profile.id} / ${model}`
    })))
    .map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
}

function assignmentValue(assignment) {
  if (!assignment) return "";
  if (typeof assignment === "string") return assignment;
  return assignment.profileId && assignment.model ? `${assignment.profileId}::${assignment.model}` : "";
}

function parseAssignment(value) {
  if (!value) return { profileId: "", model: "" };
  const [profileId, ...modelParts] = value.split("::");
  return { profileId, model: modelParts.join("::") };
}

function modeLabel(mode) {
  return {
    openai_chat: "OpenAI Chat",
    openai_responses: "OpenAI Responses",
    anthropic_messages: "Claude Messages",
    gemini_generate_content: "Gemini",
    custom_json: "通用 JSON"
  }[mode || "openai_chat"] || "OpenAI Chat";
}

function modeOptions(selected = "openai_chat") {
  return `
    <option value="openai_chat" ${selected === "openai_chat" || !selected ? "selected" : ""}>OpenAI Chat Completions</option>
    <option value="openai_responses" ${selected === "openai_responses" ? "selected" : ""}>OpenAI Responses</option>
    <option value="anthropic_messages" ${selected === "anthropic_messages" ? "selected" : ""}>Anthropic Messages / Claude</option>
    <option value="gemini_generate_content" ${selected === "gemini_generate_content" ? "selected" : ""}>Google Gemini GenerateContent</option>
    <option value="custom_json" ${selected === "custom_json" ? "selected" : ""}>通用 JSON</option>
  `;
}

function endpointLabel(endpoint) {
  try {
    const url = new URL(endpoint);
    return url.host;
  } catch {
    return endpoint || "未配置 endpoint";
  }
}

function renderApiProfiles() {
  requireEl("apiProfiles").innerHTML = state.apiProfiles
    .map((profile) => `
      <article class="apiSummaryCard" data-id="${profile.id}">
        <div class="apiSummaryTop">
          <span class="apiDot"></span>
          <div>
            <h4>${escapeHtml(profile.name || "未命名 API")}</h4>
            <p>${escapeHtml(modeLabel(profile.mode))} · ${escapeHtml(endpointLabel(profile.endpoint))}</p>
          </div>
        </div>
        <div class="apiModelPills">
          ${profileModels(profile).slice(0, 3).map((model) => `<span>${escapeHtml(model)}</span>`).join("") || "<span>未配置模型</span>"}
          ${profileModels(profile).length > 3 ? `<span>+${profileModels(profile).length - 3}</span>` : ""}
        </div>
        <p class="apiKeyState">${profile.apiKey ? "Key 已保存到本地配置" : "未保存 Key"}</p>
        <p class="profileTestResult muted"></p>
        <div class="apiSummaryActions">
          <button class="secondaryButton editProfile" type="button">编辑</button>
          <button class="secondaryButton testProfileCall" type="button">检测</button>
          <button class="removeProfile" type="button">删除</button>
        </div>
      </article>`)
    .join("") || `<p class="muted">还没有 API 卡片，点击“新增 API 卡片”。</p>`;

  document.querySelectorAll(".editProfile").forEach((button) => {
    button.addEventListener("click", () => openApiProfileDialog(button.closest(".apiSummaryCard").dataset.id));
  });
  document.querySelectorAll(".removeProfile").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.closest(".apiSummaryCard").dataset.id;
      if (!await confirmMessage("确认删除这个 API 配置？删除后不可恢复。", { title: "删除 API 配置" })) return;
      state.apiProfiles = state.apiProfiles.filter((profile) => profile.id !== id);
      renderApiProfiles();
      renderProfileOptions();
      await saveSettings();
    });
  });
  document.querySelectorAll(".testProfileCall").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".apiSummaryCard");
      const profile = state.apiProfiles.find((item) => item.id === card.dataset.id);
      testProfileData(profile, card.querySelector(".profileTestResult")).catch((error) => {
        card.querySelector(".profileTestResult").textContent = error.message;
      });
    });
  });
}

function renderApiEditor(profile) {
  const dialog = requireEl("apiProfileDialog");
  dialog.dataset.id = profile.id || uid();
  dialog.querySelector(".profileName").value = profile.name || "";
  dialog.querySelector(".profileMode").innerHTML = modeOptions(profile.mode || "openai_chat");
  dialog.querySelector(".profileEndpoint").value = profile.endpoint || "";
  dialog.querySelector(".profileKey").value = profile.apiKey === "********" ? "" : profile.apiKey || "";
  dialog.querySelector(".profileModelList").value = profileModels(profile).join("\n");
  dialog.querySelector(".profileHeaders").value = profile.headersJson || "{}";
  dialog.querySelector(".profileBodyTemplate").value = profile.bodyTemplate || "";
  dialog.querySelector(".profileRawCall").value = "";
  dialog.querySelector(".profileTestResult").textContent = profile.apiKey === "********" ? "Key 已保存在本地，留空保存不会覆盖。" : "";
}

function renderCustomerSources() {
  const container = $("customerSources");
  if (!container) return;
  if (!state.customerSources.length) {
    container.innerHTML = `<article class="emptyState"><h3>还没有客户源</h3><p>新增客户域名、产品页或站点地图链接后，会参与搜索候选加权。</p></article>`;
    return;
  }
  container.innerHTML = state.customerSources.map((source) => `
    <article class="apiSummaryCard" data-id="${escapeHtml(source.id)}">
      <div class="apiSummaryTop">
        <span class="apiDot"></span>
        <div>
          <h4>${escapeHtml(source.name || "客户源")}</h4>
          <p>${source.enabled === false ? "已停用" : "已启用"} · 权重 ${escapeHtml(source.weight ?? 3)} · ${escapeHtml((source.urls || []).length)} 条链接</p>
        </div>
      </div>
      <div class="apiSummaryActions">
        <button class="secondaryButton editCustomerSource" type="button">编辑</button>
        <button class="textButton deleteCustomerSource" type="button">删除</button>
      </div>
    </article>
  `).join("");
  container.querySelectorAll(".editCustomerSource").forEach((button) => {
    button.addEventListener("click", () => openCustomerSourceDialog(button.closest(".apiSummaryCard").dataset.id));
  });
  container.querySelectorAll(".deleteCustomerSource").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.closest(".apiSummaryCard").dataset.id;
      const ok = await confirmMessage("删除这个客户搜索源？", { title: "删除客户源", confirmText: "删除", variant: "danger" });
      if (!ok) return;
      state.customerSources = state.customerSources.filter((source) => source.id !== id);
      renderCustomerSources();
    });
  });
}

function openCustomerSourceDialog(id = "") {
  const dialog = requireEl("customerSourceDialog");
  const source = state.customerSources.find((item) => item.id === id) || {
    id: `customer_source_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    name: "",
    enabled: true,
    weight: 3,
    urls: [],
  };
  dialog.dataset.id = source.id;
  requireEl("customerSourceName").value = source.name || "";
  requireEl("customerSourceWeight").value = source.weight ?? 3;
  requireEl("customerSourceEnabled").checked = source.enabled !== false;
  requireEl("customerSourceUrls").value = customerSourceToText(source);
  requireEl("customerSourceFile").value = "";
  dialog.showModal();
}

async function readCustomerSourceFile(file) {
  if (!file) return;
  const text = await file.text();
  const textarea = requireEl("customerSourceUrls");
  textarea.value = textarea.value.trim() ? `${textarea.value.trim()}\n${text}` : text;
}

function saveCustomerSourceFromDialog() {
  const dialog = requireEl("customerSourceDialog");
  const source = {
    id: dialog.dataset.id || `customer_source_${Date.now()}`,
    name: requireEl("customerSourceName").value.trim() || "客户搜索源",
    enabled: Boolean(requireEl("customerSourceEnabled").checked),
    weight: Number(requireEl("customerSourceWeight").value || 3),
    urls: parseCustomerSourceText(requireEl("customerSourceUrls").value),
  };
  const index = state.customerSources.findIndex((item) => item.id === source.id);
  if (index >= 0) state.customerSources[index] = source;
  else state.customerSources.push(source);
  dialog.close();
  renderCustomerSources();
  showMessage(`客户源已保存，共 ${source.urls.length} 条链接。`, { title: "保存成功", eyebrow: "Saved", variant: "success" });
}

function openApiProfileDialog(id = "") {
  const profile = state.apiProfiles.find((item) => item.id === id) || {
    id: uid(),
    name: `API ${state.apiProfiles.length + 1}`,
    mode: "openai_chat",
    endpoint: "",
    apiKey: "",
    headersJson: "{}",
    bodyTemplate: "",
    availableModels: [],
    models: {}
  };
  renderApiEditor(profile);
  requireEl("apiProfileDialog").showModal();
}

function profileHasMaskedKey(profile) {
  return String(profile?.apiKey || "") === "********";
}

function collectProfileFromEditor() {
  const dialog = requireEl("apiProfileDialog");
  const old = state.apiProfiles.find((item) => item.id === dialog.dataset.id) || {};
  const typedKey = dialog.querySelector(".profileKey").value.trim();
  const apiKey = typedKey || (profileHasMaskedKey(old) ? "********" : old.apiKey || "");
  return {
    id: dialog.dataset.id,
    name: dialog.querySelector(".profileName").value.trim() || "未命名 API",
    mode: dialog.querySelector(".profileMode").value,
    endpoint: dialog.querySelector(".profileEndpoint").value.trim(),
    apiKey,
    headersJson: dialog.querySelector(".profileHeaders").value.trim() || "{}",
    bodyTemplate: dialog.querySelector(".profileBodyTemplate").value.trim(),
    availableModels: dialog.querySelector(".profileModelList").value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
    models: {}
  };
}

async function saveApiProfileFromDialog() {
  const profile = collectProfileFromEditor();
  const index = state.apiProfiles.findIndex((item) => item.id === profile.id);
  if (index >= 0) state.apiProfiles[index] = profile;
  else state.apiProfiles.push(profile);
  requireEl("apiProfileDialog").close();
  renderApiProfiles();
  renderProfileOptions();
  await saveSettings();
}

function bindApiProfileDialog() {
  const dialog = requireEl("apiProfileDialog");
  requireEl("apiProfileEditor").innerHTML = apiProfileEditorMarkup();
  dialog.querySelector(".parseProfileCall")?.addEventListener("click", () => parseRawCallIntoCard(dialog));
  dialog.querySelector(".profileRawCall")?.addEventListener("input", () => scheduleParseRawCall(dialog));
  dialog.querySelector(".testProfileCall")?.addEventListener("click", () => {
    testProfileData(collectProfileFromEditor(), dialog.querySelector(".profileTestResult")).catch((error) => {
      dialog.querySelector(".profileTestResult").textContent = error.message;
    });
  });
  on("saveApiProfile", "click", () => saveApiProfileFromDialog().catch(showError));
  on("cancelApiProfile", "click", () => dialog.close());
  on("cancelApiProfileBottom", "click", () => dialog.close());
}

function apiProfileEditorMarkup() {
  return `
        <div class="apiModalGrid">
          <div class="apiSection">
            <p class="apiSectionTitle">基础信息</p>
            <label>API 名称<input class="profileName" placeholder="例如 Claude 内网 / OpenRouter 便宜模型" /></label>
            <label>调用模式
              <select class="profileMode">${modeOptions()}</select>
            </label>
            <label>Endpoint<input class="profileEndpoint" placeholder="https://api.openai.com/v1/chat/completions 或含 {{model}} 的 Gemini URL" /></label>
            <label>API Key<input class="profileKey" type="password" placeholder="留空表示沿用已保存 Key" /></label>
          </div>
          <div class="apiSection">
            <p class="apiSectionTitle">自动解析</p>
            <label>粘贴调用配置
              <textarea class="profileRawCall" rows="10" placeholder="粘贴 curl、HTTP 请求头、.env、Claude Code JSON、Azure/OpenRouter/Gemini/DeepSeek 配置"></textarea>
            </label>
            <div class="buttonRow">
              <button class="secondaryButton parseProfileCall" type="button">解析到表单</button>
              <button class="secondaryButton testProfileCall" type="button">连通性检测</button>
            </div>
            <p class="profileTestResult muted"></p>
          </div>
        </div>
        <div class="apiModalGrid">
          <label>模型列表<textarea class="profileModelList" rows="6" placeholder="每行一个模型名"></textarea></label>
          <label>Extra Headers JSON<textarea class="profileHeaders" rows="6"></textarea></label>
        </div>
        <label>通用 JSON 请求体模板<textarea class="profileBodyTemplate" rows="5" placeholder='{"model":"{{model}}","messages":{{messages}}}'></textarea></label>
  `;
}

function collectProfilesFromDom() {
  return state.apiProfiles.map((profile) => ({ ...profile }));
}

async function loadConfig() {
  state.config = await api("/api/config");
  requireEl("language").value = state.config.language || "zh";
  requireEl("outputLanguage").value = state.config.outputLanguage || state.config.language || "zh";
  if ($("scenarioName")) $("scenarioName").value = state.config.scenarioName || "";
  state.apiProfiles = state.config.apiProfiles || [];
  state.customerSources = state.config.searchSettings?.customerSources || [];
  setPromptFields();
  renderSearchSuggestions();
  renderApiProfiles();
  renderProfileOptions();
  renderReferenceCards();
}

async function saveSettings() {
  const language = $("language").value;
  const prompts = state.config?.prompts || {};
  prompts.zh = {
    ...prompts.zh,
    ...collectPromptSystem("zh")
  };
  prompts.en = {
    ...prompts.en,
    ...collectPromptSystem("en")
  };
  state.config = await api("/api/config", {
    method: "PUT",
    body: JSON.stringify({
      language,
      outputLanguage: $("outputLanguage").value,
      scenarioName: $("scenarioName")?.value?.trim() || "",
      apiProfiles: collectProfilesFromDom(),
      taskAssignments: {
        outline: parseAssignment($("outlineProfile").value),
        article: parseAssignment($("articleProfile").value),
        evaluator: parseAssignment($("evaluatorProfile").value),
        revision: parseAssignment($("revisionProfile").value),
        entity_extractor: parseAssignment($("entityExtractorProfile").value),
        image: parseAssignment($("imageProfile").value),
        search_planner: parseAssignment($("searchPlannerProfile").value)
      },
      searchSettings: {
        enabled: true,
        searxngEndpoint: $("searxngEndpoint").value.trim(),
        rankerEndpoint: $("rankerEndpoint")?.value?.trim() || "",
        maxResults: Number($("searchMaxResults").value || 15),
        timeoutSeconds: Number($("searchTimeoutSeconds").value || 25),
        searxngEnabled: Boolean($("searxngEnabled")?.checked),
        rankerEnabled: Boolean($("rankerEnabled")?.checked),
        domainWeights: parseJsonField("domainWeights", {}),
        customerSources: state.customerSources,
      },
      gptZeroSettings: {
        enabled: Boolean($("gptZeroEnabled")?.checked),
        endpoint: $("gptZeroEndpoint")?.value?.trim() || "",
        apiKey: ($("gptZeroApiKey")?.textContent ?? $("gptZeroApiKey")?.value ?? "").trim(),
        weight: Number($("gptZeroWeight")?.value || 0.35),
        timeoutSeconds: Number($("gptZeroTimeoutSeconds")?.value || 60),
        headChars: Number($("gptZeroHeadChars")?.value || 500),
        tailChars: Number($("gptZeroTailChars")?.value || 500),
      },
      prompts
    })
  });
  state.apiProfiles = state.config.apiProfiles || [];
  renderApiProfiles();
  renderProfileOptions();
  closePromptEditors();
  await showMessage("全局设置已保存。", { title: "保存成功", eyebrow: "Saved", variant: "success" });
}

function iterationTags() {
  const raw = requireEl("iterationTag").value.trim();
  return raw ? raw.split(/[,，\s]+/).map((item) => item.trim()).filter(Boolean) : [];
}

function iterationGroupInfo() {
  const source = state.selectedTrainingBlog || {};
  const fallbackTitle = source.title || state.trainingResult?.outline?.selectedTopic || "Iterated Blog";
  return {
    groupId: source.groupId || source.id || `group_${Date.now()}`,
    groupName: source.groupName || source.title || fallbackTitle,
    source,
  };
}

async function saveIterationRound(round, label = "") {
  if (!round?.article && !round?.articleAfter) {
    throw new Error("这一轮没有可保存的文章内容。");
  }
  const { groupId, groupName, source } = iterationGroupInfo();
  const now = new Date().toISOString();
  const roundNo = round.round || (state.trainingResult?.rounds || []).indexOf(round) + 1;
  return api("/api/blogs", {
    method: "POST",
    body: JSON.stringify({
      id: `iter_${Date.now()}_${roundNo}_${Math.random().toString(16).slice(2)}`,
      title: `${groupName} - 第 ${roundNo} 轮`,
      createdAt: now,
      updatedAt: now,
      input: source.input || { brief: groupName },
      plan: source.plan || {},
      article: round.article || round.articleAfter,
      evaluation: round.evaluation || {},
      rounds: [round],
      language: source.language || requireEl("outputLanguage").value,
      tags: Array.from(new Set([...iterationTags(), `round-${roundNo}`])),
      sourceBlogId: source.id || "",
      groupId,
      groupName,
      versionLabel: label || `第 ${roundNo} 轮迭代`,
      iterationResult: {
        ...(state.trainingResult || {}),
        finalArticle: round.article || round.articleAfter,
        finalEvaluation: round.evaluation || {},
        rounds: [round],
      },
    })
  });
}

async function saveIterationAsBlog() {
  if (!state.trainingResult?.rounds?.length) {
    await showMessage("还没有可保存的迭代结果。");
    return;
  }
  await saveIterationRound(state.trainingResult.rounds[state.trainingResult.rounds.length - 1], "最终迭代版本");
  await loadBlogs();
  await showMessage("最终版本已保存到同一文章组。", { title: "保存成功", eyebrow: "Saved", variant: "success" });
}

async function saveAllIterationRounds() {
  const rounds = state.trainingResult?.rounds || [];
  if (!rounds.length) {
    await showMessage("还没有可保存的迭代轮次。");
    return;
  }
  for (const round of rounds) {
    await saveIterationRound(round);
  }
  await loadBlogs();
  await showMessage("全部轮次已保存到同一文章组。", { title: "保存成功", eyebrow: "Saved", variant: "success" });
}

async function saveIterationRoundByIndex(index) {
  const round = state.trainingResult?.rounds?.[index];
  if (!round) {
    await showMessage("没有找到这一轮结果。");
    return;
  }
  await saveIterationRound(round);
  await loadBlogs();
  await showMessage(`第 ${round.round || index + 1} 轮已保存到同一文章组。`, { title: "保存成功", eyebrow: "Saved", variant: "success" });
}

async function overwriteIterationBlog() {
  if (!state.trainingResult?.finalArticle) {
    await showMessage("还没有可覆盖的迭代结果。");
    return;
  }
  if (!state.selectedTrainingBlog?.id) {
    await showMessage("请先选择一篇已有 Blog，才能覆盖原文章。");
    return;
  }
  if (!await confirmMessage("确认用迭代结果覆盖原文章正文？这个操作会替换当前版本内容。", { title: "覆盖原文章" })) return;
  const tags = Array.from(new Set([...(state.selectedTrainingBlog.tags || []), ...iterationTags()]));
  const updated = await api(`/api/blogs/${state.selectedTrainingBlog.id}`, {
    method: "PUT",
    body: JSON.stringify({
      article: state.trainingResult.finalArticle,
      tags,
      evaluation: state.trainingResult.finalEvaluation || {},
      iterationResult: state.trainingResult,
      groupId: state.selectedTrainingBlog.groupId || state.selectedTrainingBlog.id,
      groupName: state.selectedTrainingBlog.groupName || state.selectedTrainingBlog.title,
      versionLabel: "覆盖后的当前版本"
    })
  });
  state.selectedTrainingBlog = updated;
  await loadBlogs();
  await showMessage("已覆盖原文章。", { title: "覆盖成功", eyebrow: "Saved", variant: "success" });
}

async function generateOutline({ useExistingBusy = false } = {}) {
  const button = requireEl("outlineSubNext");
  const progress = requireEl("outlineProgress");
  if (!useExistingBusy && !startBusy("outline", button, progress, "正在生成大纲...")) return;
  try {
    const input = collectInput();
    validateBrief(input);
    if (!selectedIntentOption()) {
      throw new Error("请先点击“搜索并生成标题”，完成内部意图识别和标题选择。");
    }
    if (!input.selectedTitle) {
      throw new Error("请先选择或手动填写文章标题。");
    }
    setOutlineFlowStep("outline");
    renderOutline(await api("/api/outline", { method: "POST", body: JSON.stringify(input), signal: taskSignal("outline") }));
    setOutlineFlowStep("done");
    setOutlineSubStep("outline");
    if (!useExistingBusy) finishBusy("outline", button, progress, "大纲已生成");
  } catch (error) {
    if (!useExistingBusy) failBusy("outline", button, progress, isAbortError(error) ? "已停止生成大纲" : "大纲生成失败");
    if (isAbortError(error)) return;
    throw error;
  }
}

async function generateBlog() {
  const button = requireEl("generateBtn");
  const progress = requireEl("generateProgress");
  if (!startBusy("generate", button, progress, "正在生成正文...")) return;
  resetGenProgress();
  const input = collectInput();
  try {
    validateBrief(input);
    if (!input.outline) {
      throw new Error("请先生成或填写大纲。");
    }
    let blog = null;
    await streamApi(
      "/api/generate/stream",
      input,
      (event) => {
        if (event.type === "error") {
          throw new Error(event.message || "正文生成失败");
        }
        renderGenerateProgress(event);
        if (event.type === "result") {
          blog = event.blog;
        }
      },
      taskSignal("generate")
    );
    if (!blog) throw new Error("正文生成没有返回结果。");
    showBlog(blog);
    await loadBlogs();
    selectModule("library");
    finishBusy("generate", button, progress, "正文已生成");
  } catch (error) {
    failBusy("generate", button, progress, isAbortError(error) ? "已停止生成正文" : "正文生成失败");
    if (isAbortError(error)) return;
    throw error;
  }
}

async function scoreTrainingArticle() {
  const button = requireEl("scoreArticleBtn");
  const progress = requireEl("trainingProgress");
  if (!startBusy("training", button, progress, "正在迭代内容...")) return;
  const trainingBrief = requireEl("trainingArticle").value.trim();
  const selectedBlog = state.selectedTrainingBlog;
  try {
    if (!trainingBrief && !selectedBlog) {
      throw new Error("请先选择一个已有 Blog，或填写迭代内容/需求。");
    }
    state.trainingResult = null;
    requireEl("trainingScorePanel").innerHTML = "";
    requireEl("promptEvolution").innerHTML = `<p class="muted">每轮完成后会立即显示分数、建议和内容变化。</p>`;
    resetTrainProgress();
    requireEl("trainingProgress").innerHTML = createProgress("准备迭代...");
    attachStopButton("training", requireEl("trainingProgress"));
    renderTrainingStageList({ stage: "outline", message: "等待迭代开始", round: 0 }, Number(requireEl("trainingRounds").value || 3));
    const sourceInput = selectedBlog?.input || {};
    let finalResult = null;
    let streamError = null;
    await streamApi(
      "/api/adversarial-train/stream",
      {
        language: requireEl("outputLanguage").value,
        ...(sourceInput || {}),
        brief: trainingBrief || sourceInput.brief || selectedBlog?.title || "",
        productType: sourceInput.productType || requireEl("productType").value.trim(),
        productName: sourceInput.productName || requireEl("productName").value.trim(),
        targetAudience: sourceInput.targetAudience || requireEl("targetAudience").value.trim(),
        promotionGoal: sourceInput.promotionGoal || requireEl("promotionGoal").value.trim() || "AI 检索曝光",
        market: sourceInput.market || requireEl("market").value.trim(),
        keywords: sourceInput.keywords || requireEl("keywords").value.trim(),
        productFileText: sourceInput.productFileText || state.productFileText,
        outline: selectedBlog?.plan || sourceInput.outline || state.outline,
        article: trainingBrief,
        seedArticle: selectedBlog?.article || trainingBrief || "",
        trainingBlogId: selectedBlog?.id || "",
        trainingGoal: requireEl("trainingRubric").value.trim(),
        humanFeedback: requireEl("trainingFeedback").value.trim(),
        rounds: Number(requireEl("trainingRounds").value || 3)
      },
      (event) => {
        if (event.type === "result") {
          finalResult = event.result;
          renderTrainingProgress({ stage: "done", message: "迭代完成", totalRounds: Number(requireEl("trainingRounds").value || 3) });
        } else if (event.type === "error") {
          streamError = new Error(event.message || "迭代请求失败");
          renderTrainingProgress(event);
        } else if (event.type === "round" && event.partialResult) {
          finalResult = event.partialResult;
          renderTrainingProgress(event);
          renderTrainingResult(event.partialResult);
        } else {
          renderTrainingProgress(event);
        }
      },
      taskSignal("training")
    );
    if (streamError) throw streamError;
    renderTrainingResult(finalResult || {});
    finishBusy("training", button, progress, "迭代完成");
  } catch (error) {
    failBusy("training", button, progress, isAbortError(error) ? "已停止迭代" : "迭代失败");
    if (isAbortError(error)) return;
    throw error;
  }
}

function renderTrainingResult(result) {
  state.trainingResult = result;
  const final = result.finalEvaluation || {};
  const finalAdvice = final.revisionAdvice || [];
  const finalAdviceList = Array.isArray(finalAdvice) ? finalAdvice : [finalAdvice].filter(Boolean);
  const firstScore = Number((result.rounds || [])[0]?.score || 0);
  const finalScore = Number(final.score || 0);
  const totalDelta = finalScore && firstScore ? finalScore - firstScore : 0;
  const currentRound = (result.rounds || []).length;
  const scoreTitle = result.inProgress ? `已完成第 ${currentRound} 轮` : "最终分数";
  const adviceTitle = result.inProgress ? "当前修改建议" : "最终修改建议";
  requireEl("trainingScorePanel").innerHTML = `
    <article class="iterationFinalCard">
      <div class="scoreHero">
        <span>${scoreTitle}</span>
        <strong>${escapeHtml(final.score || "-")}</strong>
        <em class="${totalDelta >= 0 ? "scoreUp" : "scoreDown"}">${totalDelta ? `${totalDelta > 0 ? "+" : ""}${totalDelta}` : "0"}</em>
      </div>
      ${scoreBreakdownHtml(final)}
      ${renderSeparatedAdvice(final, adviceTitle)}
    </article>
  `;
  requireEl("promptEvolution").innerHTML = (result.rounds || []).map((round, index, rounds) => {
    const diff = round.diff || {};
    const modification = round.modification || {};
    const added = toDisplayList(modification.added || diff.added);
    const removed = toDisplayList(modification.removed || diff.removed);
    const focus = (modification.changedFocus || modification.changeSummary || []).toString();
    const advice = round.evaluation?.revisionAdvice || [];
    const adviceItems = Array.isArray(advice) ? advice : [advice].filter(Boolean);
    const prevScore = index > 0 ? Number(rounds[index - 1]?.score || 0) : 0;
    const score = Number(round.score || 0);
    const delta = prevScore && score ? score - prevScore : 0;
    return `
      <article class="evolutionCard iterationRoundCard" data-round-index="${index}" tabindex="0">
        <div class="evolutionHead">
          <span>第 ${round.round} 轮迭代</span>
          <div class="roundScore">
            <b>${escapeHtml(round.score || "-")}</b>
            <em class="${delta >= 0 ? "scoreUp" : "scoreDown"}">${delta ? `${delta > 0 ? "+" : ""}${delta}` : index === 0 ? "baseline" : "0"}</em>
          </div>
        </div>
        ${scoreBreakdownHtml(round.evaluation || {})}
        <div class="roundAdvice">
          ${renderSeparatedAdvice(round.evaluation || {}, "本轮修改建议")}
        </div>
        ${focus ? `<p class="changeFocus"><b>本轮修改：</b>${escapeHtml(focus)}</p>` : ""}
        <div class="roundCardFooter">
          <span>${added.length} 项强化 · ${removed.length} 项删减</span>
          <div class="buttonRow">
            <button class="secondaryButton saveIterationRound" type="button" data-round-index="${index}">保存本轮</button>
            <button class="secondaryButton viewIterationArticle" type="button" data-round-index="${index}">查看修改与正文</button>
          </div>
        </div>
      </article>`;
  }).join("");
  if (!requireEl("promptEvolution").innerHTML) {
    requireEl("promptEvolution").innerHTML = `<p class="muted">每轮完成后会立即显示分数、建议和内容变化。</p>`;
  }
  document.querySelectorAll(".viewIterationArticle").forEach((button) => {
    button.addEventListener("click", () => openIterationArticle(Number(button.dataset.roundIndex)));
  });
  document.querySelectorAll(".saveIterationRound").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      saveIterationRoundByIndex(Number(button.dataset.roundIndex)).catch(showError);
    });
  });
  document.querySelectorAll(".iterationRoundCard").forEach((card) => {
    const openCard = () => openIterationArticle(Number(card.dataset.roundIndex));
    card.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      openCard();
    });
    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openCard();
    });
  });
}

function renderSeparatedAdvice(evaluation = {}, title = "修改建议") {
  const gptData = evaluation.gptZero || {};
  const gptAdvice = (gptData.revisionAdvice || []);
  const modelEval = evaluation.modelEvaluation || evaluation;
  const modelAdvice = (modelEval.revisionAdvice || evaluation.revisionAdvice || [])
    .filter((item) => !gptAdvice.includes(item));
  const gptSection = gptAdvice.length
    ? `<div class="adviceSection">
        <h4 class="adviceSectionTitle">GPTZero AI检测建议</h4>
        <ul>${gptAdvice.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>`
    : "";
  const modelSection = modelAdvice.length
    ? `<div class="adviceSection">
        <h4 class="adviceSectionTitle">EEAT 内容优化建议</h4>
        <ul>${modelAdvice.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>`
    : "";
  if (!gptSection && !modelSection) {
    return `<h4>${escapeHtml(title)}</h4><p class="muted">暂无建议。</p>`;
  }
  return `<h4>${escapeHtml(title)}</h4>${gptSection}${modelSection}`;
}

function scoreBreakdownHtml(evaluation = {}) {
  const breakdown = evaluation.scoreBreakdown || {};
  const eeat = evaluation.eeatReport || {};
  const quadrants = eeat.quadrantScores || evaluation.quadrantScores || {};
  const blockers = eeat.blockers || evaluation.blockers || [];
  const sources = eeat.scoringSources || evaluation.scoringSources || {};
  const status = eeat.publishStatus || evaluation.publishStatus || "";
  const mode = breakdown.mode || "model-only";
  const gptData = evaluation.gptZero || {};

  // ── Score chips row ──────────────────────────────────────────────────────
  const modelScore = breakdown.modelScore ?? evaluation.modelScore ?? evaluation.score ?? "-";
  const gptScore = breakdown.gptZeroScore;
  const combined = breakdown.combinedScore ?? evaluation.combinedScore ?? evaluation.score ?? "-";
  const gzWeight = Math.round((breakdown.gptZeroWeight || 0.65) * 100);
  const modeLabel = mode === "model+gptzero"
    ? `GPTZero 主导 ${gzWeight}% · EEAT 内容 ${100 - gzWeight}%`
    : (breakdown.gptZeroSkipped || breakdown.gptZeroError || "仅 EEAT 大模型评分（GPTZero 未启用）");

  const chipsHtml = `
    <div class="scoreBreakdown">
      <span class="scoreChipPrimary">GPTZero ${escapeHtml(gptScore != null ? String(gptScore) : "未启用")}</span>
      <span>EEAT内容 ${escapeHtml(String(modelScore))}</span>
      <span>综合 ${escapeHtml(String(combined))}</span>
      ${sources.ruleLocked !== undefined ? `<span class="scoreChipRule">规则锁定 ${escapeHtml(String(sources.ruleLocked))} 项</span>` : ""}
      ${sources.llm !== undefined ? `<span class="scoreChipLlm">大模型评 ${escapeHtml(String(sources.llm))} 项</span>` : ""}
      <small>${escapeHtml(modeLabel)}</small>
      ${status ? `<small>发布判定 ${escapeHtml(status)}</small>` : ""}
    </div>`;

  // ── EEAT quadrant grid ───────────────────────────────────────────────────
  const quadrantHtml = Object.keys(quadrants).length
    ? `<div class="eeatQuadrants">
        ${["Experience", "Expertise", "Authoritativeness", "Trustworthiness"].map(
          (key) => `<span>${escapeHtml(key)}<b>${escapeHtml(String(quadrants[key] ?? "-"))}</b></span>`
        ).join("")}
      </div>`
    : "";

  // ── EEAT blockers ────────────────────────────────────────────────────────
  const blockerHtml = blockers.length
    ? `<div class="eeatBlockers"><b>阻断项</b>${blockers.slice(0, 8).map(
        (item) => `<span title="${escapeHtml(item.evidence || "")}">${escapeHtml(item.id)} ${escapeHtml(item.name || "")}</span>`
      ).join("")}</div>`
    : "";

  // ── GPTZero detail panel ─────────────────────────────────────────────────
  let gptzeroHtml = "";
  if (gptData.enabled && !gptData.skipped) {
    const predClass = gptData.predictedClass || "unknown";
    const aip = gptData.aiProbability != null ? gptData.aiProbability + "%" : "-";
    const humanp = gptData.aiProbability != null ? (100 - gptData.aiProbability).toFixed(1) + "%" : "-";
    const conf = gptData.confidenceCategory
      ? ` · ${escapeHtml(gptData.confidenceCategory)} 置信度 (${escapeHtml(String(gptData.confidenceScore || ""))})`
      : "";
    const classLabel = { ai: "AI生成", human: "人类写作", mixed: "AI/人类混合", unknown: "未知" }[predClass] || predClass;
    const classColor = { ai: "#b54708", human: "#1a7a4a", mixed: "#7c5a00", unknown: "#555" }[predClass] || "#555";
    // Class probabilities row
    const cp = gptData.classProbabilities || {};
    const cpHtml = Object.keys(cp).length
      ? `<div class="gptzeroRow gptzeroCpRow">
          ${Object.entries(cp).map(([k,v]) =>
            `<span class="gptzeroCpItem"><em>${escapeHtml({ai:"AI",human:"人类",mixed:"混合"}[k]||k)}</em>${escapeHtml((v*100).toFixed(1))}%</span>`
          ).join("")}
        </div>`
      : "";
    const flagged = gptData.flaggedSentences || [];
    const flaggedHtml = flagged.length
      ? `<details class="flaggedDetails">
          <summary>AI标记句子 ${flagged.length} / ${gptData.totalSentences || "?"} 句</summary>
          <ol class="flaggedSentenceList">
            ${flagged.slice(0, 15).map(
              (s) => `<li><span class="flagAiProb">${escapeHtml(String(s.ai_prob))}%</span>${escapeHtml(s.sentence)}</li>`
            ).join("")}
            ${flagged.length > 15 ? `<li class="muted">…另有 ${flagged.length - 15} 句</li>` : ""}
          </ol>
        </details>`
      : `<p class="gptzeroNoneFlag">无高置信度 AI 句子被标记。</p>`;
    const errHtml = gptData.error ? `<p class="gptzeroError">调用失败：${escapeHtml(gptData.error)}</p>` : "";
    const subMsg = gptData.resultSubMessage ? `<p class="gptzeroSubMsg">${escapeHtml(gptData.resultSubMessage)}</p>` : "";
    // Subclass: pure_ai vs ai_paraphrased
    const subclassLabels = { pure_ai: "纯 AI 生成", ai_paraphrased: "AI 生成 + 洗稿改写" };
    const subclassColors = { pure_ai: "#b54708", ai_paraphrased: "#7c5a00" };
    const subclassHtml = gptData.aiSubclass
      ? `<div class="gptzeroRow">
          <span class="gptzeroLabel">子类型</span>
          <span style="color:${subclassColors[gptData.aiSubclass]||"#555"};font-weight:700">
            ${escapeHtml(subclassLabels[gptData.aiSubclass] || gptData.aiSubclass)}
          </span>
        </div>`
      : "";
    // Burstiness
    const burst = gptData.overallBurstiness ?? null;
    const burstHtml = burst !== null
      ? `<div class="gptzeroRow">
          <span class="gptzeroLabel">句式变化度</span>
          <span class="gptzeroBarLabel" title="Burstiness — 0=极均匀(AI特征), 越高越像人类写作">
            ${escapeHtml(burst.toFixed ? burst.toFixed(1) : String(burst))}
            ${burst < 5 ? '<span class="flagAiProb" style="margin-left:4px">AI特征</span>' : ''}
          </span>
        </div>`
      : "";
    gptzeroHtml = `
      <details class="gptzeroPanel" open>
        <summary>🔍 GPTZero 主检测 · <strong style="color:${classColor}">${escapeHtml(classLabel)}</strong> · AI概率 ${escapeHtml(aip)} · 人类感 ${escapeHtml(humanp)}</summary>
        <div class="gptzeroBody">
          <div class="gptzeroRow">
            <span class="gptzeroLabel">AI 概率</span>
            <span class="gptzeroBar"><span style="width:${escapeHtml(aip)};background:${classColor}"></span></span>
            <span class="gptzeroBarLabel">${escapeHtml(aip)} AI / ${escapeHtml(humanp)} 人类${escapeHtml(conf)}</span>
          </div>
          ${cpHtml}
          ${subclassHtml}
          ${burstHtml}
          ${subMsg}
          ${errHtml}
          ${flaggedHtml}
        </div>
      </details>`;
  } else if (gptData.skipped) {
    gptzeroHtml = `<p class="gptzeroSkipped">GPTZero：${escapeHtml(gptData.skipped)}</p>`;
  } else if (gptData.error) {
    gptzeroHtml = `<p class="gptzeroError">GPTZero 调用失败：${escapeHtml(gptData.error)}</p>`;
  }

  // ── EEAT 60-item breakdown ───────────────────────────────────────────────
  const allItems = evaluation.itemScores || (evaluation.eeatReport || {}).itemScores || [];
  let eeatItemsHtml = "";
  if (allItems.length) {
    const quadrantOrder = ["Experience", "Expertise", "Authoritativeness", "Trustworthiness"];
    const quadrantShort = { Experience: "E 体验", Expertise: "X 专业", Authoritativeness: "A 权威", Trustworthiness: "T 可信" };
    const byQuad = {};
    for (const item of allItems) {
      const q = item.quadrant || (
        item.id.startsWith("E") ? "Experience" :
        item.id.startsWith("X") ? "Expertise" :
        item.id.startsWith("A") ? "Authoritativeness" :
        item.id.startsWith("T") ? "Trustworthiness" : "Other"
      );
      (byQuad[q] = byQuad[q] || []).push(item);
    }
    const quadSections = quadrantOrder.map((q) => {
      const items = (byQuad[q] || []).slice().sort((a, b) => a.score - b.score);
      if (!items.length) return "";
      return `<div class="eeatQuadSection">
        <h5>${escapeHtml(quadrantShort[q] || q)}</h5>
        ${items.map((item) => {
          const score = item.score;
          const pct = score === 1 ? 100 : score === 0.5 ? 50 : 0;
          const scoreColor = pct === 100 ? "#1a7a4a" : pct === 50 ? "#7c5a00" : "#b54708";
          const srcBadge = item.source === "rule" || item.locked
            ? `<span class="eeatBadgeRule">规则</span>`
            : `<span class="eeatBadgeLlm">模型</span>`;
          return `<div class="eeatItemRow">
            <div class="eeatItemHead">
              <span class="eeatItemId">${escapeHtml(item.id)}</span>
              <span class="eeatItemName">${escapeHtml(item.name || "")}</span>
              ${srcBadge}
              <span class="eeatItemScore" style="color:${scoreColor}">${escapeHtml(String(score))}</span>
            </div>
            ${item.evidence ? `<p class="eeatItemEvidence">${escapeHtml(item.evidence)}</p>` : ""}
            ${item.suggestion && score < 1 ? `<p class="eeatItemSuggestion">${escapeHtml(item.suggestion)}</p>` : ""}
          </div>`;
        }).join("")}
      </div>`;
    }).join("");
    const total = allItems.length;
    const passed = allItems.filter((i) => i.score === 1).length;
    const half = allItems.filter((i) => i.score === 0.5).length;
    eeatItemsHtml = `
      <details class="eeatItemsPanel">
        <summary>EEAT 60项明细 · 满分 ${passed} / 半分 ${half} / 共 ${total}</summary>
        <div class="eeatItemsBody">
          ${quadSections}
        </div>
      </details>`;
  }

  return chipsHtml + quadrantHtml + blockerHtml + gptzeroHtml + eeatItemsHtml;
}

function openIterationArticle(index) {
  const round = state.trainingResult?.rounds?.[index];
  if (!round) return;
  const diff = round.diff || {};
  const modification = round.modification || {};
  const addedHtml = listHtml(modification.added || diff.added, "mark") || "<li>无明显新增</li>";
  const removedHtml = listHtml(modification.removed || diff.removed, "del") || "<li>无明显删减</li>";
  const focus = toDisplayList(modification.changedFocus || modification.changeSummary);
  const advice = toDisplayList(round.evaluation?.revisionAdvice);
  requireEl("iterationArticleTitle").textContent = `第 ${round.round} 轮迭代详情`;
  requireEl("iterationDetailScore").innerHTML = `
    <span>本轮分数</span>
    <strong>${escapeHtml(round.score || "-")}</strong>
    ${scoreBreakdownHtml(round.evaluation || {})}
  `;
  requireEl("iterationChangeSummary").innerHTML = `
    ${focus.length ? `<p class="changeFocus"><b>本轮修改：</b>${escapeHtml(focus.join("；"))}</p>` : ""}
    <div class="roundAdvice">
      ${renderSeparatedAdvice(round.evaluation || {}, "评价 AI 修改建议")}
    </div>
  `;
  requireEl("iterationAddedList").innerHTML = addedHtml;
  requireEl("iterationRemovedList").innerHTML = removedHtml;
  requireEl("iterationArticlePreview").innerHTML = renderMarkdown(round.article || round.articleAfter || "");
  requireEl("iterationArticleDialog").showModal();
}

async function loadBlogs() {
  state.blogs = await api("/api/blogs");
  renderLibrary();
  renderTrainingBlogOptions();
}

function renderLibrary() {
  const groups = filteredBlogGroups({
    query: $("librarySearch")?.value,
    dateField: $("libraryDateField")?.value || "updatedAt",
    from: $("libraryDateFrom")?.value,
    to: $("libraryDateTo")?.value,
  });
  requireEl("libraryList").innerHTML =
    groups.map((group) => {
      const isOpen = openLibraryGroups.has(group.id);
      return `
      <article class="libraryGroup ${isOpen ? "isOpen" : ""}" data-group-id="${escapeHtml(group.id)}">
        <div class="libraryGroupHead">
          <button class="libraryGroupToggle" type="button" data-group-id="${escapeHtml(group.id)}" aria-expanded="${isOpen ? "true" : "false"}">
            <span class="groupChevron">›</span>
            <strong>${fullTitleTip(group.name)}</strong>
            <span>${group.blogs.length} 个版本</span>
          </button>
          <button class="textButton renameGroup" type="button" data-group-id="${escapeHtml(group.id)}" data-group-name="${escapeHtml(group.name)}">改名</button>
        </div>
        <div class="libraryDateMeta">
          <span>创建 ${formatDateTime(group.createdAt)}</span>
          <span>最后修改 ${formatDateTime(group.updatedAt || group.createdAt)}</span>
        </div>
        <div class="libraryVersions" ${isOpen ? "" : "hidden"}>
          ${group.blogs
            .sort((a, b) => Number(a.versionIndex || 1) - Number(b.versionIndex || 1))
            .map((blog) => `
              <div class="libraryVersionRow">
                <button class="libraryItem" data-id="${blog.id}">
                  <strong>${fullTitleTip(blog.versionLabel || `v${blog.versionIndex || 1}`)}</strong>
                  <span>创建 ${formatDateTime(blog.createdAt)} · 修改 ${formatDateTime(blog.updatedAt || blog.createdAt)}</span>
                  <span>Score ${escapeHtml(blog.score || "-")} · ${escapeHtml(blog.productType || "未记录商品类型")}</span>
                </button>
                <div class="versionActions">
                  <button class="textButton renameVersion" type="button" data-id="${escapeHtml(blog.id)}" data-label="${escapeHtml(blog.versionLabel || `v${blog.versionIndex || 1}`)}">改名</button>
                  <button class="textButton dangerText deleteVersion" type="button" data-id="${escapeHtml(blog.id)}" data-label="${escapeHtml(blog.versionLabel || `v${blog.versionIndex || 1}`)}">删除</button>
                </div>
              </div>`)
            .join("")}
        </div>
      </article>`;
    }).join("") || `<p class="muted">暂无本地文章</p>`;
  bindTitleTooltips(requireEl("libraryList"));
  document.querySelectorAll(".libraryGroupToggle").forEach((button) => {
    button.addEventListener("click", () => {
      const groupId = button.dataset.groupId;
      if (openLibraryGroups.has(groupId)) openLibraryGroups.delete(groupId);
      else openLibraryGroups.add(groupId);
      renderLibrary();
    });
  });
  document.querySelectorAll(".libraryItem").forEach((item) => {
    item.classList.toggle("active", state.currentBlog?.id === item.dataset.id);
    item.addEventListener("click", () => {
      if (state.currentBlog?.id === item.dataset.id) {
        collapseBlogPreview();
      } else {
        openBlog(item.dataset.id).catch(showError);
      }
    });
  });
  document.querySelectorAll(".renameGroup").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openRenameDialog({
        title: "修改文章组名称",
        label: "组名称",
        value: button.dataset.groupName,
        eyebrow: "Article Group",
        onConfirm: (value) => renameBlogGroup(button.dataset.groupId, value),
      });
    });
  });
  document.querySelectorAll(".renameVersion").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openRenameDialog({
        title: "修改版本名称",
        label: "版本名称",
        value: button.dataset.label,
        eyebrow: "Version",
        onConfirm: (value) => renameBlogVersion(button.dataset.id, value),
      });
    });
  });
  document.querySelectorAll(".deleteVersion").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteBlogVersion(button.dataset.id, button.dataset.label).catch(showError);
    });
  });
}

async function openBlog(id) {
  showBlog(await api(`/api/blogs/${id}`));
}

function clearLibraryFilters() {
  requireEl("librarySearch").value = "";
  requireEl("libraryDateField").value = "updatedAt";
  requireEl("libraryDateFrom").value = "";
  requireEl("libraryDateTo").value = "";
  renderLibrary();
}

function clearTrainingFilters() {
  requireEl("trainingBlogSearch").value = "";
  requireEl("trainingDateField").value = "updatedAt";
  requireEl("trainingDateFrom").value = "";
  requireEl("trainingDateTo").value = "";
  renderTrainingBlogOptions();
}

async function renameBlogGroup(groupId, groupName) {
  await api(`/api/blog-groups/${encodeURIComponent(groupId)}`, {
    method: "PUT",
    body: JSON.stringify({ groupName })
  });
  openLibraryGroups.add(groupId);
  await loadBlogs();
}

async function renameBlogVersion(blogId, versionLabel) {
  const updated = await api(`/api/blogs/${blogId}`, {
    method: "PUT",
    body: JSON.stringify({ versionLabel })
  });
  openLibraryGroups.add(updated.groupId || updated.id);
  if (state.currentBlog?.id === blogId) showBlog(updated);
  await loadBlogs();
}

async function deleteBlogVersion(blogId, versionLabel = "") {
  if (!blogId) return;
  const label = versionLabel || "这个版本";
  if (!await confirmMessage(`确认删除「${label}」？删除后不可恢复。`, { title: "删除版本" })) return;
  await api(`/api/blogs/${blogId}`, { method: "DELETE" });
  if (state.currentBlog?.id === blogId) {
    state.currentBlog = null;
    collapseBlogPreview();
  }
  if (state.selectedTrainingBlog?.id === blogId) {
    clearTrainingBlog();
  }
  await loadBlogs();
  await showMessage("版本已删除。", { title: "删除成功", eyebrow: "Deleted", variant: "success" });
}

async function saveMarkdownOverwrite() {
  if (!state.currentBlog?.id) {
    await showMessage("请先选择一个版本。");
    return;
  }
  const article = requireEl("markdownOutput").value;
  const updated = await api(`/api/blogs/${state.currentBlog.id}`, {
    method: "PUT",
    body: JSON.stringify({ article })
  });
  showBlog(updated);
  await loadBlogs();
  await showMessage("当前版本已覆盖保存。", { title: "保存成功", eyebrow: "Saved", variant: "success" });
}

async function saveMarkdownAsVersion() {
  if (!state.currentBlog?.id) {
    await showMessage("请先选择一个版本。");
    return;
  }
  openRenameDialog({
    title: "另存为新版本",
    label: "新版本名称",
    value: `手动编辑版本`,
    eyebrow: "Save As",
    onConfirm: async (versionLabel) => {
      const created = await api(`/api/blogs/${state.currentBlog.id}/versions`, {
        method: "POST",
        body: JSON.stringify({
          article: requireEl("markdownOutput").value,
          versionLabel,
        })
      });
      openLibraryGroups.add(created.groupId || created.id);
      await loadBlogs();
      showBlog(created);
      await showMessage("已另存为新版本。", { title: "保存成功", eyebrow: "Saved", variant: "success" });
    },
  });
}

function markdownTitle(markdown, fallback = "手动导入文章") {
  const match = String(markdown || "").match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : fallback;
}

function normalizeMarkdownText(text) {
  return String(text || "")
    .replace(/\u00a0/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function escapeMarkdownText(text) {
  return String(text || "").replace(/([\\`*_{}\[\]()#+\-.!|>])/g, "\\$1");
}

function htmlToMarkdown(html) {
  const doc = new DOMParser().parseFromString(String(html || ""), "text/html");
  doc.querySelectorAll("script, style, noscript, iframe, svg").forEach((node) => node.remove());
  const blockTags = new Set(["P", "DIV", "SECTION", "ARTICLE", "HEADER", "FOOTER", "MAIN", "ASIDE"]);

  const inline = (node) => {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent.replace(/\s+/g, " ");
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    const tag = node.tagName;
    const content = Array.from(node.childNodes).map(inline).join("").replace(/\s+/g, " ").trim();
    if (!content && !["IMG", "BR"].includes(tag)) return "";
    if (tag === "STRONG" || tag === "B") return `**${content}**`;
    if (tag === "EM" || tag === "I") return `*${content}*`;
    if (tag === "CODE") return `\`${content.replace(/`/g, "\\`")}\``;
    if (tag === "A") {
      const href = node.getAttribute("href");
      return href ? `[${content || href}](${href})` : content;
    }
    if (tag === "IMG") {
      const src = node.getAttribute("src");
      const alt = node.getAttribute("alt") || "image";
      return src ? `![${escapeMarkdownText(alt)}](${src})` : "";
    }
    if (tag === "BR") return "\n";
    return Array.from(node.childNodes).map(inline).join("");
  };

  const block = (node, depth = 0) => {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent.trim();
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    const tag = node.tagName;
    const childBlocks = () => Array.from(node.childNodes).map((child) => block(child, depth)).filter(Boolean).join("\n\n");
    if (/^H[1-6]$/.test(tag)) return `${"#".repeat(Number(tag.slice(1)))} ${inline(node)}`;
    if (tag === "P") return inline(node);
    if (tag === "PRE") return `\`\`\`\n${node.textContent.trim()}\n\`\`\``;
    if (tag === "BLOCKQUOTE") return inline(node).split(/\n+/).map((line) => `> ${line.trim()}`).join("\n");
    if (tag === "UL" || tag === "OL") {
      return Array.from(node.children).filter((child) => child.tagName === "LI").map((li, index) => {
        const marker = tag === "OL" ? `${index + 1}.` : "-";
        return `${"  ".repeat(depth)}${marker} ${inline(li)}`;
      }).join("\n");
    }
    if (tag === "TABLE") {
      const rows = Array.from(node.querySelectorAll("tr")).map((row) => Array.from(row.children).map((cell) => inline(cell)));
      if (!rows.length) return "";
      const header = rows[0];
      return [
        `| ${header.join(" | ")} |`,
        `| ${header.map(() => "---").join(" | ")} |`,
        ...rows.slice(1).map((row) => `| ${row.join(" | ")} |`)
      ].join("\n");
    }
    if (tag === "LI") return inline(node);
    if (blockTags.has(tag) || ["BODY", "HTML"].includes(tag)) return childBlocks();
    return inline(node);
  };

  return normalizeMarkdownText(block(doc.body || doc));
}

function getImportFormat() {
  return document.querySelector(".importFormatSwitch button.isActive")?.dataset.format || "markdown";
}

function setImportFormat(format) {
  const normalized = format === "html" ? "html" : "markdown";
  document.querySelectorAll(".importFormatSwitch button").forEach((button) => {
    button.classList.toggle("isActive", button.dataset.format === normalized);
  });
  const label = requireEl("importMarkdownBodyLabel");
  const textarea = requireEl("importMarkdownBody");
  if (normalized === "html") {
    label.textContent = "HTML 正文";
    textarea.placeholder = "<article>\n  <h1>标题</h1>\n  <p>在这里粘贴 HTML 文档。</p>\n</article>";
  } else {
    label.textContent = "Markdown 正文";
    textarea.placeholder = "# 标题\n\n在这里粘贴 Markdown 文档。";
  }
}

function openImportMarkdownDialog() {
  requireEl("importMarkdownTitle").value = "";
  requireEl("importMarkdownVersion").value = "手动导入版本";
  requireEl("importMarkdownProductType").value = "";
  requireEl("importMarkdownTags").value = "";
  requireEl("importMarkdownBody").value = "";
  setImportFormat("markdown");
  requireEl("importMarkdownDialog").showModal();
  requireEl("importMarkdownBody").focus();
}

function closeImportMarkdownDialog() {
  requireEl("importMarkdownDialog").close();
}

async function saveImportedMarkdown() {
  const rawArticle = requireEl("importMarkdownBody").value.trim();
  const importFormat = getImportFormat();
  const article = importFormat === "html" ? htmlToMarkdown(rawArticle) : normalizeMarkdownText(rawArticle);
  if (!rawArticle || !article) {
    await showMessage(`请先粘贴 ${importFormat === "html" ? "HTML" : "Markdown"} 正文。`, { title: "内容为空" });
    return;
  }
  const now = new Date().toISOString();
  const title = requireEl("importMarkdownTitle").value.trim() || markdownTitle(article);
  const versionLabel = requireEl("importMarkdownVersion").value.trim() || "手动导入版本";
  const tags = requireEl("importMarkdownTags").value.split(/[,，\s]+/).map((item) => item.trim()).filter(Boolean);
  const productType = requireEl("importMarkdownProductType").value.trim();
  const blog = await api("/api/blogs", {
    method: "POST",
    body: JSON.stringify({
      id: `import_${Date.now()}_${Math.random().toString(16).slice(2)}`,
      title,
      createdAt: now,
      updatedAt: now,
      input: { brief: title, productType },
      plan: {},
      article,
      importFormat,
      evaluation: {},
      rounds: [],
      language: requireEl("outputLanguage").value,
      groupName: title,
      versionLabel,
      versionIndex: 1,
      tags,
    })
  });
  blog.groupId = blog.groupId || blog.id;
  closeImportMarkdownDialog();
  openLibraryGroups.add(blog.groupId || blog.id);
  await loadBlogs();
  showBlog(blog);
  await showMessage(`${importFormat === "html" ? "HTML 已解析为 Markdown 并" : "Markdown 已"}保存到文章库。`, { title: "导入成功", eyebrow: "Saved", variant: "success" });
}

function renderTrainingBlogOptions() {
  if (!$("trainingBlogCards")) return;
  const groups = filteredBlogGroups({
    query: $("trainingBlogSearch")?.value,
    dateField: $("trainingDateField")?.value || "updatedAt",
    from: $("trainingDateFrom")?.value,
    to: $("trainingDateTo")?.value,
  });
  requireEl("trainingBlogCards").innerHTML =
    groups.map((group) => {
      const isOpen = openTrainingGroups.has(group.id);
      return `
      <article class="libraryGroup ${isOpen ? "isOpen" : ""}" data-group-id="${escapeHtml(group.id)}">
        <div class="libraryGroupHead">
          <button class="libraryGroupToggle trainingGroupToggle" type="button" data-group-id="${escapeHtml(group.id)}" aria-expanded="${isOpen ? "true" : "false"}">
            <span class="groupChevron">›</span>
            <strong>${fullTitleTip(group.name)}</strong>
            <span>${group.blogs.length} 个版本</span>
          </button>
        </div>
        <div class="libraryDateMeta">
          <span>创建 ${formatDateTime(group.createdAt)}</span>
          <span>最后修改 ${formatDateTime(group.updatedAt || group.createdAt)}</span>
        </div>
        <div class="libraryVersions" ${isOpen ? "" : "hidden"}>
          ${group.blogs
            .sort((a, b) => Number(a.versionIndex || 1) - Number(b.versionIndex || 1))
            .map((blog) => `
              <div class="libraryVersionRow singleAction">
                <button class="libraryItem blogPickCard" type="button" data-id="${escapeHtml(blog.id)}">
                  <strong>${fullTitleTip(blog.versionLabel || `v${blog.versionIndex || 1}`)}</strong>
                  <span>创建 ${formatDateTime(blog.createdAt)} · 修改 ${formatDateTime(blog.updatedAt || blog.createdAt)}</span>
                  <span>Score ${escapeHtml(blog.score || "-")} · ${escapeHtml(blog.productType || "未记录商品类型")}</span>
                </button>
              </div>`)
            .join("")}
        </div>
      </article>`;
    }).join("") || `<p class="muted">暂无可选 Blog。</p>`;
  bindTitleTooltips(requireEl("trainingBlogCards"));
  document.querySelectorAll(".trainingGroupToggle").forEach((button) => {
    button.addEventListener("click", () => {
      const groupId = button.dataset.groupId;
      if (openTrainingGroups.has(groupId)) openTrainingGroups.delete(groupId);
      else openTrainingGroups.add(groupId);
      renderTrainingBlogOptions();
    });
  });
  document.querySelectorAll(".blogPickCard").forEach((button) => {
    button.addEventListener("click", () => selectTrainingBlog(button.dataset.id).catch(showError));
  });
}

function renderCompareSelectionSummary() {
  const selected = state.blogs.filter((blog) => state.compareSelectedBlogIds.has(blog.id));
  requireEl("compareSelectionSummary").innerHTML = `
    <article><b>已选文章</b><span>${selected.length || "未选择"}</span></article>
    <article><b>最多建议</b><span>8 篇</span></article>
    <article><b>评分模型</b><span>评价 AI</span></article>`;
}

function renderCompareBlogOptions() {
  const groups = filteredBlogGroups({
    query: $("compareBlogSearch")?.value,
    dateField: $("compareDateField")?.value || "updatedAt",
    from: $("compareDateFrom")?.value,
    to: $("compareDateTo")?.value,
  });
  requireEl("compareBlogCards").innerHTML =
    groups.map((group) => `
      <article class="libraryGroup isOpen" data-group-id="${escapeHtml(group.id)}">
        <div class="libraryGroupHead">
          <strong>${fullTitleTip(group.name)}</strong>
          <span>${group.blogs.length} 个版本</span>
        </div>
        <div class="libraryVersions">
          ${group.blogs
            .sort((a, b) => Number(a.versionIndex || 1) - Number(b.versionIndex || 1))
            .map((blog) => {
              const checked = state.compareSelectedBlogIds.has(blog.id) ? "checked" : "";
              return `
                <label class="comparePickRow">
                  <input type="checkbox" class="compareBlogPick" data-id="${escapeHtml(blog.id)}" ${checked} />
                  <span>
                    <b>${fullTitleTip(blog.versionLabel || `v${blog.versionIndex || 1}`)}</b>
                    <em>${escapeHtml(blog.title || group.name)} · Score ${escapeHtml(blog.score || "-")}</em>
                  </span>
                </label>`;
            })
            .join("")}
        </div>
      </article>`).join("") || `<p class="muted">暂无可选 Blog。</p>`;
  bindTitleTooltips(requireEl("compareBlogCards"));
  document.querySelectorAll(".compareBlogPick").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) state.compareSelectedBlogIds.add(input.dataset.id);
      else state.compareSelectedBlogIds.delete(input.dataset.id);
      renderCompareSelectionSummary();
    });
  });
  renderCompareSelectionSummary();
}

async function openCompareBlogDialog() {
  await loadBlogs();
  renderCompareBlogOptions();
  requireEl("compareBlogDialog").showModal();
}

function clearCompareSelection() {
  state.compareSelectedBlogIds.clear();
  state.compareResult = null;
  requireEl("compareResults").innerHTML = "";
  renderCompareSelectionSummary();
  renderCompareBlogOptions();
}

async function scoreCompareArticles() {
  const button = requireEl("compareScoreBtn");
  const progress = requireEl("compareProgress");
  if (!startBusy("compare", button, progress, "正在评分比较...")) return;
  try {
    const ids = Array.from(state.compareSelectedBlogIds).slice(0, 8);
    if (!ids.length) throw new Error("请先选择要评分比较的文章。");
    setProgress(progress, 18, "正在读取文章正文...");
    const articles = [];
    for (const id of ids) {
      const blog = await api(`/api/blogs/${id}`, { signal: taskSignal("compare") });
      articles.push({
        id: blog.id,
        title: blog.title,
        groupName: blog.groupName,
        versionLabel: blog.versionLabel,
        article: blog.article,
      });
    }
    setProgress(progress, 35, "评价 AI 正在逐篇评分...");
    const result = await api("/api/score/compare", {
      method: "POST",
      body: JSON.stringify({
        language: requireEl("outputLanguage").value,
        articles,
        rubric: requireEl("compareRubric").value.trim(),
      }),
      signal: taskSignal("compare"),
    });
    state.compareResult = result;
    renderCompareResults(result);
    finishBusy("compare", button, progress, "评分比较完成");
  } catch (error) {
    failBusy("compare", button, progress, isAbortError(error) ? "已停止评分比较" : "评分比较失败");
    if (isAbortError(error)) return;
    throw error;
  }
}

function renderCompareResults(result) {
  const rows = result.results || [];
  requireEl("compareResults").innerHTML = `
    <article class="iterationFinalCard compareSummaryCard">
      <div class="scoreHero">
        <span>平均分</span>
        <strong>${escapeHtml(result.averageScore || "-")}</strong>
        <em>${escapeHtml(rows.length)} 篇</em>
      </div>
      <h4>总体点评</h4>
      <p>${escapeHtml(result.summary || "暂无点评。")}</p>
    </article>
    ${rows.map((item, index) => {
      const evaluation = item.evaluation || {};
      const advice = toDisplayList(evaluation.revisionAdvice || evaluation.risks || evaluation.strengths);
      return `
        <article class="evolutionCard compareScoreCard">
          <div class="evolutionHead">
            <span>#${index + 1} ${escapeHtml(item.versionLabel || item.title || "未命名文章")}</span>
            <div class="roundScore"><b>${escapeHtml(item.score || "-")}</b><em>${item.id === result.bestId ? "best" : "score"}</em></div>
          </div>
          ${scoreBreakdownHtml(evaluation)}
          <h4>${escapeHtml(item.groupName || item.title || "未命名文章")}</h4>
          <p class="muted">${escapeHtml(item.articlePreview || "")}</p>
          <div class="roundAdvice">
            <h4>评价 AI 点评</h4>
            <ul>${advice.slice(0, 5).map((entry) => `<li>${escapeHtml(entry)}</li>`).join("") || "<li>评价 AI 未返回细项。</li>"}</ul>
          </div>
        </article>`;
    }).join("")}`;
}

async function selectTrainingBlog(id) {
  if (!id) {
    state.selectedTrainingBlog = null;
    requireEl("trainingBlogMeta").textContent = "选择文章后，会把该 Blog 的正文作为迭代起点。";
    return;
  }
  const blog = await api(`/api/blogs/${id}`);
  state.selectedTrainingBlog = blog;
  requireEl("trainingArticle").value = blog.article || blog.input?.brief || blog.title || "";
  requireEl("trainingBlogMeta").textContent = `${blog.groupName || blog.title || "Untitled"} · ${blog.versionLabel || `v${blog.versionIndex || 1}`} · 已载入迭代起点`;
  requireEl("trainingBlogDialog").close();
}

function clearTrainingBlog() {
  state.selectedTrainingBlog = null;
  requireEl("trainingBlogMeta").textContent = "选择文章后，会把该 Blog 的正文作为迭代起点。";
}

function clearGeneratedOutlineOnInputChange() {
  if (!state.outline && !requireEl("outlineJson").value.trim()) return;
  renderOutline(null);
}

function clearResearchOnInputChange() {
  state.searchResults = [];
  state.analysisSearchResults = [];
  state.intentOptions = [];
  state.selectedIntentId = "";
  state.titleOptions = [];
  state.titleStrategy = null;
  state.selectedTitleId = "";
  state.selectedTitleText = "";
  state.selectedTitleTrack = "both";
  state.selectedCitationRefs.clear();
  renderReferenceCards();
  renderInternalIntentStatus();
  renderTitleOptions();
  clearGeneratedOutlineOnInputChange();
}

async function deleteCurrent() {
  if (!state.currentBlog) return;
  if (!await confirmMessage("确认删除当前本地文章？删除后不可恢复。", { title: "删除当前文章" })) return;
  await api(`/api/blogs/${state.currentBlog.id}`, { method: "DELETE" });
  state.currentBlog = null;
  collapseBlogPreview();
  await loadBlogs();
  state.selectedTrainingBlog = null;
  await showMessage("当前文章已删除。", { title: "删除成功", eyebrow: "Deleted", variant: "success" });
}

function selectModule(moduleName) {
  document.querySelectorAll(".moduleCard").forEach((card) => card.classList.toggle("active", card.dataset.module === moduleName));
  document.querySelectorAll(".module").forEach((module) => module.classList.remove("active"));
  requireEl(`${moduleName}Module`).classList.add("active");
}

function setWizardStep(step) {
  const next = Math.max(0, Math.min(2, Number(step) || 0));
  state.wizardStep = next;
  document.querySelectorAll(".wizardPage").forEach((page) => {
    page.classList.toggle("active", Number(page.dataset.wizardPage) === next);
  });
  document.querySelectorAll(".wizardDot").forEach((dot) => {
    dot.classList.toggle("active", Number(dot.dataset.wizardStep) === next);
  });
}

async function advanceWizard() {
  if (state.wizardStep === 0) {
    const input = collectInput();
    validateBrief(input);
    setWizardStep(1);
    return;
  }
  if (state.wizardStep === 1) {
    if (state.outline && $("outlineTitleInput")) {
      collectOutlineEditor({ silent: true });
    } else if ($("outlineJson")?.value.trim()) {
      applyOutlineJson();
    }
    if (!collectInput().outline) {
      throw new Error("请先点击“搜索并生成标题”，确认标题后点击“按标题生成大纲”。大纲生成后才能进入正文。");
    }
    setWizardStep(2);
  }
}

async function advanceOutlineSubStep() {
  if (state.outlineSubStep === "research") {
    if (state.titleOptions.length || collectInput().selectedTitle) {
      await generateOutline();
    } else {
      await prepareOutlineResearch();
    }
    return;
  }
  if (state.outlineSubStep === "outline") {
    if (state.outline && $("outlineTitleInput")) {
      collectOutlineEditor({ silent: true });
    } else if ($("outlineJson")?.value.trim()) {
      applyOutlineJson();
    }
    if (!collectInput().outline) {
      throw new Error("请先生成大纲，大纲生成后才能进入正文。");
    }
    setWizardStep(2);
    // 直接触发正文生成，无需再手动点击
    generateBlog().catch(showError);
  }
}

function backOutlineSubStep() {
  if (state.outlineSubStep === "outline") {
    setOutlineSubStep("research");
  }
}

async function readImages(files) {
  const readers = Array.from(files || []).map((file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, dataUrl: reader.result });
    reader.onerror = reject;
    reader.readAsDataURL(file);
  }));
  state.images = await Promise.all(readers);
}

function bindEvents() {
  on("language", "change", () => {
    if (state.config) state.config.language = requireEl("language").value;
    setPromptFields();
  });
  on("outputLanguage", "change", () => {
    renderSearchSuggestions();
    clearGeneratedOutlineOnInputChange();
  });
  document.addEventListener("keydown", handleRecommendationUndo);
  bindAll(".moduleCard", "click", (event) => selectModule(event.currentTarget.dataset.module));
  on("addApiProfile", "click", () => openApiProfileDialog());
  bindApiProfileDialog();
  on("addCustomerSource", "click", () => openCustomerSourceDialog());
  on("cancelCustomerSource", "click", () => requireEl("customerSourceDialog").close());
  on("cancelCustomerSourceBottom", "click", () => requireEl("customerSourceDialog").close());
  on("saveCustomerSource", "click", () => {
    try {
      saveCustomerSourceFromDialog();
    } catch (error) {
      showError(error);
    }
  });
  on("customerSourceFile", "change", (event) => readCustomerSourceFile(event.target.files?.[0]).catch(showError));
  on("saveSettings", "click", async (event) => {
    event.preventDefault();
    try {
      await saveSettings();
    } catch (error) {
      showError(error);
    }
  });
  bindAll(".settingsTab", "click", (event) => selectSettingsPage(event.currentTarget.dataset.settingsPage));
  bindAll(".promptEditToggle", "click", (event) => togglePromptEditor(event.currentTarget));
  on("prepareOutlineBtn", "click", () => {
    if (state.outlineSubStep === "outline") {
      advanceOutlineSubStep().catch(showError);
    } else {
      prepareOutlineResearch().catch(showError);
    }
  });
  on("applyOutlineEditor", "click", () => {
    try {
      collectOutlineEditor();
    } catch (error) {
      showError(error);
    }
  });
  on("generateBtn", "click", () => generateBlog().catch(showError));
  bindAll(".wizardNext", "click", () => advanceWizard().catch(showError));
  on("outlineSubNext", "click", () => advanceOutlineSubStep().catch(showError));
  on("outlineSubBack", "click", backOutlineSubStep);
  bindAll(".wizardBack", "click", () => setWizardStep(state.wizardStep - 1));
  bindAll(".wizardDot", "click", (event) => setWizardStep(event.currentTarget.dataset.wizardStep));
  on("searchReferencesBtn", "click", () => searchReferences().catch(showError));
  on("analyzeIntentBtn", "click", () => analyzeIntents().catch(showError));
  on("selectedTitleInput", "input", () => {
    state.selectedTitleText = requireEl("selectedTitleInput").value.trim();
    clearGeneratedOutlineOnInputChange();
  });
  on("selectAllCitationRefs", "click", () => {
    state.searchResults.forEach((item) => state.selectedCitationRefs.add(item.id));
    renderReferenceCards();
  });
  on("clearReferenceSelection", "click", clearReferenceSelection);
  on("generateImageBtn", "click", () => generateImagePlaceholder().catch(showError));
  bindAll(".imagePlanCard", "click", (event) => {
      const card = event.currentTarget;
      state.imageMode = card.dataset.imageMode || "manual";
      document.querySelectorAll(".imagePlanCard").forEach((item) => item.classList.toggle("active", item === card));
      clearGeneratedOutlineOnInputChange();
  });
  on("viewLibraryAfterGenerate", "click", () => selectModule("library"));
  on("scoreArticleBtn", "click", () => scoreTrainingArticle().catch(showError));
  on("saveIterationAsBlog", "click", () => saveIterationAsBlog().catch(showError));
  on("saveAllIterationRounds", "click", () => saveAllIterationRounds().catch(showError));
  on("overwriteIterationBlog", "click", () => overwriteIterationBlog().catch(showError));
  on("productFile", "change", async (event) => {
    const file = event.target.files?.[0];
    state.productFileText = file ? await file.text() : "";
  });
  on("imageFiles", "change", async (event) => {
    await readImages(event.target.files);
    clearGeneratedOutlineOnInputChange();
  });
  ["brief", "market", "productType", "productName", "targetAudience", "promotionGoal", "keywords"].forEach((id) => {
    on(id, "input", clearResearchOnInputChange);
  });
  ["imagePrompt"].forEach((id) => {
    on(id, "input", clearGeneratedOutlineOnInputChange);
  });
  on("refreshBlogs", "click", () => loadBlogs().catch(showError));
  on("openTrainingBlogPicker", "click", async () => {
    await loadBlogs();
    if (state.selectedTrainingBlog?.groupId || state.selectedTrainingBlog?.id) {
      openTrainingGroups.add(state.selectedTrainingBlog.groupId || state.selectedTrainingBlog.id);
    }
    renderTrainingBlogOptions();
    requireEl("trainingBlogDialog").showModal();
  });
  on("closeTrainingBlogDialog", "click", () => requireEl("trainingBlogDialog").close());
  on("closeIterationArticleDialog", "click", () => requireEl("iterationArticleDialog").close());
  on("collapseBlogPreview", "click", collapseBlogPreview);
  on("blogArticleDialog", "close", () => {
    if (state.currentBlog) collapseBlogPreview();
  });
  on("cancelRenameDialog", "click", closeRenameDialog);
  on("cancelRenameDialogBottom", "click", closeRenameDialog);
  on("confirmRenameDialog", "click", () => confirmRenameDialog().catch(showError));
  on("messageDialogClose", "click", () => closeMessageDialog(false));
  on("messageDialogCancel", "click", () => closeMessageDialog(false));
  on("messageDialogConfirm", "click", () => closeMessageDialog(true));
  on("messageDialog", "cancel", (event) => {
    event.preventDefault();
    closeMessageDialog(false);
  });
  on("messageDialog", "close", () => {
    if (messageDialogState) closeMessageDialog(false);
  });
  on("renameDialogInput", "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      confirmRenameDialog().catch(showError);
    }
  });
  on("clearTrainingBlog", "click", clearTrainingBlog);
  on("trainingBlogSearch", "input", renderTrainingBlogOptions);
  on("trainingDateField", "change", renderTrainingBlogOptions);
  on("trainingDateFrom", "change", renderTrainingBlogOptions);
  on("trainingDateTo", "change", renderTrainingBlogOptions);
  on("clearTrainingFilters", "click", clearTrainingFilters);
  on("librarySearch", "input", renderLibrary);
  on("libraryDateField", "change", renderLibrary);
  on("libraryDateFrom", "change", renderLibrary);
  on("libraryDateTo", "change", renderLibrary);
  on("clearLibraryFilters", "click", clearLibraryFilters);
  on("copyMarkdown", "click", async () => {
    await navigator.clipboard.writeText(requireEl("markdownOutput").value);
    await showMessage("Markdown 已复制。", { title: "复制成功", eyebrow: "Copied", variant: "success" });
  });
  on("saveMarkdownOverwrite", "click", () => saveMarkdownOverwrite().catch(showError));
  on("saveMarkdownAsVersion", "click", () => saveMarkdownAsVersion().catch(showError));
  on("openImportMarkdown", "click", openImportMarkdownDialog);
  on("closeImportMarkdownDialog", "click", closeImportMarkdownDialog);
  on("cancelImportMarkdown", "click", closeImportMarkdownDialog);
  bindAll(".importFormatSwitch button", "click", (event) => setImportFormat(event.currentTarget.dataset.format));
  on("saveImportedMarkdown", "click", () => saveImportedMarkdown().catch(showError));
  on("openCompareBlogPicker", "click", () => openCompareBlogDialog().catch(showError));
  on("closeCompareBlogDialog", "click", () => requireEl("compareBlogDialog").close());
  on("compareBlogSearch", "input", renderCompareBlogOptions);
  on("compareDateField", "change", renderCompareBlogOptions);
  on("compareDateFrom", "change", renderCompareBlogOptions);
  on("compareDateTo", "change", renderCompareBlogOptions);
  on("clearCompareSelection", "click", clearCompareSelection);
  on("compareScoreBtn", "click", () => scoreCompareArticles().catch(showError));
  on("deleteCurrent", "click", () => deleteCurrent().catch(showError));
  on("markdownOutput", "input", () => {
    renderArticleView(state.articleViewMode);
  });
  bindAll(".articleViewSwitch button", "click", (event) => renderArticleView(event.currentTarget.dataset.view));
}

const rawParseTimers = new WeakMap();

function scheduleParseRawCall(card) {
  if (!card) return;
  clearTimeout(rawParseTimers.get(card));
  rawParseTimers.set(card, setTimeout(() => parseRawCallIntoCard(card), 500));
}

function readEnvLike(raw) {
  const env = {};
  for (const match of raw.matchAll(/^\s*(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=\s*["']?([^"'\r\n]+)["']?\s*$/gim)) {
    env[match[1]] = match[2].trim();
  }
  try {
    const parsed = JSON.parse(raw);
    const source = parsed.env || parsed;
    if (source && typeof source === "object" && !Array.isArray(source)) {
      Object.assign(env, source);
    }
  } catch {
    // Plain curl/header text can continue through the generic parser.
  }
  return env;
}

function setModels(card, models) {
  const list = card.querySelector(".profileModelList");
  const next = new Set(list.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean));
  models.map((item) => String(item || "").trim()).filter(Boolean).forEach((model) => next.add(model));
  list.value = Array.from(next).join("\n");
}

function replaceModels(card, models) {
  card.querySelector(".profileModelList").value = models.map((item) => String(item || "").trim()).filter(Boolean).join("\n");
}

function setHeaders(card, headers) {
  const clean = {};
  Object.entries(headers).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    clean[key] = String(value).trim();
  });
  if (Object.keys(clean).length) {
    card.querySelector(".profileHeaders").value = JSON.stringify(clean, null, 2);
  }
}

function firstValue(...values) {
  return values.find((value) => value !== undefined && value !== null && String(value).trim() !== "");
}

function buildEndpoint(base, suffix) {
  const trimmed = String(base || "").trim().replace(/\/+$/, "");
  if (!trimmed) return "";
  if (new RegExp(`${suffix.replace(/\//g, "\\/")}$`, "i").test(trimmed)) return trimmed;
  if (/\/v1\/chat\/completions$/i.test(trimmed) && suffix === "/v1/responses") {
    return trimmed.replace(/\/chat\/completions$/i, "/responses");
  }
  if (/\/v1$/i.test(trimmed) && suffix.startsWith("/v1/")) return `${trimmed}${suffix.slice(3)}`;
  return `${trimmed}${suffix}`;
}

function appendPathForRequest(endpoint, suffix) {
  const trimmed = String(endpoint || "").trim().replace(/\/+$/, "");
  if (!trimmed) return "";
  if (/\/(messages|chat\/completions|responses)$/i.test(trimmed)) return trimmed;
  return buildEndpoint(trimmed, suffix);
}

function buildGeminiEndpoint(base, modelName = "") {
  const trimmed = String(base || "").trim().replace(/\/+$/, "");
  if (!trimmed) return "https://generativelanguage.googleapis.com/v1beta/models/{{model}}:generateContent";
  if (/generateContent/i.test(trimmed)) {
    return modelName ? trimmed.replace(modelName, "{{model}}") : trimmed.replace(/\/models\/[^/:]+:generateContent/i, "/models/{{model}}:generateContent");
  }
  if (/\/models$/i.test(trimmed)) return `${trimmed}/{{model}}:generateContent`;
  return `${trimmed}/models/{{model}}:generateContent`;
}

function inferProvider(raw, env, endpoint) {
  const text = `${raw}\n${endpoint || ""}`;
  if (/openai\.azure\.com|AZURE_OPENAI_|api-version=/i.test(text)) return "azure";
  if (/openrouter\.ai|OPENROUTER_/i.test(text)) return "openrouter";
  if (/deepseek\.com|DEEPSEEK_/i.test(text)) return "deepseek";
  if (/generativelanguage\.googleapis\.com|GEMINI_|GOOGLE_API_KEY|x-goog-api-key|generateContent/i.test(text)) return "gemini";
  if (/ANTHROPIC_|anthropic-version|claude/i.test(text)) return "anthropic";
  if (/\/responses\b|OPENAI_RESPONSES/i.test(text)) return "openai_responses";
  return "openai";
}

function parseRawCallIntoCard(card) {
  const raw = card.querySelector(".profileRawCall").value.trim();
  if (!raw) return;
  const env = readEnvLike(raw);
  const curlEndpoint = raw.match(/https?:\/\/[^\s'"\\]+/)?.[0]?.replace(/\\$/, "");
  const endpoint = firstValue(
    env.OPENAI_BASE_URL && buildEndpoint(env.OPENAI_BASE_URL, "/v1/chat/completions"),
    env.OPENAI_ENDPOINT,
    env.ANTHROPIC_BASE_URL && String(env.ANTHROPIC_BASE_URL).replace(/\/+$/, ""),
    env.ANTHROPIC_ENDPOINT,
    env.GEMINI_BASE_URL,
    env.GOOGLE_GEMINI_ENDPOINT,
    env.OPENROUTER_BASE_URL && buildEndpoint(env.OPENROUTER_BASE_URL, "/chat/completions"),
    env.DEEPSEEK_BASE_URL && buildEndpoint(env.DEEPSEEK_BASE_URL, "/chat/completions"),
    env.AZURE_OPENAI_ENDPOINT,
    curlEndpoint
  );
  const provider = inferProvider(raw, env, endpoint);
  const modelFromUrl = raw.match(/\/models\/([^\/\s:'"]+):generateContent/i)?.[1];
  const deploymentFromUrl = raw.match(/\/deployments\/([^\/\s?]+)/i)?.[1];
  const model = firstValue(
    env.OPENAI_MODEL,
    env.MODEL,
    env.ANTHROPIC_MODEL,
    env.CLAUDE_MODEL,
    env.GEMINI_MODEL,
    env.GOOGLE_MODEL,
    env.OPENROUTER_MODEL,
    env.DEEPSEEK_MODEL,
    env.AZURE_OPENAI_DEPLOYMENT,
    deploymentFromUrl,
    raw.match(/"model"\s*:\s*"([^"]+)"/)?.[1],
    raw.match(/model[=:]\s*["']?([^'"\s\\,}]+)/i)?.[1],
    modelFromUrl
  );
  const auth = firstValue(
    env.OPENAI_API_KEY,
    env.ANTHROPIC_API_KEY,
    env.ANTHROPIC_AUTH_TOKEN,
    env.GEMINI_API_KEY,
    env.GOOGLE_API_KEY,
    env.GENAI_API_KEY,
    env.OPENROUTER_API_KEY,
    env.DEEPSEEK_API_KEY,
    env.AZURE_OPENAI_API_KEY,
    raw.match(/Authorization:\s*Bearer\s+([^'"\s\\]+)/i)?.[1],
    raw.match(/(?:x-api-key|api-key|x-goog-api-key)[:=]\s*["']?([^'"\s\\]+)/i)?.[1],
    raw.match(/[?&]key=([^&\s'"]+)/i)?.[1]
  );
  const headers = {};
  for (const match of raw.matchAll(/-H\s+['"]([^:'"]+):\s*([^'"]+)['"]/g)) {
    const key = match[1].trim();
    const value = match[2].trim();
    if (!/^(authorization|x-api-key|api-key|x-goog-api-key)$/i.test(key)) headers[key] = value;
  }
  for (const match of raw.matchAll(/^\s*([A-Za-z][A-Za-z0-9_-]+):\s*([^\r\n]+)\s*$/gm)) {
    const key = match[1].trim();
    const value = match[2].trim().replace(/^["']|["']$/g, "");
    if (!/^(authorization|x-api-key|api-key|x-goog-api-key)$/i.test(key)) headers[key] = value;
  }
  if (env.OPENROUTER_HTTP_REFERER) headers["HTTP-Referer"] = env.OPENROUTER_HTTP_REFERER;
  if (env.OPENROUTER_APP_NAME || env.OPENROUTER_X_TITLE) headers["X-Title"] = env.OPENROUTER_APP_NAME || env.OPENROUTER_X_TITLE;
  if (provider === "anthropic") headers["anthropic-version"] = headers["anthropic-version"] || env.ANTHROPIC_VERSION || "2023-06-01";
  if (provider === "anthropic" && env.ANTHROPIC_AUTH_TOKEN) headers["Authorization"] = "Bearer {{apiKey}}";

  if (provider === "azure") {
    const base = String(endpoint || "").replace(/\/+$/, "");
    const deployment = model || "deployment-name";
    const version = env.AZURE_OPENAI_API_VERSION || raw.match(/api-version=([^&\s'"]+)/i)?.[1] || "2024-02-15-preview";
    if (!/\/chat\/completions/i.test(base)) {
      const azureBase = base || "https://your-resource.openai.azure.com";
      card.querySelector(".profileEndpoint").value = `${azureBase}/openai/deployments/${deployment}/chat/completions?api-version=${version}`;
    } else if (endpoint) {
      card.querySelector(".profileEndpoint").value = endpoint;
    }
    card.querySelector(".profileMode").value = "custom_json";
    headers["api-key"] = auth || "";
    card.querySelector(".profileBodyTemplate").value = '{"messages":{{messages}},"temperature":0.7}';
    if (model) setModels(card, [model]);
  } else if (provider === "anthropic") {
    card.querySelector(".profileMode").value = "anthropic_messages";
    card.querySelector(".profileEndpoint").value = endpoint || "https://api.anthropic.com";
    if (env.ANTHROPIC_AUTH_TOKEN && /claude\.deeplumen\.io/i.test(endpoint || "")) {
      replaceModels(card, ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"]);
    }
  } else if (provider === "gemini") {
    card.querySelector(".profileMode").value = "gemini_generate_content";
    card.querySelector(".profileEndpoint").value = buildGeminiEndpoint(endpoint, modelFromUrl || model || "");
  } else if (provider === "openai_responses") {
    card.querySelector(".profileMode").value = "openai_responses";
    const responseEndpoint = raw.match(/https?:\/\/[^\s'"\\]*\/responses[^\s'"\\]*/i)?.[0]?.replace(/\\$/, "");
    card.querySelector(".profileEndpoint").value = responseEndpoint || (env.OPENAI_BASE_URL ? buildEndpoint(env.OPENAI_BASE_URL, "/v1/responses") : endpoint || "https://api.openai.com/v1/responses");
  } else {
    card.querySelector(".profileMode").value = "openai_chat";
    const defaults = {
      openrouter: "https://openrouter.ai/api/v1/chat/completions",
      deepseek: "https://api.deepseek.com/chat/completions",
      openai: "https://api.openai.com/v1/chat/completions"
    };
    card.querySelector(".profileEndpoint").value = endpoint || defaults[provider] || defaults.openai;
  }

  if (auth) card.querySelector(".profileKey").value = auth;
  setHeaders(card, headers);
  if (model && provider !== "azure") setModels(card, [model]);
  if (!card.querySelector(".profileModelList").value.trim()) {
    const defaults = {
      anthropic: ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"],
      gemini: ["gemini-1.5-pro", "gemini-1.5-flash"],
      openrouter: ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
      deepseek: ["deepseek-chat", "deepseek-reasoner"],
      openai: ["gpt-4o-mini"],
      openai_responses: ["gpt-4o-mini"]
    };
    setModels(card, defaults[provider] || []);
  }
  renderProfileOptions();
}

async function testProfileData(profile, resultEl) {
  const task = `test:${profile?.id || "dialog"}`;
  if (busyTasks.has(task)) return;
  busyTasks.add(task);
  resultEl.innerHTML = createProgress("正在检测连通性...");
  let value = 12;
  const timer = setInterval(() => {
    value = Math.min(90, value + Math.max(1, Math.round((90 - value) / 7)));
    setProgress(resultEl, value, "正在检测连通性...");
  }, 700);
  const model = profile.availableModels[0] || "";
  try {
    const result = await api("/api/test-profile", {
      method: "POST",
      body: JSON.stringify({ profile, model })
    });
    clearInterval(timer);
    setProgress(resultEl, 100, "连通性检测通过");
    setTimeout(() => {
      resultEl.textContent = `OK: ${result.mode} / ${result.model}`;
    }, 500);
  } catch (error) {
    clearInterval(timer);
    setProgress(resultEl, 100, "连通性检测失败");
    setTimeout(() => {
      resultEl.textContent = error.message;
    }, 500);
    throw error;
  } finally {
    busyTasks.delete(task);
  }
}

async function init() {
  renderOutline(null);
  renderIntentOptions();
  setOutlineSubStep("research");
  requireEl("promptEvolution").innerHTML = `<p class="muted">迭代完成后会显示每一轮的内容修改差异。</p>`;
  bindEvents();
  await loadConfig();
  renderSearchSuggestions();
  await loadBlogs();
}

init().catch(showError);
