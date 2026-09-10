"""验证能耗计算分支的纯函数 + 集成点"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.chat_service import ChatService

svc = ChatService()

# 追踪结果
results = {"pass": 0, "fail": 0, "fails": []}


def check(name, ok, detail=""):
    if ok:
        results["pass"] += 1
        print(f"  [PASS] {name}")
    else:
        results["fail"] += 1
        results["fails"].append(name)
        print(f"  [FAIL] {name} {detail}")


print("=" * 60)
print("1. _extract_device_ids")
print("=" * 60)
check("正常提取", ChatService._extract_device_ids("[1001]+[1002]-[1003]") == [1001, 1002, 1003])
check("去重", ChatService._extract_device_ids("[1001]+[1001]+[1002]") == [1001, 1002])
check("空字符串", ChatService._extract_device_ids("") == [])
check("None", ChatService._extract_device_ids(None) == [])
check("乘法公式", ChatService._extract_device_ids("[1001]*2") == [1001])
check("带空格", ChatService._extract_device_ids("[ 1001 ] + [ 1002 ]") == [])

print()
print("=" * 60)
print("2. _eval_formula")
print("=" * 60)
check("加法", ChatService._eval_formula("[1001]+[1002]", {1001: 10, 1002: 20}) == 30.0)
check("减法", ChatService._eval_formula("[1001]-[1002]", {1001: 10, 1002: 20}) == -10.0)
check("乘法", ChatService._eval_formula("[1001]*[1002]", {1001: 10, 1002: 20}) == 200.0)
check("除法", ChatService._eval_formula("[1001]/[1002]", {1001: 10, 1002: 4}) == 2.5)
check("除0返回None", ChatService._eval_formula("[1001]/[1002]", {1001: 10, 1002: 0}) is None)
check("括号", ChatService._eval_formula("([1001]+[1002])*[1003]", {1001: 1, 1002: 2, 1003: 3}) == 9.0)
check("嵌套括号", ChatService._eval_formula("(([1001]+[1002])*[1003])-[1004]", {1001: 1, 1002: 2, 1003: 3, 1004: 5}) == 4.0)
check("缺失device默认0", ChatService._eval_formula("[1001]+[9999]", {1001: 10}) == 10.0)
check("空公式", ChatService._eval_formula("", {}) is None)
check("None公式", ChatService._eval_formula(None, {}) is None)
# 安全测试
check("恶意__import__被拒", ChatService._eval_formula("__import__('os')", {}) is None)
check("恶意exec被拒", ChatService._eval_formula("exec('print(1)')", {}) is None)
check("属性访问被拒", ChatService._eval_formula("[1001].__class__", {1001: 10}) is None)
check("纯数字表达式", ChatService._eval_formula("1+2*3", {}) == 7.0)
check("负号", ChatService._eval_formula("-[1001]", {1001: 10}) == -10.0)

print()
print("=" * 60)
print("3. _parse_energy_time_range")
print("=" * 60)
from datetime import date, timedelta

today = date.today()
# 本月(默认)
s, e = svc._parse_energy_time_range("各能源介质累计能耗是多少")
check("本月默认", s == today.replace(day=1) and e == today, f"got {s}~{e}")
# 本月显式
s, e = svc._parse_energy_time_range("本月各能介能耗")
check("本月显式", s == today.replace(day=1) and e == today, f"got {s}~{e}")
# 上月
s, e = svc._parse_energy_time_range("上月各能介能耗")
first_this = today.replace(day=1)
last_end = first_this - timedelta(days=1)
last_start = last_end.replace(day=1)
check("上月", s == last_start and e == last_end, f"got {s}~{e}, expect {last_start}~{last_end}")
# 最近7天
s, e = svc._parse_energy_time_range("最近7天各能介能耗")
check("最近7天", s == today - timedelta(days=6) and e == today, f"got {s}~{e}")
# 近30天
s, e = svc._parse_energy_time_range("近30天能耗统计")
check("近30天", s == today - timedelta(days=29) and e == today, f"got {s}~{e}")
# 过去3天
s, e = svc._parse_energy_time_range("过去3天能耗")
check("过去3天", s == today - timedelta(days=2) and e == today, f"got {s}~{e}")
# 今年
s, e = svc._parse_energy_time_range("今年各能介总能耗")
check("今年", s == date(today.year, 1, 1) and e == today, f"got {s}~{e}")
# 去年
s, e = svc._parse_energy_time_range("去年各能介总能耗")
check("去年", s == date(today.year - 1, 1, 1) and e == date(today.year - 1, 12, 31), f"got {s}~{e}")

print()
print("=" * 60)
print("4. _is_energy_formula_query")
print("=" * 60)
# 应匹配
check("各能源介质累计能耗", svc._is_energy_formula_query("各能源介质（电/水/气/热）本月累计能耗是多少?"))
check("各能介总能耗", svc._is_energy_formula_query("各能介本月总能耗"))
check("综合能耗", svc._is_energy_formula_query("电水气热本月综合能耗"))
check("能耗统计", svc._is_energy_formula_query("各能介累计能耗统计"))
check("用电量", svc._is_energy_formula_query("各能源介质用电量是多少"))
check("能耗汇总", svc._is_energy_formula_query("能介能耗汇总"))
# 不应匹配
check("设备级能耗不匹配", not svc._is_energy_formula_query("3号设备跑了多少电"))
check("折标煤系数不匹配", not svc._is_energy_formula_query("各能介的折标煤系数是多少"))
check("成本查询不匹配", not svc._is_energy_formula_query("某能源本月成本是多少"))
check("闲聊不匹配", not svc._is_energy_formula_query("今天天气怎么样"))
check("客流不匹配", not svc._is_energy_formula_query("今日场馆客流峰值最高?"))
check("单纯能耗不匹配", not svc._is_energy_formula_query("能耗是多少"))  # 没有能介聚合意图

print()
print("=" * 60)
print("5. 集成点验证:能耗问题被拦截, 非能耗问题走原路径")
print("=" * 60)
# 验证能耗问题会被拦截
check("能耗问题被分支拦截", svc._is_energy_formula_query("各能源介质本月累计能耗是多少?"))
# 验证非能耗问题不会被拦截(会走原 QA 匹配路径)
check("客流问题不被拦截", not svc._is_energy_formula_query("哪些场馆今天客流峰值最高?"))
check("告警问题不被拦截", not svc._is_energy_formula_query("当前有多少未处理的告警?"))
check("兜底问题不被拦截", not svc._is_energy_formula_query("你好,你是谁?"))

print()
print("=" * 60)
print(f"总计: {results['pass']} 通过, {results['fail']} 失败")
print("=" * 60)
if results["fail"]:
    print("失败用例:")
    for f in results["fails"]:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("全部通过!")
