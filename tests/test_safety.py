from src.agent.safety import decide
from src.agent.tools import read_file, edit_file
class TestDangerousCommands:
    """危险命令必须 block。"""
    dangerous = [
        "rm -rf /",
        'rm -rf "D:\\Agent_Test\\test\\test.txt"',
        "rm -rf /tmp",
        "chmod 777 /",
        "sudo rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        "mkfs.xfs /dev/sdb1",
        "chown -R root:root /",
        "chmod -R 777 /etc",
        "tar -xvf x.tar -C /tmp",
    ]

    def test_dangerous_blocked(self):
        for cmd in self.dangerous:
            assert decide("execute_command", {"command": cmd})=="block",f"应拦截：{cmd}"

    def test_case_insensitive(self):
        """大小写变体也必须拦截。"""
        for cmd in ["RM -RF /", "Chmod 777 /", "SUDO rm -rf /"]:
            assert decide("execute_command", {"command": cmd}) == "block", f"应拦截: {cmd}"

class TestSafeCommands:
    """合法命令必须不 block。"""
    safe = [
        "ls -la",
        "python main.py",
        "echo hello",
        "git status",
        "chmod 755 myfile.py",
        "chown user:user myfile.py",
    ]

    def test_safe_not_blocked(self):
        for cmd in self.safe:
            assert decide("execute_command", {"command": cmd})!="block",f"不应拦截：{cmd}"

class TestToolDecision:
    """工具决策矩阵。"""

    def test_read_file_allows(self):
        assert decide("read_file", {"file_path": "x.py"}) == "allow"

    def test_edit_file_confirms(self):
        assert decide("edit_file", {"file_path": "x.py"}) == "confirm"

    def test_execute_command_confirms(self):
        assert decide("execute_command", {"command": "echo hi"}) == "confirm"

class TestReadFile:
    def test_normal(self):
        result = read_file.invoke({"file_path": "D:/Agent_Test/test/hello.py"})
        assert "print" in result          # 读到了内容

    def test_not_found(self):
        result = read_file.invoke({"file_path": "D:/Agent_Test/test/不存在.py"})
        assert "文件不存在" in result      # 错误处理

    def test_outside_workdir(self):
        result = read_file.invoke({"file_path": "D:/Windows/win.ini"})
        assert "只能访问工作目录" in result  # 沙箱拦截


class TestEditFile:
    def test_multi_match_rejected(self):
        result = edit_file.invoke({
            "file_path": "D:/Agent_Test/test/dup.txt",
            "old_string": "orange",
            "new_string": "apple",
        })
        assert "出现了" in result or "次" in result


