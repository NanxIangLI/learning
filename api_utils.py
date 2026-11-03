import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

## 登录函数
import requests
import json
from typing import Optional, Dict, Any


def login_goodwe(
        # base_url: str = "https://test.we.goodwe.com", # test
        base_url: str = "https://uat.we.goodwe.com",  # uat
        account: str = "",
        password: str = "",
        remember_me: bool = False,
        session: Optional[requests.Session] = None
) -> Optional[requests.Session]:
    """
    登录 GoodWe 系统

    Args:
        base_url: 接口基础地址
        account: 账号
        password: 密码
        remember_me: 是否记住登录
        session: 可选，复用已有 session

    Returns:
        已登录的 Session 对象，失败返回 None
    """
    if session is None:
        session = requests.Session()

    login_url = f"{base_url}/api/manager/auth/login"
    login_payload = {
        "account": account,
        "pwd": password,
        "rememberMe": "true" if remember_me else "false"
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        print(f"🔐 正在登录: {account}")
        response = session.post(login_url, json=login_payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == "00000":
            token = data.get("data", {}).get("token")
            if token:
                session.headers.update({
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                })
                user_info = data.get("data", {}).get("userInfo", {})
                print(f"✅ 登录成功")
                print(f"👤 用户: {user_info.get('name', '')} ({user_info.get('username', '')})")
                return session
            else:
                print("❌ 未找到 token")
                return None
        else:
            print(f"❌ 登录失败: {data.get('description', '未知错误')}")
            return None

    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return None


def fetch_variable(
        session: requests.Session,
        context: Dict[str, Any],
        base_url: str = ""
) -> Dict[str, Any]:
    """
    获取变量数据（通用接口）
    """
    # 检查 base_url 是否为空
    if not base_url:
        print("❌ 错误: base_url 为空，请配置接口地址")
        return {}

    # 确保 base_url 有协议前缀
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    endpoint = "/api/e-price-template/rpc/variable/fetch"
    full_url = f"{base_url}{endpoint}"
    payload = {"context": context}

    try:
        response = session.post(
            full_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.MissingSchema as e:
        print(f"❌ URL 格式错误: {e}")
        print(f"   当前 base_url: {base_url}")
        print(f"   完整 URL: {full_url}")
        return {}
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接失败: {e}")
        return {}
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return {}
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return {}


def fetch_stand_price(
        session: requests.Session,
        period: str,  # valley / flat / peak / critical / deep
        month: str = "",
        asset_id: str = "",
        code: str = "",
        index: str = "",
        base_url: str = "",
        type: str = ""

) -> float:
    """
    获取指定时段的基准电价

    Args:
        session: 已登录的 Session
        month: 月份，格式 YYYY-MM-DD
        asset_id: 资产ID
        code: 时段代码 (valley/flat/peak/critical/deep)
        index: 索引值
        base_url: 接口基础地址

    Returns:
        基准电价 (float)，失败返回 0.0
    """


    context = {
        "type": type,
        "month": month,
        "assetId": asset_id,
        "periodCode": period,
        "variableCode": "standPriceFlat",
        "code": period,
        "index": period,
        "tagCode": "standPriceFlat"
    }

    # 传入 base_url
    data = fetch_variable(session, context, base_url)

    if data.get("code") == "00000":
        value = data.get("data", {}).get("value")
        if isinstance(value, (int, float)):
            print(f"✅ 获取到 {period}段基准电价: {value}")
            return float(value)
        elif isinstance(value, list) and value:
            price = float(value[0])
            print(f"✅ 获取到 {period} 段基准电价: {price}")
            return price
        else:
            print(f"⚠️ value 格式异常: {value}")
            return 0.0
    else:
        print(f"❌ 请求失败: {data.get('description', '未知错误')}")
        return 0.0


def fetch_stand_price_flat(
        session: requests.Session,
        period: str,  # valley / flat / peak / critical / deep
        month: str = "",
        asset_id: str = "",
        base_url: str = ""
) -> float:
    """
    获取指定时段的基准电价 (standPriceFlat)

    Args:
        session: 已登录的 Session
        period: 时段，可选值: valley, flat, peak, critical, deep
        month: 月份，格式 YYYY-MM-DD
        asset_id: 资产ID
        base_url: 接口基础地址

    Returns:
        基准电价 (float)，失败返回 0.0
    """
    context = {
        "type": "default",
        "month": month,
        "assetId": asset_id,
        "periodCode": "flat",
        "variableCode": "standPriceFlat",
        "code": period,
        "index": period,
        "tagCode": "standPriceFlat"
    }

    # 传入 base_url
    data = fetch_variable(session, context, base_url)

    if data.get("code") == "00000":
        value = data.get("data", {}).get("value")
        if isinstance(value, (int, float)):
            print(f"✅ 获取到 {period} 段基准电价: {value}")
            return float(value)
        elif isinstance(value, list) and value:
            price = float(value[0])
            print(f"✅ 获取到 {period} 段基准电价: {price}")
            return price
        else:
            print(f"⚠️ value 格式异常: {value}")
            return 0.0
    else:
        print(f"❌ 请求失败: {data.get('description', '未知错误')}")
        return 0.0


# def calculate_package_price(actualEnergyArray, atAlgRealTimeArray):
#     """
#     计算加权平均价格（跳过无效值）
#
#     参数:
#         actualEnergyArray: 实际能量数组（作为权重）
#         atAlgRealTimeArray: 算法实时价格数组
#
#     返回:
#         加权平均价格
#     """
#     # 检查数组长度
#     if len(actualEnergyArray) != len(atAlgRealTimeArray):
#         raise ValueError("两个数组长度必须相同")
#
#     # 收集有效数据的索引
#     valid_indices = []
#     for i, energy in enumerate(actualEnergyArray):
#         # 跳过None、NaN和0值
#         if energy is not None and energy != 0:
#             try:
#                 # 检查是否为NaN
#                 if not (energy != energy):  # NaN的特性：NaN != NaN 为True
#                     valid_indices.append(i)
#             except:
#                 pass
#
#     # 如果没有有效数据，返回0
#     if not valid_indices:
#         return 0.0
#
#     # 计算加权平均
#     total_energy = 0.0
#     weighted_sum = 0.0
#
#     for idx in valid_indices:
#         energy = actualEnergyArray[idx]
#         price = atAlgRealTimeArray[idx]
#         total_energy += energy
#         weighted_sum += energy * price
#
#     package_price = weighted_sum / total_energy if total_energy != 0 else 0.0
#     return package_price


from decimal import Decimal, getcontext

# 设置精度（建议在文件开头统一设置）
getcontext().prec = 15


def calculate_package_price(actualEnergyArray, atAlgRealTimeArray):
    """
    计算加权平均价格（跳过无效值），返回 Decimal 类型

    参数:
        actualEnergyArray: 实际能量数组（作为权重）
        atAlgRealTimeArray: 算法实时价格数组

    返回:
        Decimal 类型的加权平均价格
    """
    # 检查数组长度
    if len(actualEnergyArray) != len(atAlgRealTimeArray):
        raise ValueError("两个数组长度必须相同")

    # 收集有效数据的索引
    valid_indices = []
    for i, energy in enumerate(actualEnergyArray):
        # 跳过None、NaN和0值
        if energy is not None and energy != 0:
            try:
                # 检查是否为NaN
                if not (energy != energy):  # NaN的特性：NaN != NaN 为True
                    valid_indices.append(i)
            except:
                pass

    # 如果没有有效数据，返回Decimal(0)
    if not valid_indices:
        return Decimal(0)

    # 使用 Decimal 高精度计算加权平均
    total_energy = Decimal(0)
    weighted_sum = Decimal(0)

    for idx in valid_indices:
        energy = Decimal(str(actualEnergyArray[idx]))
        price = Decimal(str(atAlgRealTimeArray[idx]))
        total_energy += energy
        weighted_sum += energy * price

    if total_energy != 0:
        package_price = weighted_sum / total_energy
    else:
        package_price = Decimal(0)

    return package_price
