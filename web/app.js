const $ = (id) => document.getElementById(id);
let indexData = null;
const siteBase = new URL("./", window.location.href);

function fileUrl(relativePath) {
  return new URL(relativePath, siteBase).href;
}

function renderResult(title, description, relativePath) {
  const target = $("selection-result");
  target.replaceChildren();
  target.classList.remove("hidden");

  const heading = document.createElement("strong");
  heading.textContent = title;
  const detail = document.createElement("p");
  detail.className = "hint";
  detail.textContent = description;

  const actions = document.createElement("div");
  actions.className = "actions";
  const link = document.createElement("a");
  link.className = "link-button";
  link.href = fileUrl(relativePath);
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "查看 / 下載 TXT";

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "secondary";
  copy.textContent = "复制订阅网址";
  copy.addEventListener("click", () => copyUrl(link.href, copy));
  actions.append(link, copy);
  target.append(heading, detail, actions);
}

function copyUrl(url, button) {
  const original = button.textContent;
  const fallback = () => window.prompt("复制以下订阅网址：", url);
  if (!navigator.clipboard?.writeText) {
    fallback();
    return;
  }
  navigator.clipboard.writeText(url).then(() => {
    button.textContent = "已复制";
    window.setTimeout(() => { button.textContent = original; }, 1400);
  }).catch(fallback);
}

function populateChoices() {
  const select = $("region-choice");
  select.replaceChildren(new Option("请选择城市或省份", ""));

  const cities = [];
  const provinces = [];
  for (const province of indexData.regions) {
    for (const city of province.cities) {
      cities.push({ province, city });
    }
    if (province.province_url) provinces.push(province);
  }

  if (cities.length) {
    const group = document.createElement("optgroup");
    group.label = "城市完整清单（省级 IP + 城市专用 IP）";
    for (const item of cities.sort((a, b) => a.city.name.localeCompare(b.city.name, "zh-Hans"))) {
      const option = new Option(
        `${item.city.name}（${item.province.name}，共 ${item.city.total_count} 个）`,
        `city|${item.province.id}|${item.city.id}`
      );
      group.append(option);
    }
    select.append(group);
  }

  if (provinces.length) {
    const group = document.createElement("optgroup");
    group.label = "省级清单（只含省级适用 IP）";
    for (const province of provinces.sort((a, b) => a.name.localeCompare(b.name, "zh-Hans"))) {
      group.append(new Option(
        `${province.name}（${province.province_count} 个）`,
        `province|${province.id}`
      ));
    }
    select.append(group);
  }

  if (!cities.length && !provinces.length) {
    select.replaceChildren(new Option("目前没有可用地区数据", ""));
  }
  select.addEventListener("change", onChoiceChange);
}

function onChoiceChange() {
  const value = $("region-choice").value;
  const target = $("selection-result");
  target.classList.add("hidden");
  if (!value || !indexData) return;
  const parts = value.split("|");
  if (parts[0] === "province") {
    const province = indexData.regions.find(item => item.id === parts[1]);
    if (!province) return;
    renderResult(
      `${province.name}省级清单`,
      `共 ${province.province_count} 个省级适用节点，不包含城市专用 IP。`,
      province.province_url
    );
    return;
  }
  if (parts[0] === "city") {
    const province = indexData.regions.find(item => item.id === parts[1]);
    const city = province?.cities.find(item => item.id === parts[2]);
    if (!province || !city) return;
    renderResult(
      `${province.name} · ${city.name}完整清单`,
      `共 ${city.total_count} 个节点：省级适用 ${city.province_count_included} 个，城市专用 ${city.city_count} 个。`,
      city.url
    );
  }
}

async function init() {
  try {
    const response = await fetch(fileUrl("index.json"), { cache: "no-store" });
    if (!response.ok) throw new Error(`加载数据失败（HTTP ${response.status}）`);
    indexData = await response.json();
    $("total-count").textContent = indexData.total;
    $("province-count").textContent = indexData.province_total;
    $("city-count").textContent = indexData.city_total;
    $("updated").textContent = `数据更新日期：${indexData.updated}`;
    populateChoices();
    $("copy-all").addEventListener("click", (event) => {
      copyUrl(fileUrl("all.txt"), event.currentTarget);
    });
  } catch (error) {
    $("region-choice").replaceChildren(new Option("地区数据加载失败", ""));
    $("updated").textContent = error.message;
  }
}

init();
