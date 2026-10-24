# 数据驱动与Allure报告（ui-test-framework · 文档07）

> 一句话：解决"同一套逻辑多组数据怎么写、测试结果怎么让人看懂"的问题——YAML + parametrize 做数据驱动，allure-pytest + Allure 命令行把结果变成带分组、附件、趋势的可视化报告。

## 1. 在整个框架中的位置

数据驱动与报告体系是框架的"输入与输出两端"：users.yaml 从入口喂用例，Allure 在出口消化结果。

```mermaid
flowchart LR
    subgraph 输入端·数据驱动
        Y[data/users.yaml<br/>valid_accounts + invalid_accounts]
        DL[common/data_loader.load_yaml]
        PM["pytest.mark.parametrize<br/>+ ids=中文名"]
    end
    subgraph 输出端·Allure
        DEC["@allure.feature / story<br/>装饰用例类与方法"]
        RES["reports/allure-results/*.json<br/>（pytest 运行时生成）"]
        GEN["allure generate"]
        REP["reports/allure-report/<br/>静态站点（HTML+JS）"]
    end
    TC[testcases 用例]

    Y --> DL --> PM --> TC
    TC -- 装饰 --> DEC
    TC -- 运行产生 --> RES --> GEN --> REP
```

依赖关系：
- 数据驱动只依赖 `data_loader`（统一编码与路径处理），用例层通过 `load_yaml(config["users_file"])` 取数据；
- Allure 分两级：**allure-pytest**（pytest 插件，运行时写 JSON 结果）与 **Allure 命令行**（独立 Java 程序，把 JSON 渲染成站点）——两者版本解耦，报告随时可以重生成。

## 2. 涉及文件

| 文件 | 职责 |
|---|---|
| `data/users.yaml` | 有效账号 2 组 + 失败场景 3 组（含期望文案） |
| `common/data_loader.py` | `load_yaml()`：utf-8 读取 + 项目根路径解析 |
| `testcases/test_login.py` | `test_login_failed_data_driven`：parametrize 消费 YAML |
| `testcases/test_*.py` | `@allure.feature/story` 装饰 + `@pytest.mark.smoke` |
| `pytest.ini` | `--alluredir=reports/allure-results --clean-alluredir` |
| `reports/allure-results/` | 每条用例一个 `-result.json` + 附件文件 |
| `reports/allure-report/` | generate 产出的静态站点 |

## 3. 如何实现（逐文件/逐方法讲解）

### 3.1 users.yaml 的结构设计

```yaml
valid_accounts:
  - username: lemon
    password: "123456"
    nickname: 柠檬          # 登录成功后 #nav-user 显示"你好，柠檬"——断言数据也进数据文件
  - username: test
    password: "123456"
    nickname: 测试号
invalid_accounts:
  - case_name: 密码错误          # ids 的来源：报告里显示中文名
    username: lemon
    password: "wrong_password"
    expected_flash: "用户名或密码错误"   # 期望值也数据化：断言文案与被测系统对齐
  - case_name: 用户不存在
    username: ghost_user
    ...
```

三个设计点：
1. **期望值跟着数据走**：`expected_flash` 写在数据文件里，数据驱动才算完整——否则"3 组数据 1 个写死的期望"是半吊子驱动；
2. **nickname 参与断言**：登录成功的断言（导航栏"你好，柠檬"）的数据来源也是本文件；
3. **`password: "123456"` 必须加引号**：YAML 会把裸的 `123456` 解析成 int，虽然 send_keys(str()) 兜底了，但数据文件的类型纪律必须守住。

### 3.2 data_loader 的两个防坑细节

```python
def load_yaml(relative_path: str) -> dict:
    path = project_root() / relative_path
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在：{path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
```

- `encoding="utf-8"`：Windows 默认编码是 GBK，中文 YAML 不显式指定必报 `UnicodeDecodeError`——这是 Windows 上写数据驱动最常见的第一坑；
- `or {}`：空文件 safe_load 返回 None，兜底成空 dict，避免下游 `None["valid_accounts"]` 的迷惑报错。

### 3.3 parametrize 的消费端

```python
@pytest.mark.parametrize(
    "case",
    load_yaml(config["users_file"])["invalid_accounts"],
    ids=lambda c: c["case_name"],
)
def test_login_failed_data_driven(self, driver, case):
    page = LoginPage(driver).open_login_page()
    page.login(case["username"], case["password"])
    actual_flash = page.flash_text_after_submit(case["expected_flash"])
    assert case["expected_flash"] in actual_flash
    assert "/login" in driver.current_url
```

- `case` 是整行 dict，用例内按 key 取用——加字段（如"期望 302 状态"）不用改签名；
- `ids=lambda c: c["case_name"]` 把报告里的 `case0/case1/case2` 换成"密码错误/用户不存在/空用户名"；
- `load_yaml` 在**收集期**（pytest 收集用例时）执行一次，运行期零 IO。

### 3.4 Allure 装饰与结果流

```python
@allure.feature("登录模块")          # 一级分组：业务模块
class TestLogin:
    @allure.story("登录成功")         # 二级分组：功能场景
    @pytest.mark.smoke               # pytest 标记：筛选用例集
    def test_login_success(self, driver): ...
```

- `feature`/`story` 决定报告左侧树状结构（模块→场景）；`smoke` 决定 `-m smoke` 能筛出什么；
- 运行时 allure-pytest 给每条用例写 `reports/allure-results/<uuid>-result.json`（含状态、分组、步骤、附件索引、开始结束时间）；
- `allure generate reports/allure-results -o reports/allure-report --clean` 把 JSON 渲染成静态站点（需要 Java）；
- `allure open reports/allure-report` 起本地服务展示。

### 3.5 pytest.ini 里的报告管线

```ini
addopts = --alluredir=reports/allure-results --clean-alluredir --reruns 1 --reruns-delay 1
```

`--alluredir` 让每次运行自动写结果（不用记参数）；`--clean-alluredir` 防止新旧结果混杂——**报告反映的永远是最近一次运行**，历史趋势是 CI 的事。

## 4. 为什么这样设计（决策点 + 备选方案对比表）

| 决策 | 备选方案 | 对比结论 |
|---|---|---|
| YAML 做数据文件 | Excel / CSV / JSON / @pytest.mark.parametrize 内联 | 内联最简单但改数据要动代码；Excel 要 openpyxl 且二进制难 review；CSV 表达不了嵌套（期望值多字段就捉急）；YAML 中文友好、注释友好、git diff 友好 |
| 期望文案进数据文件 | 期望写死在用例里 | 数据驱动断言分离不彻底的典型：加一组数据还要去改用例的 assert。期望跟数据走，新增场景真的零代码 |
| allure.feature/story 双层分组 | 只用一个 @allure.title | 单层报告 22 条平铺没法看；feature=模块、story=场景，正好映射"4 个测试文件 → N 个业务场景"，还能与测试计划对齐 |
| 结果 JSON 与报告渲染分离 | pytest 直接出 HTML（pytest-html） | pytest-html 一个文件搞定但交互弱、无历史趋势；Allure 两段式支持 feature 树、附件内嵌、历史趋势、缺陷归类，是大厂事实标准 |
| --clean-alluredir | 保留累积结果 | 累积会把"上次的失败"带进"这次的报告"造成误判；本地产物每次干净，历史归档交给 CI |
| smoke 标记只标 4 条核心链路 | 全标 / 不标 | 全标失去筛选意义；不标则回归时只能全跑。4 条（登录/列表/购物车合计/e2e 下单）15 秒跑完，覆盖核心链路 |

## 5. 怎么运行/验证

```bash
cd /d/软件测试/ui-test-framework

# 1) 数据文件加载验证
python -c "
from common.data_loader import load_yaml
d = load_yaml('data/users.yaml')
print('有效账号:', [(u['username'], u['nickname']) for u in d['valid_accounts']])
print('失败场景:', [c['case_name'] for c in d['invalid_accounts']])
"
# 真实输出：
# 有效账号: [('lemon', '柠檬'), ('test', '测试号')]
# 失败场景: ['密码错误', '用户不存在', '空用户名']

# 2) 数据驱动用例名验证（中文 ids；Git Bash 终端默认显示 \uXXXX 转义，
#    属于显示编码问题——Allure 报告里是正常中文，设置 PYTHONIOENCODING=utf-8 可改善终端显示）
python -m pytest testcases/test_login.py --collect-only -q
# 真实输出：
# testcases/test_login.py::TestLogin::test_login_failed_data_driven[\u5bc6\u7801\u9519\u8bef]   <- 密码错误
# testcases/test_login.py::TestLogin::test_login_failed_data_driven[\u7528\u6237\u4e0d\u5b58\u5728] <- 用户不存在
# testcases/test_login.py::TestLogin::test_login_failed_data_driven[\u7a7a\u7528\u6237\u540d]     <- 空用户名
# ...
# 7 tests collected in 0.01s

# 3) 全量运行产生结果文件（真实输出）
python -m pytest
# ======================== 22 passed in 79.44s (0:01:19) ========================
ls reports/allure-results/ | wc -l
# 114    （22 条用例 result.json + 重跑记录 + 各用例的 log/stdout 附件）

# 4) Allure 生成报告（真实输出，allure 2.30.0 需已安装并配置 PATH）
export PATH="/c/Users/37535/tools/allure-2.30.0/bin:$PATH"
allure generate reports/allure-results -o reports/allure-report --clean
# Report successfully generated to reports\allure-report
allure --version
# 2.30.0

# 5) 报告数据核对
python -c "
import json
s = json.load(open('reports/allure-report/widgets/summary.json', encoding='utf-8'))
print('total:', s['statistic']['total'], '| passed:', s['statistic']['passed'])
"
# total: 22 | passed: 22
allure open reports/allure-report    # 浏览器打开静态站点人工检查 feature/story 分组
```

## 6. 常见坑

1. **YAML 数值类型陷阱**：`password: 123456`（无引号）被解析成 int，`password: 012345` 甚至直接语法报错（八进制歧义）。纪律：数据文件里所有"看起来像号码/密码"的值一律加引号。
2. **中文编码三连坑**：读 YAML 忘了 `encoding="utf-8"`（GBK 报错）；parametrize 的 ids 中文在部分 Windows 终端显示 `\uXXXX`（显示问题，报告正常）；Allure 报告页面中文乱码（generate 时 JVM 编码，设置 `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8`）。
3. **allure-results 与 allure-report 混淆**：results 是 pytest 写的原始 JSON（每次运行自动产生），report 是 generate 出的静态站点（手动/CI 产生）。**改了用例必须重新跑 pytest 再 generate**，只 generate 不重跑看到的还是旧结果。
4. **--clean-alluredir 忘配**：新结果追加进旧目录，报告里出现"上次失败的幽灵用例"，总数对不上当前用例数。本项目已在 pytest.ini 固化。
5. **feature/story 忘装饰**：没装饰的用例在报告里归进"未知"分组，树状图缺枝少叶。自查命令：`grep -rL "allure.feature" testcases/test_*.py`（应无输出）。
6. **Java 环境缺失**：Allure 命令行是 Java 程序，`allure` 报 `JAVA_HOME is not set`。装 JDK 8+ 或用 scoop/choco 安装会自动带上依赖。

## 7. 面试怎么讲

**30 秒版本**：
"数据驱动我选 YAML + parametrize：账号、密码、期望 flash 文案都在 users.yaml，一条用例覆盖 3 组失败场景，ids 映射中文让报告可读；加载层统一 utf-8 和根路径解析防 Windows 坑。报告用 Allure 两段式——allure-pytest 运行时写 JSON 结果，allure generate 渲染静态站点，22 条用例按 feature/story 树状分组，失败截图内嵌在用例详情里。实测全量跑完 22/22，报告 summary 与 pytest 结果一致。"

**3 个高频追问及答法**：
1. *"为什么不用 Excel 管理测试数据？"* —— 我的场景是少量结构化数据 + 中文 + 注释需求 + git 协作，YAML 全占；Excel 的价值在"业务人员也能维护数据"的场景，代价是二进制 diff、额外依赖、合并冲突难解。工具跟着协作模式选，不跟流行选。
2. *"Allure 报告在 CI 里怎么用？"* —— CI 上 pytest 只负责产生 allure-results，然后 `allure generate` 成站点发布（GitHub Pages/Allure Service）；进阶做法是用 Allure 的 history 机制把上一轮 results 里的 history 拷贝进本轮，报告就有"趋势图/重试曲线"。我本地 --clean-alluredir 是为了单次运行纯净，CI 里则要保留。
3. *"数据驱动和关键字驱动的区别？"* —— 数据驱动是"同一操作流 × 多组数据"（我的登录失败用例）；关键字驱动是把操作抽象成关键字表（打开/点击/输入），用例变成表格行，适合非程序员维护但抽象成本高、调试难。本项目选择数据驱动，因为登录失败的差异真的只在数据；操作流有差异的场景（下单 vs 取消）就该写成不同用例而不是硬塞数据表。

## 8. 复现任务清单

1. **写 users.yaml 与 data_loader**：验收：第 5 节脚本 1 输出两组账号三个场景，中文无乱码。
2. **改造登录失败用例为数据驱动**：验收：`--collect-only -q` 能看到 3 条中文用例名；跑通 3 passed。
3. **给全部用例类和方法加 feature/story**：验收：`grep -rL "allure.feature" testcases/test_*.py` 无输出。
4. **配置 pytest.ini 报告管线**：验收：跑全量后 `reports/allure-results/` 出现 `*-result.json`，且文件数 = 用例数 + 附件数（22 条用例时实测 114 个文件）。
5. **安装 Allure 命令行并 generate**：验收：输出 `Report successfully generated`，summary.json 显示 `total: 22 | passed: 22`。
6. **人工浏览报告**：`allure open`，核对：Behaviors 页有 4 个 feature；点开任一失败（可造一条临时失败用例）能看到内嵌截图；Suites 页按文件分组正确。
7. **smoke 集验证**：`pytest -m smoke -v` 恰好收集 4 条且 15 秒左右跑完（实测 4 passed, 18 deselected in 15.04s）。
8. **数据驱动扩展练习**：在 users.yaml 的 invalid_accounts 加一行"密码为空"，跑登录模块变成 4 组数据全通过——验证"新增场景零代码改动"。
