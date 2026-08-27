---
name: commit
description: 生成规范的 git commit message
---

# Commit Message 规范

当你需要生成 git commit message 时，遵循以下规范：

1. **先看改动**：运行 `git status` 和 `git diff --stat` 查看改了哪些文件
2. **判断类型**：根据改动内容选一个前缀：
   - `feat:` 新功能
   - `fix:` 修复 bug
   - `docs:` 文档改动
   - `refactor:` 重构（不改功能）
   - `style:` 格式/样式（不影响逻辑）
   - `test:` 测试相关
   - `chore:` 杂项（依赖、构建等）
3. **标题规范**：`类型: 简短描述`，≤ 50 字符，描述用动宾短语（如 `feat: 添加用户登录`）
4. **正文**：如改动复杂，标题下空一行，用要点列"做了什么"
5. **不要**：不要用"update"这种含糊词，不要混用多个类型

示例：
feat: 添加用户注册功能

新增 register 接口和表单页面
添加邮箱格式校验
密码加密存储（bcrypt）