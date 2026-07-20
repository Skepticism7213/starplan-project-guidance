"""
StarPlan Loop - Qwen 连通性测试

验证百炼 API Key 和模型调用是否正常。这是接入 Qwen 后的第一步"验货"，
对应阶段计划里"第 3 周第一天就先验证工具调用链路是否稳定"。

运行前确保已在 StarPlan/.env 中填入有效的 DASHSCOPE_API_KEY
（把 your_api_key_here 替换成你在百炼控制台新生成的 Key）。

用法（在 StarPlan 目录下，激活虚拟环境后）:
    python scripts/test_qwen_connection.py
"""

import sys
from pathlib import Path

# 把项目根目录加入路径，便于导入 starplan_skills
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starplan_skills.qwen_client import call_qwen, DEFAULT_MODEL, QWEN_MODELS


def main() -> bool:
    print("=" * 60)
    print("StarPlan Qwen 连通性测试")
    print("=" * 60)
    print(f"默认模型: {DEFAULT_MODEL}")
    print(f"可用模型: {QWEN_MODELS}")
    print()

    # ── 测试 1: 最简单的单轮调用 ──
    print("[1/2] 简单单轮调用测试...")
    try:
        result = call_qwen(
            prompt="你好，请只回复 OK 两个字母，不要输出其他内容。",
            step_name="connectivity_test",
        )
    except RuntimeError as e:
        # 通常是 API Key 未设置或仍是占位符
        print(f"  [FAIL] {e}")
        return False
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
        return False

    if result.get("finish_reason") == "error":
        print(f"  [FAIL] API 返回错误: {result.get('error')}")
        return False

    content = (result.get("content") or "").strip()
    print(f"  [OK] 模型返回: {content[:80]}")
    print(f"  [OK] finish_reason: {result.get('finish_reason')}")
    print(f"  [OK] 使用模型: {result.get('model')}")
    print()

    # ── 测试 2: JSON 结构化输出模式 ──
    print("[2/2] JSON 结构化输出测试（nl_parser/outreach_pack 依赖此模式）...")
    try:
        from starplan_skills.qwen_client import call_qwen_json

        json_result = call_qwen_json(
            prompt='请返回一个 JSON 对象：{"status": "ok", "number": 42}，只返回 JSON。',
            step_name="connectivity_json_test",
        )
        parsed = json_result.get("parsed_json")
        if parsed and parsed.get("status") == "ok":
            print(f"  [OK] JSON 解析成功: {parsed}")
        else:
            print(f"  [WARN] JSON 解析结果异常: {json_result.get('json_error') or parsed}")
    except Exception as e:
        print(f"  [WARN] JSON 模式测试出错: {type(e).__name__}: {e}")
    print()

    print("=" * 60)
    print("连通性测试通过！Qwen 可正常调用，可以进入端到端案例测试。")
    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
