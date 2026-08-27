---
name: test
description: 编写 pytest 单元测试：覆盖核心分支、边界条件和错误处理
---

# 单元测试规范

当你需要为代码编写测试时，遵循以下规范：

1. **先读代码**：理解函数/类的输入输出和逻辑，识别关键分支
2. **测试放在 `tests/` 目录**：文件名 `test_xxx.py`，测试函数名 `test_xxx` 开头
3. **覆盖维度**：
   - 正常路径：主要功能能用
   - 边界条件：空值、0、负数、超大值、None
   - 错误处理：异常、文件不存在、非法输入
   - 关键逻辑：if/else 分支、循环边界、返回值
4. **用 assert 断言**：`assert 函数(输入) == 期望输出`，不要用 print
5. **命名规范**：测试名说明场景，如 `test_read_file_not_found`、`test_calc_division_by_zero`
6. **测试要独立**：不依赖其他测试的执行顺序，不修改共享状态
7. **运行方式**：`python -m pytest tests/ -v`，全部通过才算完成

示例：
```python
# tests/test_calc.py
from src.agent.tools import calc

def test_calc_normal():
    assert calc(10, 2) == 5

def test_calc_division_by_zero():
    # 除零应报错或返回明确结果
    try:
        calc(10, 0)
        assert False, "应该抛出异常"
    except ZeroDivisionError:
        pass