# 恒岬温漂试验室

试验室的两台架独立抽测同一工况。资料员登记工况和单位，试验员按台架冻结完整测次，发行员只交付指定修订的统计证据。质控员在站端关闭后按两份固定站件和一个阈值签发报告。次班能更正来源并出新版，也能按原号领取左、右台架的原件引用和原裁决。

## 运行

需要 Python 3.11、标准库和 Python 自带的 SQLite 支持。在项目根目录运行。

```console
python3 -B check_project.py
python3 -B demo.py
```

第一条命令是运行平台提供的完整 `tests` 回归入口。演示在临时目录建立独立的试验清单库、两个台架库和中心库。它读取 `samples/`，关闭源端后签发初版，下一班录入勘误，再关闭源端签发新版，最后重开中心库领取和导出。输出保留精确有理参数。

## Python 接口

从 `database` 导入 `open_database` 创建业务连接。每个连接由调用方负责关闭，写入接口自行管理事务。通过各存储对象的 `initialize()` 建表，可以重复调用。清单、台架和中心可以使用独立连接及文件。

| 阶段 | 入口 | 返回 |
| --- | --- | --- |
| 登记 | `trial.protocols.register(registry, **spec)` | 清单号 |
| 取清单 | `trial.protocols.get_trial(registry, trial_id)` | `TrialSpec` |
| 冻结或勘误 | `station.intake.freeze(registry, source, trial_id, bench_id, rows, parent_id=None)` | 新修订号 |
| 发行 | `evidence.issue.issue(source, catalog, revision_id, reference_order=None)` | `StationPacket` |
| 接纳 | `review.intake.admit(registry, accepted, packet_json)` | 中心固定件号 |
| 签发 | `review.decision.decide(accepted, archive, first_id, second_id, limit)` | `ArchivedReport` |
| 领取 | `archive.readback.read(archive, report_id)` | `ArchivedReport` |
| 导出 | `archive.export.export_report(archive, report_id)` | 固定交班记录的 JSON 文本 |

`TrialRegistry` 持有清单，`SourceBook.get_revision` 按号取冻结队列，`PacketCatalog.get` 按原发行号取站件。发送者用 `evidence.packet_format.encode_packet` 序列化站件。中心用 `AcceptedStore.get` 从本地凭固定件号领取，`ArchiveStore` 负责报告和成功回执。`demo.py` 给出各类的完整导入和连接示例。

## 数据与口径

- 清单使用 `trial_id`、`condition`、`left_bench`、`right_bench`、`references` 和 `units`。`main` 是保留的主列标识。标识为无首尾空白的非空字符串。`units` 按三个通道标识各给一个 `unit` 和一个 `inputs` 数组。温差单位支持 `K`、`mK`、`uK`，约定单位总可用。
- 测次由 `run_id` 和 `values` 组成。`values` 恰含三个通道。读数可使用整数、`Fraction` 或有理数字符串，也可用 `{"value": "1500", "unit": "mK"}` 指定输入单位。零有效，浮点、布尔值、缺值和重复原号拒绝。勘误的 `parent_id` 必须属于同清单和同台架。勘误提交完整队列。
- V1 JSON 站件外层字段为 `version`、`issue_id`、`trial_id`、`bench_id`、`revision_id`、`body`。正文含 `channels`、`means`、`covariance`。`channels` 第一列是主通道，接着是两个具名参考。均值及矩阵按该顺序编码，矩阵的两轴采用同一个顺序。数字以规范有理数字符串发行。站件没有原号或原行。中心保留首次接纳的实质内容和原列序。相同身份及具名统计的重投可使用不同 JSON 排版或参考顺序。
- 统计是在同一完整队列上的总体均值和总体协方差，每对通道的中心乘积和除以行数。单行可发行。签发时比较两个具名参考的全部协方差，均值随件保留。公共参考的合法方向给出确定的主通道共享协方差，未配对主通道的残差可在半正定约束下共同变化。差值方差的全部可达范围以 `draft.m`、`draft.r` 表示为 `[m−√r,m+√r]`。上端以有理比较判定，等于 `draft.limit` 时 `draft.passed` 为真。
- 报告的 `draft.parents` 按左、右角色排列。每个父件含中心固定件号、发行号、台架号和修订号。`report_id` 和 `receipt` 在提交后可按号领取，导出沿用存档值。非法输入或内容冲突引发 `ValueError`，未知身份引发 `KeyError`，SQLite 写入错误由 `sqlite3.Error` 传出。无效裁决或失败提交不会增加报告、回执。超限是有报告和回执的正常裁决。

样例的两站公共参考均为 `U=V`，参考方差为 1，两个主方差为 2。主通道各有方差为 1 的共享部分和方差为 1 的残差，故初版差值范围为 `[0,4]`。阈值 3 拒绝放行，阈值 4 放行。勘误使甲站主通道与参考不相关，其主方差仍为 2。新版范围为 `[4−2√2,4+2√2]`。重开后，初版和新版仍分别绑定各自的固定父件。
