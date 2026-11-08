# 优选 IP 地区数据库

使用 GitHub Repository + GitHub Actions + GitHub Pages 发布地区查询网页及 TXT 清单。不需要租用服务器、数据库、Cloudflare Workers，也不需要安装第三方 Python 套件。

## 1. 日常只维护一个文件

`data/ip_list.txt` 是唯一需要人工维护的正式数据文件。每个 `IP:端口` 一行：

```text
104.16.4.14|北京,广东,新疆
104.16.142.237:8443|江苏/南京
1.2.3.4|广东/深圳
```

规则：

- 不写端口时默认 `443`；写了端口就使用指定端口。
- 同一 IP 不同端口是不同节点；同一 IP:端口只能写一行。
- 多省用英文逗号 `,` 分隔。
- 城市专用范围写成 `省份/城市`，例如 `广东/深圳`。
- 同一省份列出两个或以上城市时，按既定规则自动提升为省级适用。
- 同一笔资料不能同时写某省省级和该省城市级范围。
- 一笔资料可以同时包含不同省份的省级和城市级范围，例如 `广东,江苏/南京`。
- 省份使用标准全名，例如 `广东`，不要使用 `粤`；南京请写 `江苏/南京`。
- 不要把 `?`、`待测`、`无` 等不确定或无效地区放进正式数据。
- 文件请使用 UTF-8 编码。

## 2. 自动生成的结果

在项目根目录执行 `python3 scripts/generate.py`，输出到 `dist/`：

```text
dist/
├── index.html
├── style.css
├── app.js
├── index.json
├── all.txt
├── all.json
├── province/
│   └── guangdong.txt
└── city/
    └── jiangsu/
        └── 南京.txt
```

- `all.txt`：所有唯一节点，每个 IP:端口一次，备注列出完整适用地区。
- `province/*.txt`：只包含该省省级适用的节点，不含城市专用节点。
- `city/<province>/<city>.txt`：该省省级节点 + 该城市专用节点。
- 对外 TXT 格式：`IP:端口#备注`。
- 城市清单的每一行备注统一为 `省份-城市`；省级清单备注为省份；全部清单备注为原始适用范围。
- 没有省级节点的省份不会生成空省级 TXT，但仍会列出有城市数据的城市。
- `index.json` 由程序生成，网页用它自动建立实际有数据的城市和省份选项。

## 3. 本地测试

需要 Python 3.9 或更新版本；不需要安装第三方套件。

```bash
python3 scripts/generate.py
python3 -m unittest discover -s tests -v
```

若要在浏览器预览，请运行：

```bash
python3 -m http.server 8000 --directory dist
```

然后打开 `http://localhost:8000`。不要直接双击 `index.html`，部分浏览器会限制本机网页读取 JSON。

## 4. 部署到 GitHub Pages（一次性设置）

这套部署使用 GitHub Actions。先在 GitHub 网站启用 Pages，再上传项目文件，避免第一次自动部署抢在 Pages 设置之前运行。

### 建立 GitHub Repository 并启用 Pages

1. 登录 GitHub，按右上角 `+` → `New repository`。
2. Repository 名称填写 `ip-database`，可按需要改名。
3. 选择 `Public`，并勾选 `Add a README file`，然后创建 Repository。公开网页和 TXT 才能让其他人直接访问；GitHub Free 的 Pages 支持范围以 GitHub 当前方案说明为准。
4. 进入新 Repository → `Settings` → `Pages`。
5. 在 `Build and deployment` 的 `Source` 选择 `GitHub Actions`，保存设置。

### 用 GitHub Desktop 上传项目

1. 从 <https://desktop.github.com/> 安装 GitHub Desktop，并登录刚才使用的 GitHub 账号。
2. 在 GitHub Desktop 选择 `File` → `Clone Repository`，选取刚建立的 `ip-database`，再选择本机保存位置并点击 `Clone`。
3. 解压本项目 ZIP。用 Finder 分别打开解压后的 `ip-database` 文件夹，以及刚才 GitHub Desktop 克隆出来的 `ip-database` 文件夹。
4. 在解压后的项目文件夹按 `Command + Shift + .` 显示隐藏文件，按 `Command + A` 全选文件夹内的内容并复制。
5. 切换到 GitHub Desktop 克隆出来的文件夹，粘贴。若询问是否替换 README 或 `.gitignore`，选择替换。确认隐藏的 `.github` 文件夹也已经复制过去。
6. 切回 GitHub Desktop，确认变更清单包含 `.github/workflows/deploy.yml`、`data`、`scripts`、`web` 等文件。填写提交摘要，例如 `Add IP database project`，点击 `Commit to main`。
7. 点击 `Push origin`，把项目文件推送到 GitHub。

### 检查自动部署

1. 打开 Repository → `Actions`。
2. 找到 `Generate and deploy IP database` 工作，确认 `build` 和 `deploy` 两个 job 都成功。
3. 部署网址会显示在 Action 的部署结果，也可以在 Repository → `Settings` → `Pages` 查看。

网址通常是：

```text
https://你的GitHub账号.github.io/ip-database/
```

如果 Repository 名称不同，网址最后一段也会不同。

## 5. 日后更新数据

1. 只编辑 `data/ip_list.txt`。
2. 在 GitHub Desktop 填写提交摘要，例如 `Update IP region list`，点击 `Commit to main`。
3. 点击 `Push origin`。
4. GitHub Actions 会自动验证数据、重新生成 TXT 和网页、重新部署。
5. 如果生成失败，打开 Repository → `Actions` → 失败的工作，错误信息会附上数据行号；修正后重新提交即可。

也可以在 `Actions` 中手动运行 `Generate and deploy IP database`。

## 6. 自定义域名

不是必需品。先使用 GitHub Pages 提供的网址即可。以后如果有自己的域名，再到 `Settings` → `Pages` 设置 `Custom domain`，并按 GitHub 页面提示设置 DNS。没有域名不影响查询页面或订阅文件运行。

## 7. 验证与限制

- 重复的 IP:端口会导致生成失败，并提示两笔资料的行号；请将适用地区合并到同一行。
- 无效 IP、无效端口、未知省份、空城市名称、不确定地区标记会导致生成失败，不会悄悄进入订阅。
- 同一 IP 不同端口可以同时存在。
- 此项目负责数据分类和发布，不会主动测试 IP 的实际连接可用性。
- TXT 是指定的 `IP:端口#备注` 清单格式，不会自动把 IP 转换成 VLESS、VMess 等完整代理节点。
