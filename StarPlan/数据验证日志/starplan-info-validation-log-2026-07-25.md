# StarPlan INFO 级校验日志

日期：2026-07-25
校验环境：Windows 10 (x64) / Python 3.14.6 (py launcher) / Asia/Shanghai
校验范围：7.23 检测报告中 I-1 ~ I-6 全部 INFO 级确认项
校验性质：只读验证，未修改任何项目代码和数据

---

## 校验结果汇总

| 编号 | 项目 | 状态 | 关键数据 |
|------|------|------|----------|
| I-1 | Python/依赖 | PASS | Python 3.14.6; pip check 无冲突; astropy 8.0.1, astroplan 0.10.1, numpy 2.5.1, pydantic 2.13.4 可导入 |
| I-2 | 文本与配置 | PASS | 54 个文本文件严格 UTF-8 合法; 5 JSON 解析通过 (catalog 150条, locations 8条, 3 examples); 2 YAML 可读 |
| I-3 | 编译与 Schema | PASS | compileall 零错误; validate_examples 3/3 PASS |
| I-4 | Layer 1 | PASS | 150 条目录 x 10 轮 x 4 类检查 = 0 issue; 轮次一致性 [0,0,0,0,0,0,0,0,0,0] |
| I-5 | 暮光 | PASS | 自研二分 18:58:49 vs astroplan 18:58:46; 差值 3.2s; 容差 2min |
| I-6 | Qwen 连接 | PASS | 单轮调用 finish_reason=stop, 模型 qwen3.7-max; JSON 模式解析成功 |

---

## 与 7.23 报告的差异说明

- Python 版本从报告中的 3.13.7 升级为 3.14.6，不影响库兼容性和功能。
- I-6 首次执行时因 .env 缺失而阻塞，手动配置 DASHSCOPE_API_KEY 后复验通过。
- 终端中文乱码为 Windows cmd 输出捕获编码问题（代码页 936），非项目代码缺陷，写入文件的中文正常。

---

## 环境前置修复记录（手动完成，非代码改动）

1. 通过 py launcher 安装 Python 3.14.6，执行 pip install -r requirements.txt 安装全部依赖。
2. 将 StarPlan/.env.example 复制为 StarPlan/.env 并填入有效 DASHSCOPE_API_KEY。

---

## 结论

I-1 ~ I-6 全部通过，当前环境与 7.23 报告所描述的 INFO 级状态一致。
INFO 级项目为环境确认项，无代码缺陷，无需修复。
待处理项为 C-1~C-5（CRITICAL）和 W-1~W-11（WARNING）。

---

## 校验命令记录

```
py -3.14 -c "import sys; print(sys.version)"
py -3.14 -m pip check
py -3.14 -c "import astropy, astroplan, numpy, pydantic; ..."
perl validate_utf8.pl   (54 files strict UTF-8)
perl validate_json.pl   (5 JSON + 2 YAML)
py -3.14 -m compileall -q starplan_skills scripts tests
py -3.14 scripts/validate_examples.py
py -3.14 tests/layer1_validation.py
py -3.14 i5_twilight_check.py
py -3.14 scripts/test_qwen_connection.py
```
